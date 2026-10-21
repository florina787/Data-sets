import io
import json

from sqlalchemy import func, select

from app.db import session_scope
from app.models.orm import Action
from app.security.csv_safe import safe_cell, to_csv
from app.security.redaction import redact


def test_csv_formula_injection_is_neutralised():
    assert safe_cell("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert safe_cell("+1+1") == "'+1+1"
    assert safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert safe_cell("-3") == "-3" and safe_cell("12") == "12"
    assert "'=cmd" in to_csv(["a"], [["=cmd|' /C calc'!A0"]])


def test_redaction_patterns():
    text, counts = redact("email a.b@example.com card 4111 1111 1111 1111 call +1 415 555 0134 @12345 hi @BrandCare",
                          keep_handles={"BrandCare"})
    assert "example.com" not in text and "4111" not in text and "555" not in text
    assert "@[CUSTOMER]" in text and "@BrandCare" in text
    assert counts["EMAIL"] == 1 and counts["CARD"] == 1


def test_upload_rejects_non_csv_and_bad_schema(client):
    r = client.post("/api/imports/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/api/imports/upload", files={"file": ("x.csv", b"id,text\n1,hi\n", "text/csv")})
    assert r.status_code == 422 and "Missing required columns" in r.json()["detail"]


def test_local_import_cannot_escape_import_root(client):
    r = client.post("/api/imports/local", json={"path": "../../../../etc/passwd"})
    assert r.status_code == 403
    r = client.post("/api/imports/local", json={"path": "/etc/passwd"})
    assert r.status_code == 403


def test_upload_and_background_import_with_progress(client):
    from tests.conftest import FIXTURES
    data = (FIXTURES / "mini_twcs.csv").read_bytes()
    r = client.post("/api/imports/upload", files={"file": ("twcs.csv", data, "text/csv")}, data={"seed": "11"})
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    import time
    for _ in range(100):
        j = client.get(f"/api/imports/jobs/{jid}").json()
        if j["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert j["status"] == "completed", j
    assert j["progress"] == 1.0 and j["dataset_id"]
    ds = next(d for d in client.get("/api/datasets").json()["datasets"] if d["id"] == j["dataset_id"])
    assert ds["conversations"] == 4 and ds["synthetic"] is False  # actual count, never a nominal 3,000
    q = client.get(f"/api/datasets/{ds['id']}/quality").json()
    assert q["manifest"]["sampling"]["seed"] == 11 and q["cycles"]["messages_in_cycles"] == 2


def test_job_recovery_marks_interrupted(client):
    from app.ingestion.jobs import get_jobs
    from app.models.orm import ImportJob
    with session_scope() as s:
        s.add(ImportJob(id="job_stale", kind="local_path", status="running", params={"path": "/nonexistent.csv"}))
    assert get_jobs().recover() >= 1
    assert client.get("/api/imports/jobs/job_stale").json()["status"] == "interrupted"
    assert client.post("/api/imports/jobs/job_stale/resume").status_code == 200


def test_session_token_required(client, session, demo_ids):
    body = {"question": "Brief me on this dataset.", "dataset_id": demo_ids["demo"], "mode": "demo"}
    assert client.post("/api/flo/chat", json=body).status_code == 422  # missing headers
    bad = {**session, "X-Flo-Token": "nope"}
    assert client.post("/api/flo/chat", json=body, headers=bad).status_code == 403
    other = client.post("/api/flo/sessions").json()
    with client.stream("POST", "/api/flo/chat", json=body, headers=session) as r:
        events = [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]
    rid = events[0]["request_id"]
    assert client.get(f"/api/flo/runs/{rid}", headers=session).status_code == 200
    intr = {"X-Flo-Session": other["session_id"], "X-Flo-Token": other["session_token"]}
    assert client.get(f"/api/flo/runs/{rid}", headers=intr).status_code == 404
    assert client.get("/api/flo/runs", headers=intr).json()["runs"] == []


def test_sse_chat_approval_flow_single_record(client, session, demo_ids):
    body = {"question": "Propose an action to reduce unresolved refund issues", "dataset_id": demo_ids["demo"], "mode": "demo",
            "page": "overview", "filters": {"topics": ["billing_refunds"]}}
    with client.stream("POST", "/api/flo/chat", json=body, headers=session) as r:
        events = [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]
    assert [e for e in events if e["type"] == "approval_required"]
    rid = events[0]["request_id"]
    with session_scope() as s:
        before = s.scalar(select(func.count(Action.id)))
    dec = {"decision": "approve", "reviewer": "Head of Support", "edits": {"owner": "Billing operations lead", "due_date": "2026-12-01"}}
    with client.stream("POST", f"/api/flo/runs/{rid}/approval", json=dec, headers=session) as r:
        ev2 = [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]
    assert ev2[-1]["response"]["action_record"]["created"] is True
    assert client.post(f"/api/flo/runs/{rid}/approval", json=dec, headers=session).status_code == 409
    with session_scope() as s:
        assert s.scalar(select(func.count(Action.id))) == before + 1
    acts = client.get("/api/actions").json()["actions"]
    a = next(x for x in acts if x["investigation"]["request_id"] == rid)
    assert a["status"] == "approved" and a["due_date"] == "2026-12-01"
    r = client.patch(f"/api/actions/{a['id']}", json={"actor": "PM", "status": "completed"})
    assert r.status_code == 409  # approved -> completed is not a valid transition
    assert client.patch(f"/api/actions/{a['id']}", json={"actor": "PM", "status": "in_progress"}).json()["status"] == "in_progress"


def test_save_investigation_and_feedback(client, session, demo_ids):
    body = {"question": "Brief me on this dataset.", "dataset_id": demo_ids["demo"], "mode": "demo"}
    with client.stream("POST", "/api/flo/chat", json=body, headers=session) as r:
        events = [json.loads(l[6:]) for l in r.iter_lines() if l.startswith("data: ")]
    rid = events[0]["request_id"]
    assert client.post("/api/flo/investigations", json={"request_id": rid, "title": "Dataset brief"}, headers=session).status_code == 200
    assert client.get("/api/flo/investigations", headers=session).json()["investigations"][0]["title"] == "Dataset brief"
    fb = client.post(f"/api/flo/runs/{rid}/feedback", json={"score": 0, "correction": "Topic counts look high"}, headers=session).json()
    assert fb["saved"] and fb["sent_to_langsmith"] is False


def test_corrections_preserve_original_prediction(client, demo_ids):
    ds = demo_ids["demo"]
    item = client.get(f"/api/datasets/{ds}/conversations", params={"page_size": 1}).json()["items"][0]
    orig = item["resolution_status"]
    new = "unknown" if orig != "unknown" else "unresolved_explicit"
    r = client.post(f"/api/datasets/{ds}/conversations/{item['key']}/corrections",
                    json={"field": "resolution_status", "value": new, "reviewer": "QA"})
    assert r.status_code == 200
    d = client.get(f"/api/datasets/{ds}/conversations/{item['key']}").json()
    assert d["labels"]["resolution_status"] == new and d["labels"]["corrected"] is True
    assert d["corrections"][-1]["original"] == orig
    assert client.post(f"/api/datasets/{ds}/conversations/{item['key']}/corrections",
                       json={"field": "summary", "value": "x", "reviewer": "QA"}).status_code == 422


def test_pages_endpoints_respond(client, demo_ids):
    ds = demo_ids["demo"]
    for path in ["overview", "quality", "timeseries", "cohorts", "maps/issues", "maps/journey", "maps/ownership", "maps/geo",
                 "opportunities", "languages"]:
        assert client.get(f"/api/datasets/{ds}/{path}").status_code == 200, path
    geo = client.get(f"/api/datasets/{ds}/maps/geo").json()
    assert geo["available"] is False and "reliable location data is absent" in geo["reason"]
    assert client.get("/api/observability/graph").json()["nodes"][0] == "interpret_request"


def test_impact_review_empty_state_and_warning(client, demo_ids):
    ds = demo_ids["demo"]
    r = client.post("/api/impact", json={"baseline_dataset": ds, "intervention_date": "2030-01-01"}).json()
    assert r["followup_available"] is False and r["empty_state"]
    assert "does not show that the intervention caused it" in r["warning"]
    r = client.post("/api/impact", json={"baseline_dataset": ds, "intervention_date": "2017-11-01"}).json()
    assert r["followup_available"] and r["baseline"]["conversations"] + r["followup"]["conversations"] <= 422


def test_conversation_export_csv_is_safe(client, demo_ids):
    r = client.get(f"/api/datasets/{demo_ids['demo']}/conversations/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("conversation_key")
