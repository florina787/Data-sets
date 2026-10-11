"""Case states and legal transitions, enforced in the backend.

Transitions are applied with optimistic concurrency (Case.version) so two
investigators cannot both move a case from the same state.
"""
from __future__ import annotations

from enum import Enum

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models.orm import Case


class CaseStatus(str, Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    ASSESSING = "ASSESSING"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    MONITORING = "MONITORING"
    ESCALATED = "ESCALATED"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


S = CaseStatus

# from-state -> {to-state: prerequisite description}
TRANSITIONS: dict[CaseStatus, dict[CaseStatus, str]] = {
    S.NEW: {S.TRIAGED: "triage output validated", S.CANCELLED: "cancel request",
            S.FAILED: "workflow error"},
    S.TRIAGED: {S.COLLECTING_EVIDENCE: "scope check passed", S.NEEDS_INFORMATION: "triage cannot proceed",
                S.FAILED: "workflow error", S.CANCELLED: "cancel request"},
    S.COLLECTING_EVIDENCE: {S.ASSESSING: "evidence bundle persisted",
                            S.NEEDS_INFORMATION: "required evidence missing after iteration limit",
                            S.ESCALATED: "budget exhausted", S.FAILED: "workflow error"},
    S.ASSESSING: {S.COLLECTING_EVIDENCE: "specific missing signal identified",
                  S.RECOMMENDATION_READY: "hypotheses validated and action selected",
                  S.NEEDS_INFORMATION: "insufficient evidence",
                  S.ESCALATED: "contradictory evidence or budget exhausted",
                  S.FAILED: "workflow error"},
    S.RECOMMENDATION_READY: {S.AWAITING_APPROVAL: "approval record created",
                             S.ESCALATED: "recommended escalation", S.CANCELLED: "cancel request",
                             S.COLLECTING_EVIDENCE: "re-investigation requested"},
    S.AWAITING_APPROVAL: {S.APPROVED: "authorised approval recorded", S.REJECTED: "approver rejected",
                          S.RECOMMENDATION_READY: "approval expired or superseded",
                          S.CANCELLED: "cancel request"},
    S.APPROVED: {S.EXECUTING: "approval and policy revalidated",
                 S.RECOMMENDATION_READY: "approval expired or invalidated",
                 S.CANCELLED: "cancel request"},
    S.EXECUTING: {S.VERIFYING: "execution succeeded or reconciled",
                  S.FAILED: "execution failed", S.APPROVED: "execution outcome unknown; retry after reconcile"},
    S.VERIFYING: {S.RESOLVED: "fresh healthy samples across window",
                  S.MONITORING: "recovery not yet verified",
                  S.ESCALATED: "recovery failed"},
    S.MONITORING: {S.VERIFYING: "re-verification", S.ESCALATED: "monitoring escalated",
                   S.COLLECTING_EVIDENCE: "new complaint", S.CANCELLED: "cancel request"},
    S.NEEDS_INFORMATION: {S.TRIAGED: "clarification received", S.CANCELLED: "cancel request",
                          S.ESCALATED: "manual escalation"},
    S.ESCALATED: {S.COLLECTING_EVIDENCE: "analyst re-opens investigation"},
    S.REJECTED: {S.COLLECTING_EVIDENCE: "re-investigation requested", S.CANCELLED: "cancel request"},
    S.FAILED: {S.COLLECTING_EVIDENCE: "retry investigation", S.CANCELLED: "cancel request"},
    S.RESOLVED: {S.COLLECTING_EVIDENCE: "new complaint on resolved case"},
    S.CANCELLED: {},
}

TERMINAL_OR_WAITING = {S.RESOLVED, S.MONITORING, S.ESCALATED, S.NEEDS_INFORMATION,
                       S.REJECTED, S.CANCELLED, S.FAILED, S.AWAITING_APPROVAL,
                       S.RECOMMENDATION_READY, S.APPROVED}


class IllegalTransition(Exception):
    def __init__(self, current: str, target: str):
        super().__init__(f"Illegal transition {current} -> {target}")
        self.current = current
        self.target = target


class ConcurrentModification(Exception):
    pass


def can_transition(current: str, target: str) -> bool:
    return CaseStatus(target) in TRANSITIONS.get(CaseStatus(current), {})


def transition(db: Session, case: Case, target: CaseStatus, reason: str = "") -> str:
    """Atomically move a case to `target`. Returns the previous status.

    Uses a compare-and-set on (status, version) so concurrent writers fail
    with ConcurrentModification instead of silently overwriting.
    """
    current = case.status
    if not can_transition(current, target.value):
        raise IllegalTransition(current, target.value)
    now = utcnow()
    result = db.execute(
        update(Case)
        .where(Case.id == case.id, Case.version == case.version, Case.status == current)
        .values(status=target.value, version=case.version + 1, updated_at=now,
                status_reason=reason)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise ConcurrentModification(f"Case {case.id} changed concurrently")
    case.status = target.value
    case.version += 1
    case.updated_at = now
    case.status_reason = reason
    return current
