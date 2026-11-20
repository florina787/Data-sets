"""MCP gateway against real stdio MCP servers: the bundled sandbox-ops server and a hostile test server."""

from __future__ import annotations

from florome.models import MCPToolRecord
from tests.conftest import H


def _server_id(c, name="sandbox-ops"):
    servers = c.get("/api/v1/mcp/servers", headers=H("admin")).json()["servers"]
    sid = next((s["id"] for s in servers if s["name"] == name), None)
    if sid is None:
        sid = c.post("/api/v1/mcp/servers", json={"name": name}, headers=H("admin")).json()["id"]
    return sid


def _tools(c, sid):
    r = c.post(f"/api/v1/mcp/servers/{sid}/discover", headers=H("admin"))
    assert r.status_code == 200, r.text
    return {t["name"]: t for t in r.json()}


def test_discovery_and_read_invocation(client):
    c = client
    sid = _server_id(c)
    tools = _tools(c, sid)
    assert set(tools) == {"get_service_status", "list_recent_errors", "restart_service"}
    assert tools["get_service_status"]["access"] == "read" and tools["get_service_status"]["enabled"]
    assert tools["restart_service"]["access"] == "write" and not tools["restart_service"]["enabled"]
    assert tools["list_recent_errors"]["input_schema"]["properties"]["limit"]["type"] == "integer"
    out = c.post(f"/api/v1/mcp/tools/{tools['get_service_status']['id']}/invoke", json={"arguments": {"service": "revenue-api"}},
                 headers=H("operator")).json()
    assert out["structured"]["health"] == "failed" and out["structured"]["simulated"] is True and out["untrusted_content_flags"] == []
    health = c.post(f"/api/v1/mcp/servers/{sid}/health", headers=H("viewer")).json()
    assert health["status"] == "healthy"


def test_argument_validation_and_write_denial(client):
    c = client
    tools = _tools(c, _server_id(c))
    bad = c.post(f"/api/v1/mcp/tools/{tools['list_recent_errors']['id']}/invoke", json={"arguments": {"service": 5}}, headers=H("operator"))
    assert bad.status_code == 422
    # enabling a write tool is possible for an admin, but direct invocation of writes is still refused
    c.post(f"/api/v1/mcp/tools/{tools['restart_service']['id']}/enable", headers=H("admin"))
    w = c.post(f"/api/v1/mcp/tools/{tools['restart_service']['id']}/invoke", json={"arguments": {"service": "revenue-api"}}, headers=H("admin"))
    assert w.status_code == 403 and "approved remediation plan" in w.json()["detail"]


def test_unauthorized_invocation(client):
    c = client
    tools = _tools(c, _server_id(c))
    r = c.post(f"/api/v1/mcp/tools/{tools['get_service_status']['id']}/invoke", json={"arguments": {"service": "x"}}, headers=H("viewer"))
    assert r.status_code == 403
    assert c.post(f"/api/v1/mcp/tools/{tools['get_service_status']['id']}/invoke", json={"arguments": {"service": "x"}},
                  headers=H("admin", "halcyon")).status_code == 404


def test_non_allowlisted_server_is_refused(client):
    r = client.post("/api/v1/mcp/servers", json={"name": "random-internet-server"}, headers=H("admin"))
    assert r.status_code == 403
    items = client.get("/api/v1/governance/audit?action=mcp.register", headers=H("viewer")).json()["items"]
    assert items[0]["outcome"] == "denied"


def test_malicious_server_tools_quarantined_and_output_sanitised(client):
    c = client
    sid = _server_id(c, "malicious")
    tools = _tools(c, sid)
    lookup = tools["lookup_customer"]
    assert not lookup["enabled"] and lookup["quarantine_reason"].startswith("Prompt-injection")
    assert c.post(f"/api/v1/mcp/tools/{lookup['id']}/enable", headers=H("admin")).status_code == 409
    status = tools["get_status"]
    assert not status["enabled"] and "non-bundled" in status["quarantine_reason"]  # default-deny for non-bundled servers
    assert c.post(f"/api/v1/mcp/tools/{status['id']}/invoke", json={"arguments": {"service": "x"}}, headers=H("operator")).status_code == 409
    assert c.post(f"/api/v1/mcp/tools/{status['id']}/enable", headers=H("admin")).json()["enabled"]
    out = c.post(f"/api/v1/mcp/tools/{status['id']}/invoke", json={"arguments": {"service": "x"}}, headers=H("operator")).json()
    assert "ghp_" not in out["text"] and "[REDACTED:github_token]" in out["text"]
    assert out["untrusted_content_flags"]


def test_schema_drift_disables_tool(client, db):
    c = client
    tools = _tools(c, _server_id(c))
    tid = tools["get_service_status"]["id"]
    t = db.get(MCPToolRecord, tid)
    t.schema_hash = "f" * 64  # what was reviewed no longer matches what the server now serves
    db.commit()
    r = c.post(f"/api/v1/mcp/tools/{tid}/invoke", json={"arguments": {"service": "revenue-api"}}, headers=H("operator"))
    assert r.status_code == 409 and "schema" in r.json()["detail"].lower()
    db.expire_all()
    assert db.get(MCPToolRecord, tid).enabled is False


def test_mcp_server_runs_without_inherited_secrets(client, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "should-not-leak")
    params = client.ctx.mcp._params("sandbox-ops")
    assert "AWS_SECRET_ACCESS_KEY" not in params.env and set(params.env) == {"PATH", "PYTHONPATH", "PYTHONIOENCODING"}
