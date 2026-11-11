"""Deployment tooling: staging, secret scan, refusal rules, apply/rollback call sequence (fake Hub API, no network)."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


deploy = _load("hf_deploy")
rollback = _load("hf_rollback")


class FakeApi:
    calls: list = []

    def __init__(self, token=None):
        self.token = token

    def __getattr__(self, name):
        def f(*a, **k):
            FakeApi.calls.append((name, a, k))
            if name == "upload_folder":
                return SimpleNamespace(oid="newcommit123")
            if name == "list_repo_commits":
                from datetime import datetime
                return [SimpleNamespace(commit_id="aaa111" + "0" * 34, created_at=datetime(2026, 11, 1), title="Deploy v2"),
                        SimpleNamespace(commit_id="bbb222" + "0" * 34, created_at=datetime(2026, 10, 1), title="Deploy v1")]
            return None
        return f


@pytest.fixture(autouse=True)
def fake_hub(monkeypatch):
    import huggingface_hub
    FakeApi.calls = []
    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    for k in ("HF_TOKEN", "STRIPE_SECRET_KEY", "STRIPE_ALLOW_LIVE"):
        monkeypatch.delenv(k, raising=False)


def test_stage_excludes_dev_files_and_writes_manifest(tmp_path):
    out = tmp_path / "s"
    assert deploy.main(["--stage-only", "--out", str(out)]) == 0
    files = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {"Dockerfile", "start.sh", "README.md", "deploy-manifest.json", "backend/app/main.py", "frontend/package.json"} <= files
    assert not any(".venv" in f or "node_modules" in f or f.startswith("backend/tests") or f.endswith(".db") for f in files)
    assert "sdk: docker" in (out / "README.md").read_text()
    assert json.loads((out / "deploy-manifest.json").read_text())["files"] > 50


def test_secret_scan_blocks_planted_key(tmp_path):
    out = tmp_path / "s"
    deploy.main(["--stage-only", "--out", str(out)])
    (out / "backend" / "leak.py").write_text('KEY = "sk_live_' + "A1b2C3d4E5f6G7h8I9j0" + '"')
    assert deploy.scan_secrets(out) == ["backend/leak.py: stripe_secret"]


def test_dry_run_uploads_nothing(tmp_path):
    assert deploy.main(["--space", "o/s", "--out", str(tmp_path / "s")]) == 0
    assert FakeApi.calls == []


def test_live_stripe_config_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_ALLOW_LIVE", "true")
    assert deploy.main(["--space", "o/s", "--out", str(tmp_path / "s"), "--apply"]) == 3
    assert FakeApi.calls == []


def test_apply_creates_private_space_and_syncs_secrets_without_printing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_value_never_printed")
    monkeypatch.setenv("SUPABASE_URL", "https://ref.supabase.co")
    assert deploy.main(["--space", "o/s", "--out", str(tmp_path / "s"), "--apply", "--sync-secrets", "--allow-missing-config"]) == 0
    names = [c[0] for c in FakeApi.calls]
    assert names[0] == "create_repo" and FakeApi.calls[0][2]["private"] is True and FakeApi.calls[0][2]["space_sdk"] == "docker"
    assert ("add_space_secret", ("o/s", "STRIPE_SECRET_KEY", "sk_test_value_never_printed"), {}) in FakeApi.calls
    assert ("add_space_variable", ("o/s", "SUPABASE_URL", "https://ref.supabase.co"), {}) in FakeApi.calls
    up = next(c for c in FakeApi.calls if c[0] == "upload_folder")
    assert up[2]["delete_patterns"] == ["*"] and "Deploy careerflo" in up[2]["commit_message"]
    assert "update_repo_settings" not in names                         # stays private unless asked
    assert "sk_test_value_never_printed" not in capsys.readouterr().out


def test_rollback_dry_run_and_apply(monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    assert rollback.main(["--space", "o/s", "--to", "bbb222"]) == 0
    assert not any(c[0] == "upload_folder" for c in FakeApi.calls)
    assert rollback.main(["--space", "o/s", "--to", "bbb222", "--apply"]) == 0
    snap = next(c for c in FakeApi.calls if c[0] == "snapshot_download")
    assert snap[2]["revision"].startswith("bbb222")
    assert any(c[0] == "upload_folder" and "Rollback to bbb222" in c[2]["commit_message"] for c in FakeApi.calls)
    assert rollback.main(["--space", "o/s", "--to", "zzz"]) == 2
