"""Security control plane: dual-engine authorization, scope, fail-closed behaviour, quotas, rate limits, signed plans."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from florome.config import Settings
from florome.main import create_app
from florome.models import RemediationPlan
from tests.conftest import H, approve, rca_and_plan


def _target(c):
    return next(t for t in c.get("/api/v1/shield/repositories", headers=H("admin")).json()["authorized_targets"] if t["name"] == "ledgerlite")


def test_both_policy_engines_are_evaluated_and_recorded(client):
    c = client
    t = _target(c)
    assert c.post("/api/v1/shield/repositories", json={"name": "ll", "path": t["path"]}, headers=H("admin")).status_code == 201
    d = c.get("/api/v1/shield/policy/decisions", headers=H("viewer")).json()[0]
    assert d["allowed"] and d["engines"]["builtin"]["allow"] and d["engines"]["opa"] == {"engine": "opa", "status": "evaluated", "allow": True}


def test_out_of_scope_targets_are_refused(client, tmp_path):
    c = client
    for path in ("/etc", str(tmp_path), _target(c)["path"] + "/../../../../config.py"):
        r = c.post("/api/v1/shield/repositories", json={"name": "x", "path": path}, headers=H("admin"))
        assert r.status_code == 403 and "outside the authorised scope" in r.json()["detail"], path


def test_symlink_escape_out_of_scope_is_refused(settings, tmp_path):
    link = Path(settings.shield_authorized_roots[0]) / "zz_symlink_escape_test"
    try:
        os.symlink(tmp_path, link)
        app = create_app(settings)
        with TestClient(app) as c:
            r = c.post("/api/v1/shield/repositories", json={"name": "esc", "path": str(link)}, headers=H("admin"))
            assert r.status_code == 403
    finally:
        link.unlink(missing_ok=True)


def test_role_denials(client):
    c = client
    t = _target(c)
    assert c.post("/api/v1/shield/repositories", json={"name": "x", "path": t["path"]}, headers=H("operator")).status_code == 403
    assert c.post("/api/v1/shield/containment/run", json={"scenario": "benign_analysis"}, headers=H("operator")).status_code == 403
    assert c.post("/api/v1/shield/evaluation/run", headers=H("viewer")).status_code == 403


def test_opa_required_but_missing_fails_closed(settings, tmp_path):
    s = settings.model_copy(update={"shield_tools_dir": str(tmp_path), "shield_opa_mode": "required"})
    with TestClient(create_app(s)) as c:
        r = c.post("/api/v1/shield/repositories", json={"name": "x", "path": _target(c)["path"]}, headers=H("admin"))
        assert r.status_code == 403 and "OPA" in r.json()["detail"]


def test_opa_error_fails_closed(settings, tmp_path):
    fake = tmp_path / "opa"
    fake.write_text("#!/bin/sh\necho garbage\nexit 1\n")
    fake.chmod(0o755)
    s = settings.model_copy(update={"shield_tools_dir": str(tmp_path)})
    with TestClient(create_app(s)) as c:
        r = c.post("/api/v1/shield/repositories", json={"name": "x", "path": _target(c)["path"]}, headers=H("admin"))
        assert r.status_code == 403 and "fail closed" in r.json()["detail"]


def test_emergency_stop_blocks_code_execution(client):
    c = client
    c.post("/api/v1/governance/emergency-stop", json={"active": True}, headers=H("admin"))
    r = c.post("/api/v1/shield/containment/run", json={"scenario": "benign_analysis"}, headers=H("admin"))
    assert r.status_code == 403 and "Emergency stop" in r.json()["detail"]


def test_scan_quota(settings):
    s = settings.model_copy(update={"shield_scan_quota_per_hour": 0})
    with TestClient(create_app(s)) as c:
        repo = c.post("/api/v1/shield/repositories", json={"name": "q", "path": _target(c)["path"]}, headers=H("admin")).json()
        c.post(f"/api/v1/shield/repositories/{repo['id']}/ingest", headers=H("admin"))
        r = c.post(f"/api/v1/shield/repositories/{repo['id']}/scan", headers=H("admin"))
        assert r.status_code == 429 and "quota" in r.json()["detail"]


def test_rate_limit(settings):
    s = settings.model_copy(update={"rate_limit_per_minute": 3})
    with TestClient(create_app(s)) as c:
        codes = [c.post("/api/v1/shield/containment/run", json={"scenario": "nope"}, headers=H("admin")).status_code for _ in range(5)]
        assert codes[:3] == [404, 404, 404] and codes[3:] == [429, 429]
        assert c.post("/api/v1/shield/containment/run", json={"scenario": "nope"}, headers=H("operator")).status_code == 404  # per principal


def test_plan_signature_detects_db_tampering_even_with_recomputed_hash(client, db):
    from florome.actions.service import plan_hash

    c = client
    _, plan = rca_and_plan(c)
    approve(c, plan)
    p = db.get(RemediationPlan, plan["id"])
    steps = [dict(x) for x in p.steps]
    steps[0]["params"] = {"to_version": "v0.0.1"}
    p.steps = steps
    p.plan_hash = plan_hash(steps, p.policy_decision["validation_targets"], p.incident_id)  # attacker recomputes the hash
    db.commit()
    r = c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))
    assert r.status_code == 409 and "signature" in r.json()["detail"]


def test_missing_scanner_binaries_produce_a_visible_partial_scan(settings, tmp_path):
    s = settings.model_copy(update={"shield_tools_dir": str(tmp_path), "shield_opa_mode": "off"})
    with TestClient(create_app(s)) as c:
        repo = c.post("/api/v1/shield/repositories", json={"name": "p", "path": _target(c)["path"]}, headers=H("admin")).json()
        c.post(f"/api/v1/shield/repositories/{repo['id']}/ingest", headers=H("admin"))
        out = c.post(f"/api/v1/shield/repositories/{repo['id']}/scan", headers=H("admin")).json()
        st = {t["tool"]: t["status"] for t in out["tools"]}
        assert out["status"] == "partial" and st["opengrep"] == "not_installed" and st["trivy"] == "not_installed" and st["bandit"] == "succeeded"
