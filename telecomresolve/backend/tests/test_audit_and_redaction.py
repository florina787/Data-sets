import pytest
from sqlalchemy import select, text

from app.db import session_scope
from app.models.orm import AppendOnlyViolation, AuditEvent
from app.observability.redaction import redact, redact_text
from conftest import investigate


def test_audit_is_append_only(client, login):
    investigate(client, login, "C-1002")
    with pytest.raises(AppendOnlyViolation):
        with session_scope() as db:
            e = db.scalars(select(AuditEvent)).first()
            e.event_type = "EDITED"
    with pytest.raises(AppendOnlyViolation):
        with session_scope() as db:
            db.delete(db.scalars(select(AuditEvent)).first())


def test_hash_chain_detects_out_of_band_edit(client, login):
    investigate(client, login, "C-1002")
    ok = client.get("/api/cases/C-1002/audit/replay", headers=login("u-sup-emma")).json()
    assert ok["hash_chain_valid"]
    with session_scope() as db:  # raw SQL bypasses ORM guards, like an attacker with DB access
        db.execute(text("UPDATE audit_events SET actor_id='someone-else' WHERE case_id='C-1002' "
                        "AND event_type='STATE_TRANSITION'"))
    bad = client.get("/api/cases/C-1002/audit/replay", headers=login("u-sup-emma")).json()
    assert not bad["hash_chain_valid"] and bad["chain_problems"]


def test_audit_records_trace_node_policy_and_mode(client, login):
    investigate(client, login, "C-1003")
    events = client.get("/api/cases/C-1003/audit", headers=login("u-sup-emma")).json()
    nodes = {e["node"] for e in events if e["node"]}
    assert {"triage", "evidence", "diagnosis", "planning"} <= nodes
    started = next(e for e in events if e["event_type"] == "INVESTIGATION_STARTED")
    trace = started["trace_id"]
    assert all(e["trace_id"] == trace for e in events if e["node"])
    assert all(e["generation_mode"] == "DEMO" for e in events if e["node"])
    assert all(e["policy_version"] for e in events if e["node"])
    ev = next(e for e in events if e["event_type"] == "EVIDENCE_COLLECTED")
    assert ev["detail"]["tool_calls"] and ev["request_id"]


def test_redaction():
    assert "[REDACTED_EMAIL]" in redact_text("contact me at jane.doe@example.com")
    assert "[REDACTED_PHONE]" in redact_text("call 416-555-0199 now")
    assert "sk-abc" not in redact_text("key sk-abcdefghijklmnop")
    assert redact({"contact_phone": "555", "nested": {"api_key": "x"}}) == \
        {"contact_phone": "[REDACTED]", "nested": {"api_key": "[REDACTED]"}}
