"""BA / Requirement agent: natural language → structured requirement (+ ambiguity flags)."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.requirements.analyzer import analyze_requirement_text


class RequirementAgent(BaseAgent):
    name = "requirement"
    title = "BA / Requirement Agent"
    implementation = "DETERMINISTIC parser + rule templates; LLM-assisted narrative in live mode"

    def run(self, state: dict) -> dict:
        req = analyze_requirement_text(state["request_text"], state.get("clarifications") or {})
        blocking = [a.ambiguity_id for a in req.blocking_ambiguities]
        fallback = (f"{req.requirement_id}: {req.title}. Facets: {', '.join(req.facets) or 'none'}. "
                    f"{len(req.acceptance_criteria)} acceptance criteria, {len(req.business_rules)} business rules, "
                    f"{len(req.ambiguities)} ambiguities ({len(blocking)} blocking).")
        return {"requirement": req, "requirement_narrative": self.narrate("Summarize the structured requirement",
                                                                          req.raw_text, fallback)}
