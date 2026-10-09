"""Release agent: deterministic risk score + READY / READY WITH APPROVAL / NOT READY / BLOCKED."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.domain import Severity
from app.release.risk import RiskInputs, assess_release_risk


class ReleaseAgent(BaseAgent):
    name = "release"
    title = "Release Agent"
    implementation = "DETERMINISTIC weighted risk engine + explicit blocking rules"

    def run(self, state: dict) -> dict:
        req = state["requirement"]
        impact = state["impact"]["summary"]
        tests = state["tests"]["summary"]
        sim = state.get("simulation")
        sec = state.get("security", {}).get("severity_counts", {})
        gov = state.get("governance", {})
        unresolved_other = sum(1 for a in req.ambiguities if a.resolution is None and not a.blocking)
        inputs = RiskInputs(
            components_affected=impact["components_changed"],
            critical_components=impact["critical_components_changed"],
            rule_changes=len(req.business_rules),
            tests_total=tests["total"], tests_failed=tests["failed"], critical_tests_failed=tests["critical_failed"],
            claims_simulated=sim.claims_simulated if sim else 0,
            unexpected_changes=sim.unexpected_changes if sim else 0,
            unresolved_critical_ambiguities=len(req.blocking_ambiguities),
            unresolved_other_ambiguities=unresolved_other,
            annual_financial_impact=sim.financial.projected_annual_impact if sim else 0.0,
            security_findings=sec, governance_fail=gov.get("fail", 0), governance_warn=gov.get("warn", 0),
            policy_evidence_missing=state.get("policy", {}).get("status") != "EVIDENCE_FOUND",
        )
        risk = assess_release_risk(inputs)
        evidence = [
            f"tests: {tests['passed']}/{tests['total']} passed",
            f"simulation: {sim.claims_simulated:,} claims, {sim.outcomes_changed:,} changed, {sim.unexpected_changes} unexpected" if sim else "simulation: not run",
            f"security findings: {sec or 'none'}",
            f"governance: {gov.get('pass', 0)} pass / {gov.get('warn', 0)} warn / {gov.get('fail', 0)} fail",
        ]
        notes = self._release_notes(req, sim)
        return {"release_risk": risk,
                "release_assessment": {"decision": risk.decision.value, "evidence": evidence, "inputs": inputs.__dict__,
                                       "release_notes": notes, "rollback_plan": self._rollback(req),
                                       "severity_scale": [s.value for s in Severity]}}

    @staticmethod
    def _release_notes(req, sim) -> str:
        lines = [f"Release 2.4 (SIMULATED) — {req.requirement_id}: {req.title}"]
        for r in req.business_rules:
            lines.append(f"- {r.rule_id} {r.change}: {r.description}")
        if sim:
            lines.append(f"- Simulated on {sim.claims_simulated:,} synthetic claims; projected annual impact "
                         f"${sim.financial.projected_annual_impact:,.0f} ({sim.financial.disclaimer})")
        return "\n".join(lines)

    @staticmethod
    def _rollback(req) -> list[str]:
        return [
            "Rules are effective-dated: rollback = re-activate RULESET_V1 rows via feature flag (no schema rollback).",
            "Claims adjudicated under the new ruleset are listed by ruleset_id for targeted reprocessing (approval O-05.2).",
            "Rollback reverts the member-favourable maximum increase too — prefer forward-fix for isolated defects.",
            f"Owner: Release Manager; trigger: ClaimIQ anomaly on {req.benefit_type.value if req.benefit_type else 'benefit'} denial metrics.",
        ]
