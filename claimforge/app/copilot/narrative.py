"""Copilot response composition: one product voice, persona-specific emphasis.

The facts are deterministic; persona only changes ordering/emphasis. In live AI mode the
summary may be rephrased by the LLM (labelled LLM-ASSISTED); numbers never change.
"""

from __future__ import annotations

from app.llm.client import LLMClient

PERSONA_FOCUS = {
    "Business Analyst": ["requirement", "ambiguity", "policy", "tests"],
    "Product Owner": ["requirement", "financial", "release", "ambiguity"],
    "Insurance Product Manager": ["financial", "policy", "simulation", "release"],
    "Solution Architect": ["impact", "architecture", "security", "release"],
    "Developer": ["development", "impact", "tests", "rootcause"],
    "QA Engineer": ["tests", "simulation", "regression", "rootcause"],
    "Claims Analyst": ["simulation", "claimiq", "rootcause", "policy"],
    "Operations Engineer": ["claimiq", "rootcause", "remediation", "release"],
    "Release Manager": ["release", "tests", "governance", "claimiq"],
    "Compliance Reviewer": ["governance", "policy", "security", "traceability"],
    "Engineering Manager": ["release", "impact", "financial", "remediation"],
}


def _facts(s: dict) -> dict[str, str]:
    f: dict[str, str] = {}
    req = s.get("requirement")
    if req is not None:
        f["requirement"] = f"Requirement {req.requirement_id}: {req.title} ({len(req.acceptance_criteria)} acceptance criteria)."
        blocking = req.blocking_ambiguities
        f["ambiguity"] = (f"⚠ {len(blocking)} critical ambiguity needs human clarification: {blocking[0].question}"
                          if blocking else f"Ambiguities: {len(req.ambiguities)} (none blocking).")
    if s.get("policy"):
        p = s["policy"]
        f["policy"] = (f"Policy evidence: {', '.join(e['citation'] for e in p.get('evidence', [])[:3])}."
                       if p.get("evidence") else "INSUFFICIENT POLICY EVIDENCE.")
    if s.get("impact"):
        sm = s["impact"]["summary"]
        f["impact"] = (f"Impact: {sm['microservices_affected']} microservices, {sm['apis_affected']} APIs, "
                       f"{sm['business_rules_affected']} business rules, {sm['database_tables_affected']} tables.")
    if s.get("architecture"):
        f["architecture"] = "Architecture: " + s["architecture"]["narrative"]["text"]
    if s.get("development_plan"):
        f["development"] = f"Development plan: {len(s['development_plan']['steps'])} steps (proposal only)."
    if s.get("tests"):
        t = s["tests"]["summary"]
        f["tests"] = f"Tests: {t['passed']}/{t['total']} generated tests pass against {s['tests']['ruleset']}."
    sim = s.get("simulation")
    if sim is not None:
        f["simulation"] = (f"Simulation: {sim.claims_simulated:,} synthetic claims, {sim.outcomes_changed:,} outcomes changed, "
                           f"{sim.unexpected_changes} unexpected.")
        f["financial"] = (f"Financial: ${sim.financial.difference:,.0f} simulated difference; projected annual "
                          f"${sim.financial.projected_annual_impact:,.0f} ({sim.financial.disclaimer})")
    if s.get("security"):
        f["security"] = f"Security (advisory): {s['security']['severity_counts'] or 'no findings'}."
    if s.get("governance"):
        g = s["governance"]
        f["governance"] = f"Governance: {g['pass']} pass / {g['warn']} warn / {g['fail']} fail."
    rr = s.get("release_risk")
    if rr is not None:
        f["release"] = f"Release risk {rr.score} ({rr.level.value}) → {rr.decision.value}; approvals: {', '.join(rr.required_approvals)}."
    if s.get("production"):
        k = s["production"]["kpis"]
        f["claimiq"] = (f"ClaimIQ (SIMULATED): {k['claims']:,} claims since release {k['current_release']}, "
                        f"denial rate {k['denial_rate']:.1%}.")
        a = s.get("anomaly", {}).get("primary")
        if a:
            f["claimiq"] += f" ANOMALY: {a.summary}"
    rc = s.get("root_cause")
    if rc is not None:
        f["rootcause"] = f"Root cause ({rc.confidence}): {(rc.likely_defect or rc.status).rstrip('.')}."
    if s.get("remediation") is not None:
        f["remediation"] = f"Remediation (needs human approval): {s['remediation'].recommended_change}"
    if s.get("regression"):
        f["regression"] = f"Regression test {s['regression']['test'].test_id}: passes on fix, fails on deployed build."
    if s.get("defect") is not None:
        f["traceability"] = f"Defect {s['defect'].key} traced to {s['defect'].source_requirement} / {s['defect'].rule_id}."
    return f


def persona_summary(state: dict, persona: str, llm: LLMClient) -> dict:
    facts = _facts(state)
    focus = PERSONA_FOCUS.get(persona, [])
    ordered = [facts[k] for k in focus if k in facts] + [v for k, v in facts.items() if k not in focus]
    status = state.get("status", "")
    headline = {
        "NEEDS_CLARIFICATION": "Human clarification required before analysis can continue.",
        "AWAITING_APPROVAL": "Release assessed — awaiting human approval.",
        "CLOSED_LOOP_COMPLETE": "Closed loop complete: production finding fed back into the SDLC.",
        "HEALTHY": "Release healthy — no anomaly detected.",
        "HALTED": f"Workflow halted: {state.get('halted_reason')}",
        "FAILED": "Workflow failed — see errors.",
    }.get(status, f"Status: {status}")
    text = headline + "\n\n" + "\n".join(f"- {line}" for line in ordered)
    res = llm.narrate(f"Rewrite this ClaimForge summary for a {persona}", text, text)
    return {"persona": persona, "headline": headline, "points": ordered, "text": res.text, "source": res.source}
