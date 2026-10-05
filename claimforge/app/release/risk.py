"""Deterministic release-risk engine.

The score is a transparent weighted sum of evidence-based components (each capped),
clamped to 0–100. The release decision applies explicit blocking rules first.
No LLM is involved in scoring or in the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.domain import ReleaseDecision, ReleaseRisk, RiskLevel


@dataclass
class RiskInputs:
    components_affected: int = 0
    critical_components: int = 0
    rule_changes: int = 0
    tests_total: int = 0
    tests_failed: int = 0
    critical_tests_failed: int = 0
    claims_simulated: int = 0
    unexpected_changes: int = 0
    unresolved_critical_ambiguities: int = 0
    unresolved_other_ambiguities: int = 0
    annual_financial_impact: float = 0.0
    security_findings: dict[str, int] = field(default_factory=dict)  # severity -> count
    governance_fail: int = 0
    governance_warn: int = 0
    policy_evidence_missing: bool = False


def _cap(value: float, cap: float) -> float:
    return round(min(cap, max(0.0, value)), 2)


def score_components(inp: RiskInputs) -> dict[str, float]:
    unexpected_rate = inp.unexpected_changes / inp.claims_simulated if inp.claims_simulated else 0.0
    sec = inp.security_findings
    return {
        "components_affected": _cap(1.5 * inp.components_affected, 15),
        "critical_components": _cap(3 * inp.critical_components, 10),
        "rule_changes": _cap(4 * inp.rule_changes, 10),
        "failed_tests": _cap(15.0 if inp.tests_total == 0 else 8 * inp.tests_failed, 25),
        "unexpected_claim_differences": _cap((5 + unexpected_rate * 1000) if inp.unexpected_changes else 0, 20),
        "policy_ambiguity": _cap(20 * inp.unresolved_critical_ambiguities + 3 * inp.unresolved_other_ambiguities
                                 + (10 if inp.policy_evidence_missing else 0), 25),
        "financial_impact": _cap(abs(inp.annual_financial_impact) / 250_000 * 5, 10),
        "security_findings": _cap(15 * sec.get("CRITICAL", 0) + 6 * sec.get("HIGH", 0) + 2 * sec.get("MEDIUM", 0), 15),
        "governance_findings": _cap(5 * inp.governance_fail + 1 * inp.governance_warn, 10),
    }


def level_for(score: float) -> RiskLevel:
    if score < 25:
        return RiskLevel.LOW
    if score < 50:
        return RiskLevel.MEDIUM
    if score < 70:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def assess_release_risk(inp: RiskInputs) -> ReleaseRisk:
    components = score_components(inp)
    score = round(min(100.0, sum(components.values())), 1)
    level = level_for(score)
    blockers: list[str] = []
    reasons: list[str] = []

    if inp.unresolved_critical_ambiguities:
        blockers.append(f"{inp.unresolved_critical_ambiguities} unresolved CRITICAL requirement ambiguity")
    if inp.critical_tests_failed:
        blockers.append(f"{inp.critical_tests_failed} critical test(s) failed")
    if inp.security_findings.get("CRITICAL", 0):
        blockers.append("CRITICAL security finding open")
    if level is RiskLevel.CRITICAL:
        blockers.append(f"risk score {score} is CRITICAL")

    if inp.tests_failed:
        reasons.append(f"{inp.tests_failed}/{inp.tests_total} generated tests failed")
    if inp.unexpected_changes:
        reasons.append(f"{inp.unexpected_changes} unexpected claim outcome changes in simulation")
    if inp.governance_fail:
        reasons.append(f"{inp.governance_fail} governance checks failed")
    if inp.policy_evidence_missing:
        reasons.append("insufficient policy evidence for the requirement")

    if blockers:
        decision = ReleaseDecision.BLOCKED
    elif reasons:
        decision = ReleaseDecision.NOT_READY
    elif level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
        decision = ReleaseDecision.READY_WITH_APPROVAL
        reasons.append(f"risk level {level.value}: additional sign-off required")
    else:
        decision = ReleaseDecision.READY
        reasons.append("all deterministic gates passed")

    approvals = ["Release Manager"]  # every rule release needs a human approval (O-08.1)
    if decision is ReleaseDecision.READY_WITH_APPROVAL:
        approvals += ["Claims Operations Manager", "Compliance Reviewer"]
    return ReleaseRisk(score=score, level=level, decision=decision, component_scores=components,
                       blockers=blockers, reasons=reasons, required_approvals=approvals)
