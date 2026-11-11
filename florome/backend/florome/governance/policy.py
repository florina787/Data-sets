"""Governance Agent: policy-as-code evaluation for remediation plans.

Policy is a JSON document stored per tenant. Inputs are only facts about the action (catalog risk, environment,
reversibility, whether the action is covered by an automated test) and tenant state. Nothing a model writes is
an input, so a model cannot make an action autonomous by calling it safe.

Execution modes
  observe     read-only: plans can be drafted, nothing executes
  approval    every plan needs an approval from someone other than its creator (default)
  autonomous  a plan may run without approval only if *every* step matches the autonomous allow-list
              (action id + environment), is low risk, reversible and tested. Anything else falls back to approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_POLICY: dict[str, Any] = {
    "execution_mode": "approval",
    "autonomous_allowlist": [
        {"action_id": "create_ticket", "environments": ["dev", "staging", "prod"]},
        {"action_id": "refresh_cache", "environments": ["dev", "staging"]},
    ],
    "approval_ttl_minutes": 60,
    "require_separation_of_duties": True,
    "high_risk_requires_rollback": True,
    "max_actions_per_hour": 30,
    "blocked_actions": [],
    "allowed_environments": ["dev", "staging", "prod"],
}


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reasons: list[str] = field(default_factory=list)
    step_decisions: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "requires_approval": self.requires_approval, "reasons": self.reasons,
                "step_decisions": self.step_decisions}


def effective_policy(tenant_policy: dict[str, Any] | None) -> dict[str, Any]:
    return {**DEFAULT_POLICY, **(tenant_policy or {})}


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errs = []
    if policy.get("execution_mode") not in ("observe", "approval", "autonomous"):
        errs.append("execution_mode must be observe, approval or autonomous")
    if not isinstance(policy.get("approval_ttl_minutes"), int) or not 1 <= policy["approval_ttl_minutes"] <= 1440:
        errs.append("approval_ttl_minutes must be an integer 1..1440")
    if not isinstance(policy.get("max_actions_per_hour"), int) or policy["max_actions_per_hour"] < 0:
        errs.append("max_actions_per_hour must be a non-negative integer")
    if policy.get("require_separation_of_duties") is not True:
        errs.append("require_separation_of_duties cannot be disabled")
    return errs


def evaluate_plan(steps: list[dict[str, Any]], policy: dict[str, Any], *, emergency_stop: bool, tenant_mode: str,
                  actions_last_hour: int) -> PolicyDecision:
    reasons: list[str] = []
    allowed = True
    if emergency_stop:
        return PolicyDecision(False, True, ["Emergency stop is active for this tenant."])
    if policy["execution_mode"] == "observe":
        return PolicyDecision(False, True, ["Tenant is in observe mode: plans are advisory and cannot execute."])
    if actions_last_hour + len(steps) > policy["max_actions_per_hour"]:
        allowed = False
        reasons.append(f"Action budget exceeded: {actions_last_hour} executed in the last hour, limit {policy['max_actions_per_hour']}.")

    autonomous_ok = policy["execution_mode"] == "autonomous"
    step_decisions = []
    for s in steps:
        sd: dict[str, Any] = {"index": s["index"], "action_id": s["action_id"], "allowed": True, "autonomous_eligible": False, "reasons": []}
        if tenant_mode == "live" and s.get("simulated"):
            sd["allowed"] = False
            sd["reasons"].append("Simulated connector actions are not executable in live mode.")
        if s["action_id"] in policy["blocked_actions"]:
            sd["allowed"] = False
            sd["reasons"].append("Action is blocked by tenant policy.")
        if s["environment"] not in policy["allowed_environments"]:
            sd["allowed"] = False
            sd["reasons"].append(f"Environment '{s['environment']}' is not allowed.")
        if s["risk"] == "high" and policy["high_risk_requires_rollback"] and not (s.get("reversible") and s.get("rollback")):
            sd["allowed"] = False
            sd["reasons"].append("High-risk action without a documented rollback strategy.")
        entry = next((a for a in policy["autonomous_allowlist"] if a["action_id"] == s["action_id"]), None)
        eligible = bool(entry and s["environment"] in entry.get("environments", []) and s["risk"] == "low"
                        and s.get("reversible") and s.get("tested"))
        sd["autonomous_eligible"] = eligible
        if not eligible:
            autonomous_ok = False
        if not sd["allowed"]:
            allowed = False
        step_decisions.append(sd)

    requires_approval = not autonomous_ok
    if requires_approval:
        reasons.append("Human approval required: " + ("tenant policy is approval mode." if policy["execution_mode"] == "approval"
                                                       else "not every step is on the autonomous allow-list as a low-risk, reversible, tested action."))
    else:
        reasons.append("Every step is on the autonomous allow-list (low risk, reversible, tested).")
    for sd in step_decisions:
        reasons += [f"Step {sd['index']} ({sd['action_id']}): {r}" for r in sd["reasons"]]
    return PolicyDecision(allowed, requires_approval, reasons, step_decisions)
