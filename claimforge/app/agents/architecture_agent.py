"""Architecture agent: KEEP / ENHANCE / ADD / REPLACE recommendations with guardrails."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.architecture.analyzer import recommend


class ArchitectureAgent(BaseAgent):
    name = "architecture"
    title = "Architecture Agent"
    implementation = "DETERMINISTIC template + guardrail (never replaces deterministic engines with LLMs)"

    def run(self, state: dict) -> dict:
        result = recommend(state["impact"]["impacts"])
        counts: dict[str, int] = {}
        for r in result["recommendations"]:
            counts[r["action"]] = counts.get(r["action"], 0) + 1
        result["counts"] = counts
        result["human_review_required"] = counts.get("REPLACE", 0) > 0 or counts.get("ADD", 0) > 0
        fallback = ("Preserve the deterministic claims platform; " +
                    ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) +
                    ". ClaimForge is additive; architecture changes require human review.")
        result["narrative"] = self.narrate("Explain the architecture recommendation", str(result["recommendations"]), fallback)
        return {"architecture": result}
