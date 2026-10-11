from datetime import timedelta

from sqlalchemy import select

from app.db import session_scope, utcnow
from app.models.orm import ActionExecution, Approval, Case, Recommendation, SimulatedExternalRecord
from conftest import approve, execute, investigate


def test_execute_before_approval_blocked(client, login):
    d = investigate(client, login, "C-1011")
    r = execute(client, login, "C-1011", d["approval"]["id"], persona="u-sup-emma")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_APPROVED"


def test_approval_replay_and_duplicate_rejected(client, login):
    d = investigate(client, login, "C-1011")
    assert approve(client, login, "C-1011", d).status_code == 200
    again = approve(client, login, "C-1011", d)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "APPROVAL_NOT_PENDING"


def test_changed_payload_requires_new_review(client, login):
    d = investigate(client, login, "C-1011")
    bad = client.post("/api/cases/C-1011/approvals", headers=login("u-sup-emma"),
                      json={"action": "approve", "approval_id": d["approval"]["id"], "payload_hash": "f" * 64})
    assert bad.status_code == 409 and bad.json()["detail"]["code"] == "PAYLOAD_MISMATCH"
    # payload altered after approval -> execution refused
    assert approve(client, login, "C-1011", d).status_code == 200
    with session_scope() as db:
        rec = db.get(Recommendation, d["recommendation"]["id"])
        rec.payload = {**rec.payload, "dispatch_type": "install_new_line"}
    r = execute(client, login, "C-1011", d["approval"]["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PAYLOAD_TAMPERED"


def test_expired_approval_requires_new_review(client, login):
    d = investigate(client, login, "C-1011")
    with session_scope() as db:
        db.get(Approval, d["approval"]["id"]).expires_at = utcnow() - timedelta(minutes=1)
    r = approve(client, login, "C-1011", d)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "APPROVAL_EXPIRED"
    case = client.get("/api/cases/C-1011", headers=login("u-spec-ava")).json()
    assert case["status"] == "RECOMMENDATION_READY"
    new = client.post("/api/cases/C-1011/approvals", headers=login("u-spec-ava"),
                      json={"action": "request", "recommendation_id": case["recommendation"]["id"]})
    assert new.status_code == 200 and new.json()["status"] == "pending"


def test_expired_after_approval_blocks_execution(client, login):
    d = investigate(client, login, "C-1011")
    approve(client, login, "C-1011", d)
    with session_scope() as db:
        db.get(Approval, d["approval"]["id"]).expires_at = utcnow() - timedelta(seconds=1)
    r = execute(client, login, "C-1011", d["approval"]["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "APPROVAL_EXPIRED"


def test_stale_policy_version_rejected(client, login):
    d = investigate(client, login, "C-1011")
    with session_scope() as db:
        db.get(Approval, d["approval"]["id"]).policy_version = "old-version"
    r = approve(client, login, "C-1011", d)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "STALE_APPROVAL"


def test_unauthorized_executor_blocked(client, login):
    d = investigate(client, login, "C-1011")
    approve(client, login, "C-1011", d)
    r = execute(client, login, "C-1011", d["approval"]["id"], persona="u-spec-ben")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "EXECUTOR_NOT_AUTHORIZED"
    assert client.get("/api/cases/C-1011", headers=login("u-spec-ava")).json()["status"] == "APPROVED"


def test_idempotency_prevents_duplicate_dispatch(client, login):
    d = investigate(client, login, "C-1011")
    approve(client, login, "C-1011", d)
    first = execute(client, login, "C-1011", d["approval"]["id"], key="same")
    replay = execute(client, login, "C-1011", d["approval"]["id"], key="same")
    other = execute(client, login, "C-1011", d["approval"]["id"], key="different")
    assert first.status_code == 200 and replay.status_code == 200 and replay.json()["replayed"]
    assert other.status_code == 409 and other.json()["detail"]["code"] == "APPROVAL_ALREADY_USED"
    assert execute(client, login, "C-1011", d["approval"]["id"], key="").status_code == 422
    with session_scope() as db:
        assert len(db.scalars(select(ActionExecution).where(ActionExecution.case_id == "C-1011")).all()) == 1
        assert len(db.scalars(select(SimulatedExternalRecord).where(
            SimulatedExternalRecord.case_id == "C-1011")).all()) == 1


def test_lost_response_reconciled_without_duplicate(client, login):
    with session_scope() as db:
        c = db.get(Case, "C-1011")
        c.simulation_profile = {**c.simulation_profile, "write_fault": "timeout_after_create"}
    d = investigate(client, login, "C-1011")
    approve(client, login, "C-1011", d)
    r = execute(client, login, "C-1011", d["approval"]["id"], key="k")
    assert r.status_code == 200 and r.json()["execution"]["status"] == "unknown"
    assert r.json()["case"]["status"] == "EXECUTING"  # not marked failed: it may exist
    r2 = execute(client, login, "C-1011", d["approval"]["id"], key="k")
    assert r2.json()["execution"]["status"] == "succeeded" and r2.json()["case"]["status"] == "VERIFYING"
    with session_scope() as db:
        assert len(db.scalars(select(SimulatedExternalRecord).where(
            SimulatedExternalRecord.case_id == "C-1011")).all()) == 1
    audit = client.get("/api/cases/C-1011/audit", headers=login("u-spec-ava")).json()
    rec = next(e for e in audit if e["event_type"] == "EXECUTION_RECONCILED")
    assert rec["detail"]["found_existing"] is True


def test_timeout_before_create_retries_safely(client, login):
    with session_scope() as db:
        c = db.get(Case, "C-1011")
        c.simulation_profile = {**c.simulation_profile, "write_fault": "timeout_before_create"}
    d = investigate(client, login, "C-1011")
    approve(client, login, "C-1011", d)
    r = execute(client, login, "C-1011", d["approval"]["id"], key="k")
    assert r.json()["execution"]["status"] == "unknown"
    r2 = execute(client, login, "C-1011", d["approval"]["id"], key="k")
    assert r2.json()["execution"]["status"] == "succeeded" and r2.json()["execution"]["attempts"] == 2
    audit = client.get("/api/cases/C-1011/audit", headers=login("u-spec-ava")).json()
    assert next(e for e in audit if e["event_type"] == "EXECUTION_RECONCILED")["detail"]["found_existing"] is False


def test_specialist_can_self_confirm_low_risk_action(client, login):
    d = investigate(client, login, "C-1001")
    assert d["recommendation"]["approval_requirement"]["separation_of_duties"] is False
    assert approve(client, login, "C-1001", d, persona="u-spec-ava").status_code == 200
    r = execute(client, login, "C-1001", d["approval"]["id"], persona="u-spec-ava")
    assert r.status_code == 200
    assert client.get("/api/cases/C-1001", headers=login("u-spec-ava")).json()["linked_incident_id"] == "INC-7001"


def test_bill_credit_never_executable(client, login):
    from app.policies import engine

    d = engine.evaluate("apply_bill_credit", {"deterministic_eligibility", "financial_authority"})
    assert not d.allowed and not d.executable
    ok, _ = engine.can_execute("supervisor", d)
    assert not ok


def test_approval_queue_shows_decidable_items(client, login):
    investigate(client, login, "C-1003")
    q_sup = client.get("/api/approvals", headers=login("u-sup-emma")).json()
    q_spec = client.get("/api/approvals", headers=login("u-spec-ava")).json()
    item = next(a for a in q_sup if a["case_id"] == "C-1003")
    assert item["can_decide"] is True
    assert next(a for a in q_spec if a["case_id"] == "C-1003")["can_decide"] is False
