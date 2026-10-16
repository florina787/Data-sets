"""AI-SDLC LangGraph: 15-stage defect lifecycle with two human checkpoints."""

import pytest

from app.governance import approvals, builds
from app.graphs import sdlc_graph
from app.sdlc_engine import qa, rca, requirements, simulation

pytestmark = pytest.mark.agents


def test_requirements_agent_detects_ambiguities():
    a = requirements.analyze("Patients should be able to find MRI appointments within 25 km.")
    codes = {q["code"] for q in a["ambiguities"]}
    assert {"VERIFIED_ONLY", "REQUISITION_ELIGIBILITY", "NO_RESULT_BEHAVIOUR", "RADIUS_EXPANSION",
            "PRIVATE_PAY"} <= codes
    assert a["status"] == "NEEDS_CLARIFICATION" and len(a["user_stories"]) >= 3
    assert all(c["id"].startswith(a["id"]) for c in a["acceptance_criteria"])


def test_qa_suite_has_20_plus_meaningful_scenarios():
    rep = qa.run_suite("1.4.0")
    assert rep["executed"] >= 20 and rep["failed"] == 0, [r for r in rep["results"] if not r["passed"]]


@pytest.mark.regression
def test_qa_detects_defective_build():
    rep = qa.run_suite("1.5.0")
    failed = {r["id"] for r in rep["results"] if not r["passed"]}
    assert failed == {"QA-013", "QA-014", "QA-015"}
    assert qa.run_suite("1.5.1", qa.REGRESSION_IDS)["failed"] == 0


def test_simulation_ground_truth():
    good = simulation.simulate(60, "1.4.0", emit_telemetry=False)
    bad = simulation.simulate(60, "1.5.0", emit_telemetry=False)
    assert good["recommendation_accuracy"] == 1.0 and good["unverified_presented_as_confirmed"] == 0
    assert bad["unverified_presented_as_confirmed"] > 0 and bad["recommendation_accuracy"] < 1.0
    assert bad["samples"][0]["source_status"] == "advertised"


def test_rca_requires_evidence():
    res = rca.analyze(None, "1.5.0")
    assert res["confirmed"] and res["component"].endswith("STATUS_MAPPINGS")
    assert "-    SourceSlotStatus.ADVERTISED: AvailabilityStatus.ADVERTISED_UNVERIFIED," in \
        next(e["diff"] for e in res["evidence"] if e["type"] == "code_diff")
    none = rca.analyze(None, "1.5.1")
    assert not none["confirmed"]  # no diff and no failing tests -> nothing asserted


def test_full_lifecycle_with_human_checkpoints():
    r = sdlc_graph.start("usr-engineer-demo", volume=40)
    assert r["status"] == "AWAITING_CLARIFICATION" and r["paused_at"] == ["human_clarification"]
    approvals.decide(r["approval_id"], "APPROVED", "usr-engineer-demo", "engineer")
    r = sdlc_graph.resume(r["run_id"], {"decision": "APPROVED", "answer": "Only verified appointments count.",
                                        "decided_by": "usr-engineer-demo"})
    assert r["status"] == "AWAITING_RELEASE_APPROVAL" and r["paused_at"] == ["release_approval"]
    assert {a["rule"] for a in r["anomalies"]} >= {"VERIFICATION_MISCLASSIFICATION", "UNVERIFIED_AS_CONFIRMED"}
    assert r["rca"]["confirmed"] and r["regression"]["fixed"]["failed"] == 0
    assert builds.active_build("demo-production").version == "1.5.0"
    with pytest.raises(PermissionError):  # engineer cannot approve releases
        approvals.decide(r["approval_id"], "APPROVED", "usr-engineer-demo", "engineer")
    approvals.decide(r["approval_id"], "APPROVED", "usr-approver-demo", "release_approver")
    r = sdlc_graph.resume(r["run_id"], {"decision": "APPROVED", "decided_by": "usr-approver-demo"})
    assert r["status"] == "COMPLETED" and r["post_release"]["defect_absent"]
    assert builds.active_build("demo-production").version == "1.5.1"
    assert len({s["stage"] for s in r["stage_log"]}) == 15
    chain = sdlc_graph.traceability(r["run_id"])
    assert [c["trace_ref"].split("-")[0] for c in chain][:1] == ["REQ"]
    assert {c["trace_ref"].split("-")[0] for c in chain} == {"REQ", "ARCH", "CODE", "TEST", "MON", "REL"}


def test_release_rejection_stops_deployment():
    r = sdlc_graph.start("usr-engineer-demo", volume=20)
    approvals.decide(r["approval_id"], "APPROVED", "usr-engineer-demo", "engineer")
    r = sdlc_graph.resume(r["run_id"], {"decision": "APPROVED", "answer": "", "decided_by": "usr-engineer-demo"})
    approvals.decide(r["approval_id"], "REJECTED", "usr-approver-demo", "release_approver")
    r = sdlc_graph.resume(r["run_id"], {"decision": "REJECTED", "decided_by": "usr-approver-demo"})
    assert r["status"] == "RELEASE_REJECTED"
    assert builds.active_build("demo-production").version == "1.5.0"


def test_graph_mermaid_generated_from_code():
    from app.graphs.patient_graph import mermaid

    m = mermaid()
    for n in ("clinical_safety", "recovery", "human_approval", "expansion_approval", "booking_handoff"):
        assert n in m
    assert "release_approval" in sdlc_graph.mermaid()
