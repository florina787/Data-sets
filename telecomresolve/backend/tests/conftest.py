import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="tr-test-"))
os.environ.update({
    "APP_MODE": "demo",
    "GENERATION_MODE": "DEMO",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}"),
    "CHECKPOINT_URL": os.environ.get("TEST_CHECKPOINT_URL", f"sqlite:///{_TMP / 'cp.db'}"),
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.agents import providers  # noqa: E402
from app.db import Base, get_engine, session_scope  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.workflows import checkpoints, graph  # noqa: E402


@pytest.fixture()
def client():
    providers.set_provider(None)
    graph.FAULT_HOOKS.clear()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    checkpoints.reset_checkpoints()
    graph.reset_graph()
    with session_scope() as db:
        seed(db)
    with TestClient(create_app(run_recovery=False)) as c:
        yield c
    graph.FAULT_HOOKS.clear()
    providers.set_provider(None)


@pytest.fixture()
def login(client):
    cache = {}

    def _login(persona: str, **extra) -> dict:
        if persona not in cache:
            r = client.post("/api/auth/demo-login", json={"persona_id": persona})
            assert r.status_code == 200, r.text
            cache[persona] = {"Authorization": f"Bearer {r.json()['token']}"}
        return {**cache[persona], **extra}

    return _login


def investigate(client, login, case_id, persona="u-spec-ava"):
    r = client.post(f"/api/cases/{case_id}/investigate?wait=true", headers=login(persona))
    assert r.status_code == 202, r.text
    return client.get(f"/api/cases/{case_id}", headers=login(persona)).json()


def approve(client, login, case_id, detail, persona="u-sup-emma", decision="approve", reason="ok"):
    rec, appr = detail["recommendation"], detail["approval"]
    return client.post(f"/api/cases/{case_id}/approvals", headers=login(persona),
                       json={"action": decision, "approval_id": appr["id"], "payload_hash": rec["payload_hash"],
                             "reason": reason})


def execute(client, login, case_id, approval_id, persona="u-field-dev", key="k-1"):
    return client.post(f"/api/cases/{case_id}/execute", headers=login(persona, **{"Idempotency-Key": key}),
                       json={"approval_id": approval_id})
