"""Human Approval Agent (17) persistence and authorization."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.database.session import ROLE_PERMISSIONS, session_scope
from app.governance import audit
from app.harness.core import new_id
from app.models import db as m

# action_type -> permission required to decide (None = only the subject patient may decide)
DECISION_PERMISSION: dict[str, str | None] = {
    "BOOKING_SUBMISSION": None,
    "APPOINTMENT_CANCELLATION": None,
    "PATIENT_DATA_SHARING": None,
    "EXTERNAL_NOTIFICATION": None,
    "SEARCH_RADIUS_EXPANSION": None,
    "REQUIREMENT_CLARIFICATION": "approval:engineering",
    "CODE_CHANGE": "approval:engineering",
    "PRODUCTION_DEPLOYMENT": "approval:release",
    "SECURITY_POLICY_CHANGE": "governance:write",
    "SENSITIVE_DATA_EXPORT": "governance:write",
}


class ApprovalError(Exception):
    pass


def create(action_type: str, requesting_agent: str, reason: str, evidence: list, consequences: list,
           payload: dict | None = None, workflow_id: str | None = None, workflow_type: str = "patient",
           subject_user_id: str | None = None) -> dict:
    if action_type not in DECISION_PERMISSION:
        raise ApprovalError(f"unknown action type {action_type}")
    aid = new_id("APR")
    perm = DECISION_PERMISSION[action_type]
    with session_scope() as s:
        s.add(m.ApprovalRequest(id=aid, action_type=action_type, workflow_id=workflow_id, workflow_type=workflow_type,
                                requesting_agent=requesting_agent, required_role=perm or "subject_patient",
                                subject_user_id=subject_user_id, reason=reason, evidence=evidence,
                                consequences=consequences, payload=payload or {}, status="PENDING"))
    audit.record("APPROVAL_REQUESTED", requesting_agent, {"approval_id": aid, "action": action_type}, workflow_id)
    return get(aid)


def _row(r: m.ApprovalRequest) -> dict:
    return {"id": r.id, "action_type": r.action_type, "workflow_id": r.workflow_id, "workflow_type": r.workflow_type,
            "requesting_agent": r.requesting_agent, "required_role": r.required_role,
            "subject_user_id": r.subject_user_id, "reason": r.reason, "evidence": r.evidence,
            "consequences": r.consequences, "payload": r.payload, "status": r.status, "decided_by": r.decided_by,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None, "decision_note": r.decision_note,
            "created_at": r.created_at.isoformat()}


def get(aid: str) -> dict:
    with session_scope() as s:
        r = s.get(m.ApprovalRequest, aid)
        if r is None:
            raise ApprovalError("approval not found")
        return _row(r)


def list_for(user_id: str, role: str, status: str | None = "PENDING", limit: int = 50) -> list[dict]:
    perms = ROLE_PERMISSIONS.get(role, set())
    with session_scope() as s:
        q = select(m.ApprovalRequest).order_by(m.ApprovalRequest.created_at.desc())
        if status:
            q = q.where(m.ApprovalRequest.status == status)
        rows = s.scalars(q.limit(500)).all()
        out = []
        for r in rows:
            need = DECISION_PERMISSION.get(r.action_type)
            visible = (need is None and r.subject_user_id == user_id) or (need is not None and need in perms) \
                or "admin:all" in perms and need is not None
            if visible:
                out.append(_row(r))
        return out[:limit]


def can_decide(approval: dict, user_id: str, role: str) -> tuple[bool, str]:
    need = DECISION_PERMISSION.get(approval["action_type"])
    perms = ROLE_PERMISSIONS.get(role, set())
    if need is None:
        return (approval["subject_user_id"] == user_id, "only the patient this request concerns may decide")
    if need not in perms:
        return False, f"requires permission {need}"
    if approval["payload"].get("requested_by") == user_id:
        return False, "separation of duties: requester cannot approve their own request"
    return True, ""


def decide(aid: str, decision: str, user_id: str, role: str, note: str | None = None) -> dict:
    if decision not in {"APPROVED", "REJECTED"}:
        raise ApprovalError("decision must be APPROVED or REJECTED")
    a = get(aid)
    if a["status"] != "PENDING":
        raise ApprovalError(f"approval already {a['status']}")
    ok, why = can_decide(a, user_id, role)
    if not ok:
        audit.record("APPROVAL_DENIED", user_id, {"approval_id": aid, "why": why}, a["workflow_id"], "WARNING")
        raise PermissionError(why)
    with session_scope() as s:
        r = s.get(m.ApprovalRequest, aid)
        assert r is not None
        r.status, r.decided_by, r.decided_at, r.decision_note = decision, user_id, datetime.now(UTC), note
    audit.record("APPROVAL_DECIDED", user_id, {"approval_id": aid, "decision": decision,
                                               "action": a["action_type"]}, a["workflow_id"])
    return get(aid)
