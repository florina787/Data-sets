import io
import json
import socket
import zipfile

import pytest

from tests.conftest import login


def test_envelope_and_security_headers(client):
    r = client.get("/health")
    body = r.json()
    assert set(body) == {"request_id", "data", "warnings", "provenance", "demo", "timestamp"}
    assert body["demo"]["live_ifs_connection"] is False
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-request-id"] == body["request_id"]


def test_typed_errors(client):
    r = client.get("/api/fleet/overview")
    assert r.status_code == 401 and set(r.json()) == {"code", "message", "details", "request_id"}
    r = client.get("/api/fleet/overview", headers={"Authorization": "Bearer abc.def"})
    assert r.json()["code"] == "bad_signature"
    h = login(client, "planner.marco")
    r = client.post("/api/chat/query", headers=h, json={"query": ""})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


def test_wrong_audience_token_rejected(client):
    from app.core.security import issue_token

    tok = issue_token("planner.marco", audience="ff-mcp-demo")
    r = client.get("/api/fleet/overview", headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 401 and r.json()["code"] == "wrong_audience"


def test_cross_screen_consistency(client, planner):
    f = client.get("/api/fleet/overview", headers=planner).json()["data"]
    assert f["total_aircraft"] == 150 == len(f["aircraft"]) == sum(f["by_status"].values()) == sum(f["by_type"].values())
    assert f["open_work_orders"] == sum(a["open_work_orders"] for a in f["aircraft"])
    sec = login(client, "sec.ines")
    wo = client.get("/api/maintenance/work-orders?status=open&limit=1", headers=sec).json()["data"]
    assert wo["total"] == f["open_work_orders"] or wo["total"] >= f["open_work_orders"]  # later tests may add planned WOs
    ac = client.get("/api/aircraft/AC-204", headers=planner).json()["data"]
    row = next(a for a in f["aircraft"] if a["id"] == "AC-204")
    assert row["health_score"] == ac["health"]["health_score"]
    parts = client.get("/api/parts/availability?part_number=P-7731", headers=planner).json()["data"]
    main = next(i for i in parts["items"] if i["location"] == "MAIN-HUB")
    assert main["conflict"] and main["verified_qty"] == 0


def test_work_orders_filtered_by_classification(client):
    exec_ = login(client, "exec.ava")
    r = client.get("/api/maintenance/work-orders?limit=500", headers=exec_).json()
    assert all(w["classification"] != "RESTRICTED" for w in r["data"]["items"])
    assert r["data"]["withheld_by_classification"] > 0


def test_guest_cannot_read_internal_endpoints(client):
    g = login(client, "guest")
    r = client.get("/api/fleet/overview", headers=g)
    assert r.status_code == 403 and r.json()["details"]["policy_id"] == "POL-003"


def test_chat_export_denial_via_api_zero_invocations(client, planner):
    tools = client.get("/api/bridge/tools", headers=planner).json()["data"]["tools"]
    before = next(t for t in tools if t["name"] == "records.export_email")["invocations"]
    r = client.post("/api/chat/query", headers=planner, json={"query": "Export restricted maintenance records to my personal email."}).json()["data"]
    assert r["status"] == "denied" and r["finished"]
    tools = client.get("/api/bridge/tools", headers=planner).json()["data"]["tools"]
    assert next(t for t in tools if t["name"] == "records.export_email")["invocations"] == before
    trace = next(b for b in r["state"]["workspace"] if b["type"] == "decision_trace")
    assert trace["decision"]["policy_id"] == "POL-004"


def test_async_query_polling_and_events(client, planner):
    r = client.post("/api/chat/query", headers=planner, json={"query": "Show me fleet health overview", "wait": False}).json()["data"]
    import time

    for _ in range(100):
        w = client.get(f"/api/workflows/{r['run_id']}", headers=planner).json()["data"]
        if w["finished"]:
            break
        time.sleep(0.05)
    assert w["finished"] and w["status"] == "completed"
    ev = client.get(f"/api/workflows/{r['run_id']}/events?after=0", headers=planner).json()["data"]["events"]
    assert ev[0]["step"] == "intake" and ev[-1]["step"] == "compose_workspace"


def test_replay_reports_reproducibility(client, planner):
    r = client.post("/api/chat/query", headers=planner, json={"query": "Compare 24-hour and 48-hour delay scenarios for a replacement part."}).json()["data"]
    rp = client.post(f"/api/workflows/{r['run_id']}/replay", headers=planner).json()["data"]
    assert rp["replay_of"] == r["run_id"] and rp["reproducibility"]["identical_fields"]["answer"]


def test_runs_are_private_to_owner(client, planner):
    r = client.post("/api/chat/query", headers=planner, json={"query": "Show me fleet health overview"}).json()["data"]
    other = login(client, "tech.jun")
    assert client.get(f"/api/workflows/{r['run_id']}", headers=other).status_code == 403
    assert client.get(f"/api/workflows/{r['run_id']}", headers=login(client, "audit.kai")).status_code == 200


def test_approval_flow_over_api(client, planner):
    r = client.post("/api/chat/query", headers=planner, json={"query": "Investigate abnormal vibration on AC-204 and draft a maintenance plan."}).json()["data"]
    appr = r["state"]["approvals"][0]
    assert client.post(f"/api/approvals/{appr['id']}/approve", headers=planner).status_code == 403  # separation of duties
    rel = login(client, "rel.nadia")
    a = client.post(f"/api/approvals/{appr['id']}/approve", headers=rel, json={"note": "ok"}).json()["data"]
    assert a["status"] == "approved"
    assert client.post(f"/api/approvals/{appr['id']}/approve", headers=rel).status_code == 409
    ex = client.post(f"/api/approvals/{appr['id']}/execute", headers=planner, json={"idempotency_key": appr["idempotency_key"]})
    assert ex.status_code == 200 and ex.json()["data"]["result"]["simulated"]
    again = client.post(f"/api/approvals/{appr['id']}/execute", headers=planner, json={"idempotency_key": appr["idempotency_key"]})
    assert again.status_code == 403 and again.json()["details"]["policy_id"] == "POL-005"


def test_reports_generate_and_download(client, planner):
    r = client.post("/api/reports/generate", headers=planner, json={"kind": "executive_brief", "fmt": "pdf"}).json()["data"]
    d = client.get(r["download"], headers=planner)
    assert d.status_code == 200 and d.content[:4] == b"%PDF"
    import hashlib

    assert hashlib.sha256(d.content).hexdigest() == r["sha256"]
    csv_ = client.post("/api/reports/generate", headers=planner, json={"kind": "work_orders", "fmt": "csv"}).json()["data"]
    body = client.get(csv_["download"], headers=planner).text
    assert body.startswith("id,") and "RESTRICTED" not in body
    assert client.get(r["download"], headers=login(client, "tech.jun")).status_code == 403
    assert client.post("/api/reports/generate", headers=planner, json={"kind": "audit_packet", "fmt": "json"}).status_code == 403
    aud = login(client, "audit.kai")
    p = client.post("/api/reports/generate", headers=aud, json={"kind": "audit_packet", "fmt": "json"}).json()["data"]
    packet = json.loads(client.get(p["download"], headers=aud).text)
    assert packet["verification"]["valid"]


def test_workspace_export_from_run(client, planner):
    r = client.post("/api/chat/query", headers=planner, json={"query": "Show which maintenance documents are stale or missing provenance."}).json()["data"]
    for fmt in ("md", "html", "json", "pdf"):
        rep = client.post("/api/reports/generate", headers=planner, json={"kind": "workspace", "fmt": fmt, "run_id": r["run_id"]})
        assert rep.status_code == 200, rep.text


def test_audit_verify_endpoint(client):
    aud = login(client, "audit.kai")
    assert client.post("/api/audit/verify", headers=aud, json={}).json()["data"]["valid"]
    exp = client.get("/api/audit/export", headers=aud)
    assert exp.status_code == 200 and json.loads(exp.text)["verification"]["valid"]
    assert client.post("/api/audit/verify", headers=login(client, "tech.jun"), json={}).status_code == 403


def test_kill_switch_over_api(client, planner):
    sec = login(client, "sec.ines")
    assert client.post("/api/governance/kill-switch", headers=planner, json={"on": True}).status_code == 403
    assert client.post("/api/governance/kill-switch", headers=sec, json={"on": True}).status_code == 200
    try:
        r = client.post("/api/chat/query", headers=planner, json={"query": "Show me fleet health overview"}).json()["data"]
        assert r["status"] == "denied"
    finally:
        client.post("/api/governance/kill-switch", headers=sec, json={"on": False})


# ---------------------------------------------------------------- Legacy X-Ray uploads

def _upload(client, h, name, content, ctype="application/octet-stream"):
    return client.post("/api/legacy/import", headers=h, files={"file": (name, content, ctype)})


def test_legacy_import_sql_and_openapi(client):
    h = login(client, "arch.olu")
    sql = b"-- system: Test MRO\nCREATE TABLE A (ID NUMBER PRIMARY KEY, B_ID NUMBER REFERENCES B(ID));\nCREATE TABLE B (ID NUMBER PRIMARY KEY);\nDROP TABLE A;"
    r = _upload(client, h, "test.sql", sql).json()["data"]
    assert r["kind"] == "sql_ddl" and r["summary"]["tables"] == 2 and r["summary"]["foreign_keys"] == 1
    oa = json.dumps({"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {"/x": {"post": {}}, "/admin/sql": {"post": {}}}}).encode()
    r = _upload(client, h, "api.json", oa).json()["data"]
    assert r["kind"] == "openapi" and any(f["kind"] == "dangerous_endpoint" for f in r["findings"])
    g = client.get("/api/legacy/graph", headers=h).json()["data"]
    assert any(n["id"] == "T:A" for n in g["nodes"])


@pytest.mark.parametrize("name,content,code", [
    ("evil.exe", b"MZ", "bad_extension"),
    ("big.sql", b"x" * (3 * 1024 * 1024), "too_large"),
    ("bin.sql", b"\x00\x01\x02CREATE", "binary_content"),
    ("x.xml", b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY b "c">]><a>&b;</a>', "xml_dtd"),
])
def test_legacy_import_rejections(client, name, content, code):
    h = login(client, "arch.olu")
    r = _upload(client, h, name, content)
    assert r.status_code == 422 and r.json()["code"] == code


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in entries:
            z.writestr(n, c)
    return buf.getvalue()


def test_zip_traversal_and_bomb_rejected(client):
    h = login(client, "arch.olu")
    r = _upload(client, h, "t.zip", _zip([("../../etc/passwd", "x")]))
    assert r.json()["code"] == "zip_traversal"
    r = _upload(client, h, "b.zip", _zip([("a.txt", "0" * (5 * 1024 * 1024))]))
    assert r.json()["code"] in ("zip_bomb", "zip_too_large")


def test_zip_source_bundle_analysed_not_executed(client, tmp_path):
    h = login(client, "arch.olu")
    marker = tmp_path / "executed"
    code = f"import os\nopen({str(marker)!r}, 'w').write('x')\npassword = 'hunter22'\nQ = 'SELECT * FROM MRO_STOCK_LOC'\n"
    java = 'package a.b;\nimport java.sql.*;\n@GetMapping("/stock")\nclass Stock { String q = "SELECT QTY FROM MRO_PART_MASTER"; }'
    r = _upload(client, h, "src.zip", _zip([("app/main.py", code), ("src/Stock.java", java), ("README.bin", "zz")])).json()["data"]
    assert not marker.exists()
    kinds = {f["kind"] for f in r["findings"]}
    assert {"hardcoded_secret", "embedded_sql"} <= kinds
    assert r["unsupported"][0]["path"] == "README.bin"


def test_import_requires_permission(client):
    r = _upload(client, login(client, "tech.jun"), "x.sql", b"CREATE TABLE A (ID INT);")
    assert r.status_code == 403


def test_legacy_recommend(client):
    h = login(client, "arch.olu")
    r = client.post("/api/legacy/recommend", headers=h).json()["data"]
    assert len(r["recommendations"]) == 8 and r["roadmap"] and r["unknowns"]
    for rec in r["recommendations"]:
        for key in ("why", "prerequisites", "evidence", "security_classification", "migration_risk", "implementation_steps", "rollback", "test_plan",
                    "effort_assumption", "tradeoffs", "confidence", "human_decisions", "diagram"):
            assert key in rec


# ---------------------------------------------------------------- Bridge + MCP

@pytest.mark.slow
def test_bridge_generate_and_run_generated_tests(client):
    h = login(client, "arch.olu")
    g = client.post("/api/bridge/generate", headers=h, json={}).json()["data"]
    assert all(c["passed"] for c in g["static_checks"])
    assert client.post("/api/bridge/test", headers=login(client, "tech.jun"), json={"bundle_id": g["bundle_id"]}).status_code == 403
    t = client.post("/api/bridge/test", headers=h, json={"bundle_id": g["bundle_id"]}).json()["data"]
    assert t["exit_code"] == 0 and t["failed"] == 0 and t["passed"] >= 12, t["output_tail"]
    z = client.get(f"/api/bridge/{g['bundle_id']}/download", headers=h)
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert any(n.endswith("mcp_server/server.py") for n in names) and any(n.endswith("THREAT_MODEL.md") for n in names)
    assert client.post("/api/bridge/generate", headers=h, json={"scopes": ["workorder.write"]}).status_code == 422


def test_untrusted_tool_cannot_register(client):
    h = login(client, "arch.olu")
    r = client.post("/api/bridge/register-tool", headers=h, json={"name": "shadow.exfiltrate", "version": "1.0.0"}).json()["data"]
    assert r["registered"] is False and "not on allowlist" in r["reason"]
    tools = client.get("/api/bridge/tools", headers=h).json()["data"]
    assert "shadow.exfiltrate" not in [t["name"] for t in tools["tools"]] and all(t["pin_ok"] for t in tools["tools"])


@pytest.mark.slow
def test_demo_mcp_server_discovery_and_authorization(client):
    r = client.get("/api/bridge/mcp-discover", headers=login(client, "planner.marco")).json()["data"]
    assert r["connected"] and all(t["pin_ok"] for t in r["tools"])
    assert r["calls"][0]["result"]["total_aircraft"] == 150
    r = client.get("/api/bridge/mcp-discover", headers=login(client, "sec.ines")).json()["data"]
    assert r["connected"]


def test_security_lab_all_scenarios_pass(client):
    r = client.post("/api/policy/tests/run", headers=login(client, "sec.ines")).json()["data"]
    failed = [x for x in r if not x["passed"]]
    assert not failed, failed
    assert len(r) == 12
    assert next(x for x in r if x["id"] == "external_export")["tool_invocations"] == 0


def test_policy_evaluate_lab(client):
    sec = login(client, "sec.ines")
    r = client.post("/api/policy/evaluate", headers=sec, json={"action": "read", "label": "RESTRICTED", "as_user": "exec.ava"}).json()["data"]
    assert r["decision"] == "DENY" and r["evaluated_for"] == "exec.ava" and r["executed"] is False
    assert client.post("/api/policy/evaluate", headers=login(client, "tech.jun"), json={"action": "read", "as_user": "sec.ines"}).status_code == 403


def test_offline_guard_blocks_external_egress(client):
    from app.core import egress

    assert egress.status()["installed"]
    with pytest.raises(OSError):
        socket.create_connection(("93.184.216.34", 80), timeout=1)
    with pytest.raises(OSError):
        socket.getaddrinfo("example.com", 443)
    st = client.get("/api/demo/status").json()["data"]
    assert st["egress_guard"]["blocked_attempts"] >= 2


def test_openapi_lists_contract_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/health", "/api/config", "/api/demo/status", "/api/demo/reset", "/api/personas", "/api/sessions", "/api/chat/query",
              "/api/workflows/{run_id}", "/api/workflows/{run_id}/events", "/api/workflows/{run_id}/cancel", "/api/workflows/{run_id}/replay",
              "/api/fleet/overview", "/api/aircraft/{ac_id}", "/api/maintenance/work-orders", "/api/parts/availability", "/api/legacy/import",
              "/api/legacy/systems", "/api/legacy/graph", "/api/legacy/recommend", "/api/bridge/generate", "/api/bridge/test", "/api/bridge/tools",
              "/api/policy/evaluate", "/api/policy/decisions", "/api/audit/events", "/api/audit/verify", "/api/approvals",
              "/api/approvals/{approval_id}/approve", "/api/approvals/{approval_id}/reject", "/api/simulations/compare", "/api/reports/generate",
              "/api/reports/{report_id}/download"]:
        assert p in paths, p
