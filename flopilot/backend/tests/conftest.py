from __future__ import annotations

import dataclasses
import io
import os
import tempfile
import time
from pathlib import Path

os.environ["FLOPILOT_SKIP_ENV_FILE"] = "1"
_TMP = tempfile.mkdtemp(prefix="flopilot-tests-")
os.environ["FLOPILOT_DATA_DIR"] = _TMP
os.environ.setdefault("FLOPILOT_RECALC_ENGINE", "none")
os.environ["FLOPILOT_LLM_PROVIDER"] = "demo"
os.environ["FLOPILOT_CHAT_RATE_PER_MIN"] = "100000"
os.environ["FLOPILOT_UPLOAD_RATE_PER_MIN"] = "100000"
os.environ.pop("ANTHROPIC_API_KEY", None)

import openpyxl  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

DEMO = Path(__file__).resolve().parents[1] / "sample_data" / "flopilot_demo_workbook.xlsx"
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "AWAITING_APPROVAL", "ROLLED_BACK"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, user: str = "florina") -> dict:
    token = client.post("/api/auth/demo-login", json={"user": user}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def H(client):
    return login(client)


@pytest.fixture()
def demo_wb(client, H) -> str:
    return client.post("/api/workbooks/demo", headers=H).json()["id"]


def upload(client, H, wb: openpyxl.Workbook | bytes, name: str = "test.xlsx") -> dict:
    if isinstance(wb, openpyxl.Workbook):
        buf = io.BytesIO()
        wb.save(buf)
        data = buf.getvalue()
    else:
        data = wb
    return client.post("/api/workbooks", headers=H, files={"file": (name, data)}).json()


def ask(client, H, wid: str, message: str, conversation_id: str | None = None, selection: dict | None = None) -> tuple[dict, str]:
    r = client.post(f"/api/workbooks/{wid}/chat", headers=H,
                    json={"message": message, "conversation_id": conversation_id, "selection": selection})
    assert r.status_code == 200, r.text
    body = r.json()
    run = wait_run(client, H, body["run_id"])
    return run, body["conversation_id"]


def wait_run(client, H, run_id: str, timeout: float = 60) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}", headers=H).json()
        if run["state"] in TERMINAL:
            return run
        time.sleep(0.03)
    raise AssertionError(f"run {run_id} did not finish")


def approve(client, H, op: dict, ack: bool = False, key: str | None = None):
    headers = dict(H)
    if key:
        headers["Idempotency-Key"] = key
    return client.post(f"/api/operations/{op['id']}/approve", headers=headers,
                       json={"expected_version": op["base_version"], "change_set_hash": op["change_set_hash"], "acknowledge_risks": ack})


@pytest.fixture()
def settings_override():
    original = config.get_settings()

    def apply(**kwargs):
        config._settings = dataclasses.replace(original, **kwargs)

    yield apply
    config._settings = original
