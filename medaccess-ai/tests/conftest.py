"""Shared fixtures. All tests use synthetic data and an isolated temporary database."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="medaccess-test-"))
os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": f"sqlite:///{_TMP / 'test.db'}",
    "CHECKPOINT_DB_PATH": str(_TMP / "checkpoints.sqlite"),
    "JWT_SECRET": "test-only-secret-not-used-anywhere-else-0123456789",
    "LLM_ENABLED": "false",
    "LANGSMITH_TRACING": "false",
    "RETRY_BASE_DELAY_S": "0.001",
    "RATE_LIMIT_PER_MINUTE": "100000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.agents.registry import register_all  # noqa: E402
from app.database.session import init_db  # noqa: E402
from app.tools.patient_tools import register  # noqa: E402

register_all()
register()
init_db()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _token(client, user_id: str) -> dict:
    r = client.post("/api/v1/auth/demo-login", json={"user_id": user_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def patient(client):
    return _token(client, "usr-patient-demo")


@pytest.fixture(scope="session")
def engineer(client):
    return _token(client, "usr-engineer-demo")


@pytest.fixture(scope="session")
def approver(client):
    return _token(client, "usr-approver-demo")


@pytest.fixture(scope="session")
def admin(client):
    return _token(client, "usr-admin-demo")


@pytest.fixture(autouse=True)
def _reset_builds():
    from app.governance import builds
    from app.harness.core import reset_breakers

    builds.reset()
    reset_breakers()
    yield
    builds.reset()
