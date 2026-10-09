"""Deterministic policy evaluation and authorization for actions.

LLM output never reaches this module as authority: it receives facts derived
from validated evidence and returns a decision. Model text cannot grant
permissions, approve actions or override these rules.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from .catalog import ActionSpec, load_catalog


@dataclass
class PolicyDecision:
    action_type: str
    policy_version: str
    allowed: bool
    executable: bool
    mvp_behavior: str
    requires_approval: bool
    approver_roles: list[str]
    executor_roles: list[str]
    separation_of_duties: bool
    risk: str
    unmet_requirements: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def evaluate(action_type: str, facts: set[str]) -> PolicyDecision:
    """Evaluate an action against the catalog using evidence-derived facts.

    `facts` are flags such as "fresh_diagnostics" or "active_mapped_incident",
    computed deterministically from the evidence bundle.
    """
    catalog = load_catalog()
    spec: ActionSpec | None = catalog.actions.get(action_type)
    if spec is None:
        return PolicyDecision(action_type, catalog.version, False, False, "unknown", True, [], [],
                              True, "unknown", violations=["action not in catalog"],
                              reasons=["Unknown actions are refused."])
    unmet = [r for r in spec.evidence_requirements if r not in facts]
    violations = [f for f in spec.forbidden_when if f in facts]
    reasons: list[str] = []
    if spec.mvp_behavior == "disabled":
        reasons.append(f"{spec.label} is disabled in this prototype.")
    elif spec.mvp_behavior == "proposal_only":
        reasons.append(f"{spec.label} can be proposed but not executed until a connector "
                       "and action authorization are supplied.")
    if unmet:
        reasons.append("Unmet evidence requirements: " + ", ".join(unmet))
    if violations:
        reasons.append("Forbidden because: " + ", ".join(violations))
    allowed = spec.mvp_behavior != "disabled" and not unmet and not violations
    return PolicyDecision(
        action_type=action_type,
        policy_version=catalog.version,
        allowed=allowed,
        executable=allowed and spec.mvp_behavior == "executable",
        mvp_behavior=spec.mvp_behavior,
        requires_approval=spec.classification == "write",
        approver_roles=list(spec.approver_roles),
        executor_roles=list(spec.executor_roles),
        separation_of_duties=spec.separation_of_duties,
        risk=spec.risk,
        unmet_requirements=unmet,
        violations=violations,
        reasons=reasons or ["All catalog requirements met."],
    )


def can_approve(role: str, user_id: str, proposer_id: str, decision: PolicyDecision) -> tuple[bool, str]:
    if role not in decision.approver_roles:
        return False, f"Role '{role}' may not approve {decision.action_type}"
    if decision.separation_of_duties and user_id == proposer_id:
        return False, "Separation of duties: the proposer cannot approve this action"
    return True, "ok"


def can_execute(role: str, decision: PolicyDecision) -> tuple[bool, str]:
    if not decision.executable:
        return False, f"{decision.action_type} is not executable ({decision.mvp_behavior})"
    if role not in decision.executor_roles:
        return False, f"Role '{role}' may not execute {decision.action_type}"
    return True, "ok"
