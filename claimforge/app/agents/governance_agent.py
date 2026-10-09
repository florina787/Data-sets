"""Compliance / governance agent: evidence-based governance checklist."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.governance.checklist import governance_checklist


class GovernanceAgent(BaseAgent):
    name = "governance"
    title = "Compliance / Governance Agent"
    implementation = "DETERMINISTIC evidence checklist"

    def run(self, state: dict) -> dict:
        req = state["requirement"]
        links = sum(1 for e in self.ctx.trace_graph.edges if e.source_id == req.requirement_id
                    or e.source_type in ("policy_section", "business_rule", "component", "implementation", "test"))
        res = governance_checklist(requirement=req, policy_result=state.get("policy", {}),
                                   simulation=state.get("simulation"), test_summary=state.get("tests", {}).get("summary", {}),
                                   approval=state.get("approval"), live_ai=self.ctx.settings.live_ai_enabled,
                                   trace_links=links)
        return {"governance": res}
