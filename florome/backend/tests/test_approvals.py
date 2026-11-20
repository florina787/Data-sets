"""Approval enforcement: separation of duties, hash binding, replay, expiry, roles."""

from __future__ import annotations

from datetime import timedelta

from florome.models import Approval, utcnow
from tests.conftest import H, approve, nonce, rca_and_plan


def test_viewer_and_operator_cannot_approve(client):
    _, plan = rca_and_plan(client)
    assert approve(client, plan, role="viewer").status_code == 403
    assert approve(client, plan, role="operator").status_code == 403


def test_separation_of_duties_creator_cannot_approve(client):
    c = client
    inc, _ = rca_and_plan(c)
    plan = c.post("/api/v1/remediations", json={"incident_id": inc}, headers=H("admin")).json()  # admin creates
    r = approve(c, plan, role="admin")
    assert r.status_code == 403 and "Separation of duties" in r.json()["detail"]
    audit = c.get("/api/v1/governance/audit?action=plan.approve", headers=H("viewer")).json()["items"]
    assert audit[0]["outcome"] == "denied"


def test_stale_plan_hash_is_rejected(client):
    _, plan = rca_and_plan(client)
    r = approve(client, {**plan, "plan_hash": "0" * 64})
    assert r.status_code == 409 and "hash mismatch" in r.json()["detail"]


def test_nonce_replay_is_rejected(client):
    c = client
    _, plan = rca_and_plan(c)
    n = nonce()
    body = {"plan_id": plan["id"], "decision": "approve", "plan_hash": plan["plan_hash"], "nonce": n}
    assert c.post("/api/v1/approvals", json=body, headers=H("approver")).status_code == 201
    inc2, plan2 = plan["incident_id"], c.post("/api/v1/remediations", json={"incident_id": plan["incident_id"]}, headers=H("operator")).json()
    body2 = {**body, "plan_id": plan2["id"], "plan_hash": plan2["plan_hash"]}
    r = c.post("/api/v1/approvals", json=body2, headers=H("approver"))
    assert r.status_code == 409 and "replay" in r.json()["detail"]
    assert inc2


def test_rejected_plan_cannot_execute(client):
    c = client
    _, plan = rca_and_plan(c)
    assert approve(c, plan, decision="reject").json()["status"] == "rejected"
    assert c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator")).status_code == 409


def test_expired_approval_blocks_execution(client, db):
    c = client
    _, plan = rca_and_plan(c)
    approve(c, plan)
    a = db.query(Approval).filter_by(plan_id=plan["id"]).one()
    a.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    r = c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))
    assert r.status_code == 403 and "No valid approval" in r.json()["detail"]


def test_tampered_stored_plan_refuses_to_execute(client, db):
    from florome.models import RemediationPlan

    c = client
    _, plan = rca_and_plan(c)
    approve(c, plan)
    p = db.get(RemediationPlan, plan["id"])
    steps = [dict(s) for s in p.steps]
    steps[0]["params"] = {"to_version": "v0.0.1"}
    p.steps = steps
    db.commit()
    r = c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))
    assert r.status_code == 409 and "hash" in r.json()["detail"]
