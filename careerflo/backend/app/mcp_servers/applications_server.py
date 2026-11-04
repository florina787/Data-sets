"""MCP Server C — Application Tracking. Submitting an application always needs human approval."""
from __future__ import annotations

from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from ..careers.context import as_uuid
from ..db import SessionLocal
from ..governance.approvals import request_approval
from ..models import Application, ApplicationEvent, Interview

VERSION = "1.0.0"
mcp = FastMCP("careerflo-applications")
STATUSES = {"draft", "applied", "screening", "interviewing", "offer", "accepted", "rejected", "withdrawn"}


def _app_dict(a: Application) -> dict:
    return {"id": str(a.id), "company": a.company, "title": a.title, "status": a.status, "job_id": str(a.job_id) if a.job_id else None,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None, "notes": a.notes, "is_synthetic": a.is_synthetic}


def _owned(db, user_id: str, application_id: str) -> Application:
    a = db.get(Application, as_uuid(application_id, "application id"))
    if a is None or a.user_id != as_uuid(user_id):
        raise LookupError("Application not found")
    return a


@mcp.tool(description="Create a draft application record.")
def create_application(user_id: str, company: str, title: str, job_id: str | None = None, notes: str | None = None) -> dict:
    with SessionLocal() as db:
        a = Application(user_id=as_uuid(user_id), company=company[:200], title=title[:300], status="draft",
                        job_id=as_uuid(job_id) if job_id else None, notes=notes)
        db.add(a)
        db.commit()
        return _app_dict(a)


@mcp.tool(description="Update status/notes. Moving a draft to 'applied' creates an approval request instead of acting.")
def update_application(user_id: str, application_id: str, status: str | None = None, notes: str | None = None,
                       requested_by: str = "agent") -> dict:
    with SessionLocal() as db:
        a = _owned(db, user_id, application_id)
        if status and status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        if status == "applied" and a.status == "draft":
            req = request_approval(db, a.user_id, "submit_application", f"Submit application: {a.title} at {a.company}",
                                   {"application_id": str(a.id)}, requested_by)
            return {"approval_required": True, "approval_id": str(req.id), "application": _app_dict(a)}
        if status and status != a.status:
            db.add(ApplicationEvent(user_id=a.user_id, application_id=a.id, kind="status_change", detail={"from": a.status, "to": status}))
            a.status = status
        if notes is not None:
            a.notes = notes
        db.commit()
        return {"approval_required": False, "application": _app_dict(a)}


@mcp.tool(description="List the user's applications.")
def list_applications(user_id: str, status: str | None = None) -> dict:
    with SessionLocal() as db:
        stmt = select(Application).where(Application.user_id == as_uuid(user_id)).order_by(Application.created_at.desc())
        if status:
            stmt = stmt.where(Application.status == status)
        return {"applications": [_app_dict(a) for a in db.scalars(stmt.limit(200))]}


@mcp.tool(description="Record a real interview for an application.")
def record_interview(user_id: str, application_id: str, scheduled_at: str, kind: str = "real", notes: str | None = None) -> dict:
    with SessionLocal() as db:
        a = _owned(db, user_id, application_id)
        when = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        i = Interview(user_id=a.user_id, application_id=a.id, kind="real" if kind != "mock" else "mock", role=a.title,
                      scheduled_at=when, feedback={"notes": notes} if notes else {})
        db.add(i)
        if a.status in ("applied", "screening"):
            a.status = "interviewing"
        db.add(ApplicationEvent(user_id=a.user_id, application_id=a.id, kind="interview_scheduled", detail={"at": when.isoformat()}))
        db.commit()
        return {"interview_id": str(i.id), "scheduled_at": when.isoformat()}


@mcp.tool(description="Schedule a follow-up reminder for an application.")
def schedule_followup(user_id: str, application_id: str, due_at: str, note: str = "") -> dict:
    with SessionLocal() as db:
        a = _owned(db, user_id, application_id)
        when = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        ev = ApplicationEvent(user_id=a.user_id, application_id=a.id, kind="followup_scheduled", detail={"note": note[:500]},
                              due_at=when if when.tzinfo else when.replace(tzinfo=timezone.utc))
        db.add(ev)
        db.commit()
        return {"event_id": str(ev.id), "due_at": ev.due_at.isoformat()}


@mcp.tool(description="Full event history for an application.")
def retrieve_application_history(user_id: str, application_id: str) -> dict:
    with SessionLocal() as db:
        a = _owned(db, user_id, application_id)
        evs = db.scalars(select(ApplicationEvent).where(ApplicationEvent.application_id == a.id).order_by(ApplicationEvent.created_at))
        return {"application": _app_dict(a), "events": [{"kind": e.kind, "detail": e.detail, "at": e.created_at.isoformat(),
                                                        "due_at": e.due_at.isoformat() if e.due_at else None} for e in evs]}
