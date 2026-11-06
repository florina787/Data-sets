from app.policies import engine
from app.policies.state_machine import CaseStatus, can_transition
from app.retrieval.knowledge import chunk_sections


def test_chunking_preserves_offsets():
    body = "Intro\n\n## A\nalpha text\n\n## B\nbeta text\n"
    chunks = chunk_sections(body)
    assert [c[0] for c in chunks] == ["A", "B"]
    for heading, text, start, end in chunks:
        assert body[start:end] == text


def test_state_machine_rules():
    assert can_transition("AWAITING_APPROVAL", "APPROVED")
    assert not can_transition("RECOMMENDATION_READY", "EXECUTING")
    assert not can_transition("NEW", "RESOLVED")
    assert not can_transition("EXECUTING", "RESOLVED")  # success response is not recovery
    assert can_transition("VERIFYING", "MONITORING")
    assert all(isinstance(s, CaseStatus) for s in CaseStatus)


def test_dispatch_forbidden_during_active_incident():
    d = engine.evaluate("create_technician_dispatch",
                        {"fresh_diagnostics", "line_or_equipment_fault", "active_mapped_incident"})
    assert not d.allowed and "active_mapped_incident" in d.violations
    assert "no_active_mapped_incident" in d.unmet_requirements


def test_separation_of_duties():
    d = engine.evaluate("create_technician_dispatch",
                        {"fresh_diagnostics", "line_or_equipment_fault", "no_active_mapped_incident"})
    assert d.allowed
    assert not engine.can_approve("supervisor", "u1", "u1", d)[0]
    assert engine.can_approve("supervisor", "u2", "u1", d)[0]
    assert not engine.can_approve("specialist", "u2", "u1", d)[0]


def test_proposal_only_not_executable():
    d = engine.evaluate("reset_equipment", {"fresh_diagnostics", "equipment_fault"})
    assert d.allowed and not d.executable
    assert not engine.can_execute("supervisor", d)[0]


def test_unknown_action_refused():
    d = engine.evaluate("format_hard_drive", set())
    assert not d.allowed


def test_citation_validator_detects_changed_source(client, login):
    from sqlalchemy import select

    from app.db import session_scope
    from app.models.orm import KnowledgeChunk
    from conftest import investigate

    investigate(client, login, "C-1003")
    assert client.get("/api/cases/C-1003/citations/validate", headers=login("u-spec-ava")).json()["all_resolve"]
    with session_scope() as db:
        for ch in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == "KB-DSP-004")):
            ch.text = "rewritten"
    res = client.get("/api/cases/C-1003/citations/validate", headers=login("u-spec-ava")).json()
    assert not res["all_resolve"] and any("excerpt" in f["problem"] for f in res["failures"])


def test_connector_matrix_reports_enterprise_unavailable(client, login):
    r = client.get("/api/connectors", headers=login("u-spec-ava")).json()
    assert all(not c["available"] and c["mode"] == "UNCONFIGURED" for c in r["enterprise_connectors"])
    from app.connectors.base import ConnectorUnavailable
    from app.connectors.enterprise import get_enterprise
    import pytest

    with pytest.raises(ConnectorUnavailable):
        get_enterprise("customer_comms").call(to="x", body="y")


def test_health_ready_and_request_id(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/ready", headers={"X-Request-ID": "req-test-1"})
    assert r.status_code == 200 and r.headers["X-Request-ID"] == "req-test-1"
