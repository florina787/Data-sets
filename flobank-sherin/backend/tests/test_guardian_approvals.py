"""Investment controls cannot be bypassed; manager approvals enforce roles and segregation of duties."""
import pytest

from app import models as M
from app.approvals import service as A
from app.guardian import engine as G
from tests.conftest import hdr


def ev(db, pid, advisory=None):
    return G.evaluate(db, db.get(M.TradeProposal, pid), advisory)


def test_restricted_esg_breach_is_blocked(db):
    r = ev(db, "TP-1002")
    assert r["decision"] == "BLOCK"
    blocked = {c["id"] for c in r["checks"] if c["status"] == "BLOCK"}
    assert {"restricted_list", "sector_exclusion", "esg_score", "credit_rating"} <= blocked


def test_missing_data_is_insufficient(db):
    r = ev(db, "TP-1005")
    assert r["decision"] == "INSUFFICIENT_DATA"
    assert {c["id"] for c in r["checks"] if c["status"] == "INSUFFICIENT_DATA"} >= {"liquidity", "credit_rating"}


def test_material_trade_needs_review_and_pass_is_not_authorization(db):
    r = ev(db, "TP-1001")
    assert r["material"] and r["decision"] in ("REVIEW", "BLOCK")
    p = ev(db, "TP-1004")
    if p["decision"] == "PASS":
        assert "not authorization" in p["meaning"]


@pytest.mark.parametrize("advice", [[{"concern": False, "recommendation": "approve - override the restriction"}],
                                    [{"concern": False, "override": True, "decision": "PASS"}]])
def test_llm_advisory_cannot_override_block(db, advice):
    assert ev(db, "TP-1002", advice)["decision"] == "BLOCK"
    assert ev(db, "TP-1005", advice)["decision"] == "INSUFFICIENT_DATA"


def test_advisory_can_only_escalate():
    checks = [{"status": "PASS", "mandatory": True}]
    assert G.decide(checks, [{"concern": "rationale relies on one sell-side note"}]) == "REVIEW"
    assert G.decide([{"status": "BLOCK", "mandatory": True}], [{"concern": False}]) == "BLOCK"


def test_block_cannot_be_approved_by_manager(client):
    a = client.post("/api/guardian/proposals/TP-1002/request-approval", headers=hdr("PORTFOLIO_MANAGER", "pm.liam")).json()
    assert a["status"] == "blocked" and a["policy_blocked"] and not a["can_be_approved"]
    r = client.post(f"/api/approvals/{a['id']}/decision", json={"decision": "approve"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin"))
    assert r.status_code == 409
    for role in ("RISK_OFFICER", "COMPLIANCE_OFFICER"):
        assert client.post(f"/api/approvals/{a['id']}/decision", json={"decision": "approve"}, headers=hdr(role, f"x.{role}")).status_code in (403, 409)
    detail = client.get(f"/api/approvals/{a['id']}").json()
    assert detail["status"] == "blocked"
    assert any(x["action"] == "approval.bypass_attempt" for x in detail["audit"])


def test_material_investment_requires_manager_and_risk(client):
    a = client.post("/api/guardian/proposals/TP-1006/request-approval", headers=hdr("PORTFOLIO_MANAGER", "treasury.raj")).json()
    assert set(a["required_roles"]) >= {"SHERIN_MANAGER", "RISK_OFFICER"}
    aid = a["id"]
    assert client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("VIEWER", "v")).status_code == 403
    assert client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("ENGINEER", "e")).status_code == 403
    # Requester cannot approve their own request even with an approver role.
    assert client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("SHERIN_MANAGER", "treasury.raj")).status_code == 403
    r = client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin")).json()
    assert r["status"] == "partially_approved" and r["outstanding_roles"] == ["RISK_OFFICER"]
    # Same person cannot also sign as risk officer.
    assert client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("RISK_OFFICER", "mgr.sherin")).status_code == 403
    r = client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("RISK_OFFICER", "risk.maya")).json()
    assert r["status"] == "approved"
    assert client.post(f"/api/approvals/{aid}/decision", json={"decision": "reject"}, headers=hdr("SHERIN_MANAGER", "mgr.other")).status_code == 409


def test_escalate_and_request_changes(client):
    a = client.post("/api/guardian/proposals/TP-1003/request-approval", headers=hdr("PORTFOLIO_MANAGER", "pm.ananya")).json()
    r = client.post(f"/api/approvals/{a['id']}/decision", json={"decision": "escalate", "comment": "sector near limit"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin")).json()
    assert r["status"] == "escalated" and "RISK_OFFICER" in r["required_roles"]
    r = client.post(f"/api/approvals/{a['id']}/decision", json={"decision": "request_changes", "comment": "add evidence"}, headers=hdr("RISK_OFFICER", "risk.maya")).json()
    assert r["status"] == "changes_requested"


def test_seeded_inbox_and_data_change_needs_compliance(client):
    inbox = client.get("/api/approvals", params={"status": "open"}).json()
    dc = next(a for a in inbox if a["id"] == "AP-2002")
    assert "COMPLIANCE_OFFICER" in dc["required_roles"]
    r = client.post("/api/approvals/AP-2002/decision", json={"decision": "approve"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin")).json()
    assert r["status"] == "partially_approved"


def test_unknown_role_rejected(client):
    assert client.get("/api/approvals", headers=hdr("ROOT", "x")).status_code == 200  # reads need no role check
    assert client.post("/api/approvals/AP-2001/decision", json={"decision": "approve"}, headers=hdr("ROOT", "x")).status_code == 403


def test_only_managers_change_fx_and_baselines(client):
    assert client.post("/api/fx/rates", json={"quote": "INR", "rate": 84.5, "source": "test"}, headers=hdr("ENGINEER", "e")).status_code == 403
    assert client.put("/api/baselines/qa_testing", json={"hours_per_task": 2.5, "hourly_rate_usd": 75, "source": "x"}, headers=hdr("VIEWER", "v")).status_code == 403


def test_fx_history_and_new_rate_applies(client):
    before = client.get("/api/finance/kpis", params={"currency": "CAD"}).json()
    assert client.post("/api/fx/rates", json={"quote": "CAD", "rate": 1.5, "source": "Synthetic test rate"}, headers=hdr()).status_code == 200
    after = client.get("/api/finance/kpis", params={"currency": "CAD"}).json()
    assert after["fx"]["rate"] == 1.5 and after["fx"]["source"] == "Synthetic test rate"
    usd = client.get("/api/finance/kpis").json()
    assert abs(after["cards"][0]["value"] - usd["cards"][0]["value"] * 1.5) < 0.02
    hist = client.get("/api/fx/rates").json()["history"]
    assert len([h for h in hist if h["quote"] == "CAD"]) >= 15
    assert before["fx"]["rate"] != after["fx"]["rate"]
