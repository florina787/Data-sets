"""Supervisor agent: understands the request, selects the workflow, guards budgets.

Intent classification is DETERMINISTIC (keyword rules) so routing is reproducible and
cannot be hijacked by prompt injection. Request text is screened and treated as data.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.security.sanitizer import screen_text

WORKFLOWS = {
    "SDLC_CLOSED_LOOP": "Requirement → policy → impact → architecture → dev plan → tests → simulation → "
                        "security/governance → release → approval → simulated release → ClaimIQ → root cause → "
                        "remediation → regression → defect → SDLC feedback",
    "POLICY_QA": "Policy evidence retrieval only",
    "CLAIMIQ_INVESTIGATION": "Production monitoring → anomaly → root cause → remediation → defect → feedback",
}

_CLAIMIQ_WORDS = ("denial rate", "denials increased", "anomaly", "investigate", "production incident",
                  "spike", "claimiq", "root cause")
_POLICY_WORDS = ("what does the policy", "what does policy", "policy say", "is it covered", "find the policy",
                 "which section")


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    title = "Supervisor Agent"
    implementation = "DETERMINISTIC intent routing + budget enforcement"

    def classify(self, text: str) -> str:
        low = text.lower()
        if any(w in low for w in _CLAIMIQ_WORDS):
            return "CLAIMIQ_INVESTIGATION"
        if any(w in low for w in _POLICY_WORDS) and not any(w in low for w in ("increase", "require", "change")):
            return "POLICY_QA"
        return "SDLC_CLOSED_LOOP"

    def run(self, state: dict) -> dict:
        text = state.get("request_text", "")
        screen = screen_text(text)
        workflow = state.get("workflow") or self.classify(text)
        if workflow not in WORKFLOWS:
            workflow = "SDLC_CLOSED_LOOP"
        return {
            "workflow": workflow,
            "request_screen": {"flagged": screen.flagged, "matches": screen.matches,
                               "handling": "treated as data; no routing or permission change" if screen.flagged else "clean"},
            "supervisor": {"workflow": workflow, "description": WORKFLOWS[workflow],
                           "limits": {"max_agent_iterations": self.ctx.settings.max_agent_iterations,
                                      "max_tool_calls": self.ctx.settings.max_tool_calls,
                                      "max_workflow_steps": self.ctx.settings.max_workflow_steps,
                                      "agent_timeout_seconds": self.ctx.settings.agent_timeout_seconds}},
        }
