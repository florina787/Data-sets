"""Policy engine, execution modes, emergency stop, budgets, live/demo separation."""

from __future__ import annotations

from florome.governance.policy import DEFAULT_POLICY, evaluate_plan, validate_policy
from florome.models import Tenant
from tests.conftest import H, approve, incident_id, rca_and_plan


def step(action="create_ticket", risk="low", env="prod", reversible=True, tested=True, simulated=False, rollback="close"):
    return {"index": 0, "action_id": action, "risk": risk, "environment": env, "reversible": reversible, "tested": tested,
            "simulated": simulated, "rollback": rollback}


def pol(**kw):
    return {**DEFAULT_POLICY, **kw}


def test_autonomous_requires_every_step_allowlisted_low_risk_tested():
    ok = evaluate_plan([step()], pol(execution_mode="autonomous"), emergency_stop=False, tenant_mode="demo", actions_last_hour=0)
    assert ok.allowed and not ok.requires_approval
    for bad in (step(action="rerun_job", risk="medium"), step(tested=False), step(action="refresh_cache", env="prod"), step(risk="medium")):
        d = evaluate_plan([step(), bad], pol(execution_mode="autonomous"), emergency_stop=False, tenant_mode="demo", actions_last_hour=0)
        assert d.requires_approval, bad


def test_approval_mode_always_requires_approval():
    d = evaluate_plan([step()], pol(), emergency_stop=False, tenant_mode="demo", actions_last_hour=0)
    assert d.allowed and d.requires_approval


def test_observe_mode_emergency_stop_budget_and_live_mode_block():
    assert not evaluate_plan([step()], pol(execution_mode="observe"), emergency_stop=False, tenant_mode="demo", actions_last_hour=0).allowed
    assert not evaluate_plan([step()], pol(), emergency_stop=True, tenant_mode="demo", actions_last_hour=0).allowed
    assert not evaluate_plan([step()], pol(max_actions_per_hour=3), emergency_stop=False, tenant_mode="demo", actions_last_hour=3).allowed
    assert not evaluate_plan([step(simulated=True)], pol(), emergency_stop=False, tenant_mode="live", actions_last_hour=0).allowed
    assert not evaluate_plan([step(risk="high", reversible=False, rollback="")], pol(), emergency_stop=False, tenant_mode="demo",
                             actions_last_hour=0).allowed


def test_policy_cannot_disable_separation_of_duties(client):
    assert validate_policy(pol(require_separation_of_duties=False))
    r = client.put("/api/v1/governance/policy", json={"require_separation_of_duties": False}, headers=H("admin"))
    assert r.status_code == 422
    assert client.put("/api/v1/governance/policy", json={"execution_mode": "observe"}, headers=H("operator")).status_code == 403


def test_emergency_stop_blocks_approved_plan(client):
    c = client
    _, plan = rca_and_plan(c)
    approve(c, plan)
    assert c.post("/api/v1/governance/emergency-stop", json={"active": True, "reason": "test"}, headers=H("admin")).status_code == 200
    assert c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator")).status_code == 423
    c.post("/api/v1/governance/emergency-stop", json={"active": False}, headers=H("admin"))
    assert c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator")).json()["status"] == "succeeded"


def test_observe_mode_plan_is_blocked(client):
    c = client
    c.put("/api/v1/governance/policy", json={"execution_mode": "observe"}, headers=H("admin"))
    _, plan = rca_and_plan(c)
    assert plan["status"] == "blocked"


def test_inconclusive_rca_plans_no_state_changing_action(client, db):
    from florome.actions.planner import build_plan
    from florome.models import RCAReport, utcnow
    from florome.rca.service import load_topology

    c = client
    inc = incident_id(c)
    c.post(f"/api/v1/rca/{inc}", headers=H("operator"))
    rca = db.query(RCAReport).filter_by(incident_id=inc).one()
    report = {**rca.report, "challenge": {**rca.report["challenge"], "final_status": "inconclusive"}}
    topo = load_topology(db, "t-meridian")
    reg = c.ctx.registry
    plan = build_plan(report, topo, {}, lambda cid: reg.get(cid) if reg.has(cid) else None, utcnow())
    assert [s["action_id"] for s in plan["steps"]] == ["create_ticket"]
    assert any("no state-changing action" in n for n in plan["notes"])


def test_autonomous_mode_runs_ticket_only_plan_without_approval(client, db):
    c = client
    c.put("/api/v1/governance/policy", json={"execution_mode": "autonomous"}, headers=H("admin"))
    _, plan = rca_and_plan(c)
    assert plan["requires_approval"] is True  # rollback/replay/rerun are medium risk: autonomy is refused
    assert any("autonomous allow-list" in r for r in plan["policy_decision"]["reasons"])


def test_live_tenant_cannot_authenticate_with_demo_tokens(client, db):
    t = db.get(Tenant, "t-meridian")
    t.mode = "live"
    db.commit()
    assert client.get("/api/v1/me", headers=H("viewer")).status_code == 401
