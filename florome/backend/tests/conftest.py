from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from florome.config import Settings
from florome.main import create_app
from florome.models import session_factory


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", default_mode="demo", action_timeout_seconds=2.0,
                    mcp_allowlist_extra=["malicious=tests.mcp_fixtures.malicious_server"])


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        c.ctx = app.state.ctx  # type: ignore[attr-defined]
        yield c


@pytest.fixture
def db():
    s = session_factory()()
    try:
        yield s
    finally:
        s.close()


def H(role: str, tenant: str = "meridian") -> dict[str, str]:
    return {"Authorization": f"Bearer demo-{tenant}-{role}"}


def nonce() -> str:
    return secrets.token_hex(12)


def incident_id(c: TestClient, tenant: str = "meridian") -> str:
    return c.get("/api/v1/incidents", headers=H("viewer" if tenant == "meridian" else "operator", tenant)).json()["items"][0]["id"]


def rca_and_plan(c: TestClient, tenant: str = "meridian") -> tuple[str, dict]:
    inc = incident_id(c, tenant)
    assert c.post(f"/api/v1/rca/{inc}", headers=H("operator", tenant)).status_code == 201
    r = c.post("/api/v1/remediations", json={"incident_id": inc}, headers=H("operator", tenant))
    assert r.status_code == 201, r.text
    return inc, r.json()


def approve(c: TestClient, plan: dict, role: str = "approver", tenant: str = "meridian", **kw):
    body = {"plan_id": plan["id"], "decision": "approve", "plan_hash": plan["plan_hash"], "nonce": nonce(), **kw}
    return c.post("/api/v1/approvals", json=body, headers=H(role, tenant))


def sandbox(c: TestClient, tenant: str = "meridian"):
    conns = c.get("/api/v1/connections", headers=H("admin", tenant)).json()
    return c.ctx.registry.get(next(x["id"] for x in conns if x["connector_type"] == "sandbox"))
