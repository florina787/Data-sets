"""Human-in-the-loop approvals.

Consequential actions are *never* executed by an agent. An agent (or the UI) can only create a
pending ``ApprovalRequest``; the action runs only after the authenticated user approves it through
``POST /api/approvals/{id}/decision`` — an endpoint no agent or MCP tool can call. Execution
re-checks ownership and status inside the same transaction.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Application, ApplicationEvent, ApprovalRequest, Recruiter, RecruiterInteraction, Resume, utcnow
from .audit import audit

CONSEQUENTIAL_ACTIONS = {
    "submit_application": "Mark an application as submitted to the employer",
    "send_recruiter_email": "Send an email to a recruiter",
    "share_resume": "Share a resume with an external party",
    "external_account_action": "Act on an external account",
    "delete_data": "Permanently delete important user data",
}


def request_approval(db: Session, user_id: uuid.UUID, action: str, summary: str, payload: dict[str, Any],
                     requested_by: str) -> ApprovalRequest:
    if action not in CONSEQUENTIAL_ACTIONS:
        raise HTTPException(400, f"Unknown approval action '{action}'")
    req = ApprovalRequest(user_id=user_id, action=action, summary=summary[:1000], payload=payload, requested_by=requested_by[:60])
    db.add(req)
    db.commit()
    audit(db, user_id, f"agent:{requested_by}" if requested_by != "user" else "user", "approval.requested", str(req.id), {"action": action})
    return req


def decide(db: Session, user_id: uuid.UUID, request_id: uuid.UUID, approve: bool) -> ApprovalRequest:
    req = db.get(ApprovalRequest, request_id)
    if req is None or req.user_id != user_id:
        raise HTTPException(404, "Approval request not found")
    new = "approved" if approve else "rejected"
    res = db.execute(update(ApprovalRequest).where(ApprovalRequest.id == request_id, ApprovalRequest.status == "pending")
                     .values(status=new, decided_at=utcnow()))
    db.commit()
    if res.rowcount != 1:
        raise HTTPException(409, f"Request already {req.status}")
    db.refresh(req)
    audit(db, user_id, "user", f"approval.{new}", str(req.id), {"action": req.action})
    if approve:
        execute(db, req)
    return req


def execute(db: Session, req: ApprovalRequest) -> None:
    claimed = db.execute(update(ApprovalRequest).where(ApprovalRequest.id == req.id, ApprovalRequest.status == "approved")
                         .values(status="executed", executed_at=utcnow()))
    db.commit()
    if claimed.rowcount != 1:
        return
    p = req.payload or {}
    result: dict[str, Any] = {}
    if req.action == "submit_application":
        app = db.get(Application, uuid.UUID(p["application_id"]))
        if app and app.user_id == req.user_id:
            app.status, app.applied_at = "applied", utcnow().date()
            db.add(ApplicationEvent(user_id=req.user_id, application_id=app.id, kind="status_change",
                                    detail={"to": "applied", "approval_id": str(req.id)}))
            result = {"application_id": str(app.id), "status": "applied",
                      "note": "Marked as submitted. Complete the employer's own application form at the posting URL."}
    elif req.action == "send_recruiter_email":
        rec = db.get(Recruiter, uuid.UUID(p["recruiter_id"]))
        if rec and rec.user_id == req.user_id:
            db.add(RecruiterInteraction(user_id=req.user_id, recruiter_id=rec.id, channel="email", direction="outbound",
                                        summary=p.get("body", "")[:2000]))
            # No outbound mail service is wired: the approved draft is handed to the user's mail client.
            result = {"mailto": f"mailto:{rec.email or ''}?subject={p.get('subject', '')}", "logged": True}
    elif req.action == "share_resume":
        res = db.get(Resume, uuid.UUID(p["resume_id"]))
        if res and res.user_id == req.user_id:
            result = {"share": "approved", "resume_id": str(res.id)}
    elif req.action == "delete_data":
        kind, target = p.get("kind"), p.get("id")
        model = {"resume": Resume, "application": Application, "recruiter": Recruiter}.get(kind)
        if model and target:
            row = db.get(model, uuid.UUID(target))
            if row is not None and row.user_id == req.user_id:
                db.delete(row)
                result = {"deleted": kind, "id": target}
    req.result = result
    db.commit()
    audit(db, req.user_id, "user", "approval.executed", str(req.id), {"action": req.action, "result": result})


def list_requests(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.user_id == user_id).order_by(ApprovalRequest.created_at.desc())
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    return list(db.scalars(stmt.limit(100)))
