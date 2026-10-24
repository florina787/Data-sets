import pytest

from app.core.security import load_actor
from app.services import approvals
from app.simulation.engine import DelayScenarioInputs, RoiInputs, compare_delays, roi


def _req():
    return approvals.create("work_order", "unit", load_actor("planner.marco"), {"aircraft_id": "AC-010", "title": "unit test", "part_number": "P-6008"})


def test_requester_cannot_approve_own_request():
    a = _req()
    with pytest.raises(approvals.ApprovalError) as e:
        approvals.decide(a["id"], load_actor("planner.marco"), True)
    assert "requester" in e.value.message


def test_non_approver_role_cannot_approve():
    a = _req()
    with pytest.raises(approvals.ApprovalError):
        approvals.decide(a["id"], load_actor("tech.jun"), True)


def test_write_requires_approval_then_runs_once():
    a = _req()
    with pytest.raises(approvals.ApprovalError):
        approvals.execute(a["id"], load_actor("planner.marco"), a["idempotency_key"])  # still pending
    d = approvals.decide(a["id"], load_actor("rel.nadia"), True)
    assert d["status"] == "approved" and d["evidence_sha256"]
    with pytest.raises(approvals.ApprovalError):
        approvals.execute(a["id"], load_actor("planner.marco"), "IDEM-wrong")
    r = approvals.execute(a["id"], load_actor("planner.marco"), a["idempotency_key"])
    assert r["result"]["work_order_id"].startswith("WO-")
    with pytest.raises(approvals.ApprovalError) as e:
        approvals.execute(a["id"], load_actor("planner.marco"), a["idempotency_key"])
    assert "Replay" in e.value.message


def test_duplicate_decision_rejected():
    a = _req()
    approvals.decide(a["id"], load_actor("rel.nadia"), False)
    with pytest.raises(approvals.ApprovalError) as e:
        approvals.decide(a["id"], load_actor("rel.nadia"), True)
    assert e.value.code == "already_decided"


def test_expired_approval_cannot_be_approved():
    a = approvals.create("work_order", "exp", load_actor("planner.marco"), {"aircraft_id": "AC-010"}, ttl_seconds=-5)
    with pytest.raises(approvals.ApprovalError) as e:
        approvals.decide(a["id"], load_actor("rel.nadia"), True)
    assert e.value.code == "expired"


def test_simulation_is_deterministic_and_explained():
    i = DelayScenarioInputs(delays_hours=[24, 48, 72])
    a, b = compare_delays(i), compare_delays(i)
    assert a == b
    d = {s["delay_hours"]: s for s in a["scenarios"]}
    assert d[24]["downtime_hours"] < d[48]["downtime_hours"] < d[72]["downtime_hours"]
    assert d[48]["cost_low_usd"] == d[48]["downtime_hours"] * i.downtime_cost_per_hour_low
    assert a["formulas"] and a["assumptions"] and a["sensitivity"]
    assert d[24]["monte_carlo"]["p90_hours"] >= d[24]["monte_carlo"]["p50_hours"]


def test_changing_lead_time_changes_result():
    base = compare_delays(DelayScenarioInputs(delays_hours=[24]))["scenarios"][0]["downtime_hours"]
    longer = compare_delays(DelayScenarioInputs(delays_hours=[60]))["scenarios"][0]["downtime_hours"]
    assert longer > base


def test_roi_formulas_and_zero_license_cost():
    r = roi(RoiInputs())
    assert r["inputs"]["incremental_software_license_cost"] == 0
    lo = r["annual_benefit"]["low"]
    assert lo["labor"] == round(320 * 12 * 95 * 0.15)
    assert r["annual_benefit"]["high"]["total"] > lo["total"]
    assert "Not a promise" in r["disclaimer"]
