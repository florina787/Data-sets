"""QA agent: generates boundary/negative/regression/API tests and executes them."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.qa.test_generator import generate_test_cases, run_test_cases, summarize
from app.requirements.analyzer import ruleset_from_requirement


class QAAgent(BaseAgent):
    name = "qa"
    title = "QA Agent"
    implementation = "DETERMINISTIC test generation + execution against the rules engine"

    def run(self, state: dict) -> dict:
        req = state["requirement"]
        cases = generate_test_cases(req)
        proposed = ruleset_from_requirement(req)
        results = run_test_cases(cases, proposed)
        summary = summarize(results)
        g = self.ctx.trace_graph
        for tc in cases:
            if tc.rule_id in ("AUTH_RULE_184", "BEN_RULE_090") and tc.critical:
                if tc.test_id not in g.nodes:
                    g.add_node(tc.test_id, "test", tc.title)
                g.link(tc.rule_id, tc.test_id, "verified_by")
                if "REL-2.4" in g.nodes and req.requirement_id == "BR-391":
                    g.link(tc.test_id, "REL-2.4", "gates")
        by_cat: dict[str, int] = {}
        for tc in cases:
            by_cat[tc.category] = by_cat.get(tc.category, 0) + 1
        return {"tests": {"cases": cases, "results": results, "summary": summary, "by_category": by_cat,
                          "ruleset": proposed.ruleset_id,
                          "boundary_cases": [tc.test_id for tc in cases if tc.category == "boundary"],
                          "method": self.implementation}}
