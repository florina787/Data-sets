"""Impact analysis agent: requirement → component impact map."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.impact.analyzer import analyze_impact, impact_tree
from app.models.domain import ImpactAction


class ImpactAgent(BaseAgent):
    name = "impact"
    title = "Impact Analysis Agent"
    implementation = "DETERMINISTIC facet matching + dependency propagation over architecture catalog"

    def run(self, state: dict) -> dict:
        req = state["requirement"]
        result = analyze_impact(req)
        result["tree"] = impact_tree(req.requirement_id, result["impacts"])
        g = self.ctx.trace_graph
        for imp in result["impacts"]:
            if imp.action is ImpactAction.KEEP:
                continue
            if imp.component_id not in g.nodes:
                g.add_node(imp.component_id, "component", imp.component_name)
        s = result["summary"]
        fallback = (f"{s['components_changed']} components change: {s['microservices_affected']} microservices, "
                    f"{s['apis_affected']} APIs, {s['database_tables_affected']} tables, "
                    f"{s['business_rules_affected']} business rules, {s['tests_affected']} test suites.")
        result["narrative"] = self.narrate("Explain the impact map", result["tree"], fallback)
        return {"impact": result}
