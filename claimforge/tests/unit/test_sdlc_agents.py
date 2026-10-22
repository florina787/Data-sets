"""Requirement ambiguity, policy evidence, impact, QA and release risk."""

from app.claims.rulesets import RULESET_V2, RULESET_V2_DEFECTIVE
from app.impact.analyzer import analyze_impact
from app.models.domain import ImpactAction
from app.policies.retrieval import INSUFFICIENT
from app.qa.test_generator import generate_test_cases, run_test_cases, summarize
from app.release.risk import RiskInputs, assess_release_risk
from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT, analyze_requirement_text


def test_13_requirement_ambiguity_blocks_workflow(platform):
    req = analyze_requirement_text(DEMO_REQUIREMENT)
    assert [a.ambiguity_id for a in req.blocking_ambiguities] == ["AMB-AUTH-THRESHOLD"]
    state = platform.run_workflow(DEMO_REQUIREMENT)
    assert state["status"] == "NEEDS_CLARIFICATION"
    assert "impact" not in state and "simulation" not in state  # nothing downstream ran
    nodes = [t["node"] for t in state["trace"]]
    assert "human_review" in nodes and "impact" not in nodes


def test_14_policy_evidence_includes_source(platform):
    res = platform.search_policy("physiotherapy annual maximum")
    assert res["status"] == "EVIDENCE_FOUND"
    top = res["evidence"][0]
    assert top["section_id"] == "P-14.2" and top["doc_id"] == "NSHB-POL-EHC-2026"
    assert top["citation"] == "[NSHB-POL-EHC-2026 §P-14.2]" and "$750" in top["text"]


def test_15_missing_evidence_not_fabricated(platform):
    res = platform.search_policy("orthodontic dental implants vision eyeglasses")
    assert res["status"] == INSUFFICIENT and res["evidence"] == []
    assert "No clause has been generated" in res["message"]


def test_16_impact_analysis_returns_expected_components():
    req = analyze_requirement_text(DEMO_REQUIREMENT, DEMO_CLARIFICATIONS)
    res = analyze_impact(req)
    changed = {i.component_id: i.action for i in res["impacts"] if i.action is not ImpactAction.KEEP}
    for cid in ("SVC-CLAIMS", "SVC-BENEFITS", "SVC-AUTH", "API-BENEFITS", "API-AUTH", "DB-BENEFIT-LIMITS",
                "DB-AUTH-RULES", "EVT-CLAIM-ADJ", "TEST-REGRESSION", "MON-CLAIMIQ"):
        assert cid in changed
    assert changed["NEW-VISIT-VIEW"] is ImpactAction.ADD
    assert changed["RULE-PHYSIO-CONST"] is ImpactAction.REPLACE
    assert res["summary"]["microservices_affected"] == 3 and res["summary"]["apis_affected"] == 2
    assert any(i.component_id == "GW-API" and i.impact_kind == "INDIRECT" for i in res["impacts"])
    assert any(i.component_id == "SVC-MEMBER" and i.action is ImpactAction.KEEP for i in res["impacts"])


def test_17_qa_generates_boundary_cases():
    req = analyze_requirement_text(DEMO_REQUIREMENT, DEMO_CLARIFICATIONS)
    cases = generate_test_cases(req)
    titles = " | ".join(c.title for c in cases if c.category == "boundary")
    assert "visit 10" in titles and "visit 11" in titles and "Cancelled visits excluded" in titles
    assert "$990.00" in titles and "effective date" in titles
    assert summarize(run_test_cases(cases, RULESET_V2))["failed"] == 0
    defective = summarize(run_test_cases(cases, RULESET_V2_DEFECTIVE))
    assert defective["critical_failed"] >= 1


def test_18_release_risk_increases_when_tests_fail():
    base = RiskInputs(components_affected=10, critical_components=3, rule_changes=2, tests_total=19, tests_failed=0,
                      claims_simulated=10_000)
    failed = RiskInputs(**{**base.__dict__, "tests_failed": 3, "critical_tests_failed": 0})
    assert assess_release_risk(failed).score > assess_release_risk(base).score
    assert assess_release_risk(failed).decision.value == "NOT READY"


def test_19_high_risk_release_blocked():
    inp = RiskInputs(components_affected=12, critical_components=4, rule_changes=3, tests_total=19, tests_failed=2,
                     critical_tests_failed=2, claims_simulated=10_000, unexpected_changes=295)
    risk = assess_release_risk(inp)
    assert risk.decision.value == "BLOCKED" and risk.blockers
    amb = assess_release_risk(RiskInputs(tests_total=5, unresolved_critical_ambiguities=1))
    assert amb.decision.value == "BLOCKED"
