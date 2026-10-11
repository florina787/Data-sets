"""Change lifecycle. The permitted transition table is the single source of truth; prerequisite
checks live in the services that request each transition and are re-checked here by name."""
from __future__ import annotations

from enum import Enum

from app.errors import PolicyViolation


class S(str, Enum):
    DRAFT = "DRAFT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REQUIREMENTS_APPROVED = "REQUIREMENTS_APPROVED"
    IMPACT_REVIEW = "IMPACT_REVIEW"
    DEVELOPMENT = "DEVELOPMENT"
    EVALUATING = "EVALUATING"
    EVALUATION_FAILED = "EVALUATION_FAILED"
    EVALUATION_INCONCLUSIVE = "EVALUATION_INCONCLUSIVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    RELEASE_APPROVED = "RELEASE_APPROVED"
    CANARY = "CANARY"
    MONITORING = "MONITORING"
    RELEASED = "RELEASED"
    ROLLBACK_RECOMMENDED = "ROLLBACK_RECOMMENDED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


TERMINAL = {S.ROLLED_BACK, S.CANCELLED, S.FAILED}

# (from, to) -> human-readable backend prerequisite
TRANSITIONS: dict[tuple[S, S], str] = {
    (S.DRAFT, S.NEEDS_CLARIFICATION): "Requirements agent found unresolved ambiguities",
    (S.DRAFT, S.REQUIREMENTS_APPROVED): "No ambiguities and product owner approved the requirement version",
    (S.NEEDS_CLARIFICATION, S.NEEDS_CLARIFICATION): "Clarification answered; others remain",
    (S.NEEDS_CLARIFICATION, S.REQUIREMENTS_APPROVED): "All required clarifications answered and product owner approved the new requirement version",
    (S.REQUIREMENTS_APPROVED, S.NEEDS_CLARIFICATION): "Requirement re-opened",
    (S.REQUIREMENTS_APPROVED, S.IMPACT_REVIEW): "Evidence and impact agents completed with resolvable citations",
    (S.IMPACT_REVIEW, S.DEVELOPMENT): "Impact assessment accepted by an authorized owner",
    (S.DEVELOPMENT, S.EVALUATING): "Candidate registered with digest-verified artifact and code revision; evaluation config present",
    (S.EVALUATING, S.EVALUATION_FAILED): "Computed gates: at least one FAIL",
    (S.EVALUATING, S.EVALUATION_INCONCLUSIVE): "Computed gates: no FAIL but at least one INCONCLUSIVE",
    (S.EVALUATING, S.REVIEW_REQUIRED): "Computed gates: all PASS",
    (S.EVALUATING, S.DEVELOPMENT): "Evaluation job failed or was cancelled (computation, not policy)",
    (S.EVALUATION_FAILED, S.DEVELOPMENT): "New candidate registered",
    (S.EVALUATION_INCONCLUSIVE, S.DEVELOPMENT): "New candidate or configuration registered",
    (S.EVALUATION_FAILED, S.EVALUATING): "Re-evaluation requested after new candidate",
    (S.EVALUATION_INCONCLUSIVE, S.EVALUATING): "Re-evaluation requested",
    (S.REVIEW_REQUIRED, S.DEVELOPMENT): "Review rejected or new candidate registered",
    (S.REVIEW_REQUIRED, S.EVALUATING): "Re-evaluation requested (prior approvals invalidated)",
    (S.REVIEW_REQUIRED, S.RELEASE_APPROVED): "Required reviews approved; distinct release approver approved bound artifacts",
    (S.RELEASE_APPROVED, S.REVIEW_REQUIRED): "Approval invalidated, expired or rejected",
    (S.RELEASE_APPROVED, S.CANARY): "Approval revalidated immediately before simulated deployment",
    (S.CANARY, S.MONITORING): "Canary window observed with no open alert",
    (S.MONITORING, S.RELEASED): "All rollout stages completed with no open alert",
    (S.CANARY, S.ROLLBACK_RECOMMENDED): "Alert investigated; monitoring agent proposed rollback",
    (S.MONITORING, S.ROLLBACK_RECOMMENDED): "Alert investigated; monitoring agent proposed rollback",
    (S.RELEASED, S.ROLLBACK_RECOMMENDED): "Alert investigated; monitoring agent proposed rollback",
    (S.ROLLBACK_RECOMMENDED, S.ROLLED_BACK): "Authorized rollback approval and compatibility check passed",
    (S.ROLLBACK_RECOMMENDED, S.MONITORING): "Rollback rejected by authorized reviewer; monitoring continues",
}
for _s in S:
    if _s not in TERMINAL and _s not in {S.RELEASED}:
        TRANSITIONS.setdefault((_s, S.CANCELLED), "Cancelled by an authorized user")
        TRANSITIONS.setdefault((_s, S.FAILED), "Unrecoverable workflow error")


def can_transition(src: str, dst: str) -> bool:
    return (S(src), S(dst)) in TRANSITIONS


def assert_transition(src: str, dst: str) -> str:
    try:
        key = (S(src), S(dst))
    except ValueError as exc:
        raise PolicyViolation("unknown_state", str(exc)) from exc
    if key not in TRANSITIONS:
        raise PolicyViolation("illegal_transition", f"Transition {src} -> {dst} is not permitted.",
                              {"from": src, "to": dst, "allowed": allowed_from(src)})
    return TRANSITIONS[key]


def allowed_from(src: str) -> list[str]:
    return sorted({b.value for (a, b) in TRANSITIONS if a.value == src})


def transition_table() -> list[dict]:
    return [{"from": a.value, "to": b.value, "prerequisite": p} for (a, b), p in TRANSITIONS.items()]
