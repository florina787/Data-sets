"""Security / privacy agent (advisory)."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.security.review import security_review


class SecurityAgent(BaseAgent):
    name = "security"
    title = "Security / Privacy Agent"
    implementation = "DETERMINISTIC rule-based advisory review"

    def run(self, state: dict) -> dict:
        res = security_review(state["requirement"], state["impact"]["impacts"], self.ctx.settings,
                              bool(state.get("request_screen", {}).get("flagged")))
        return {"security": res}
