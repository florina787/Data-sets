"""Recruiter CRM and Application Tracker (record keeping is free; intelligence and automation are metered)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from .. import mcp_gateway as gw
from ..agents.graph import run_workflow
from ..billing.metering import metered
from ..governance.approvals import request_approval
from ..models import Application, ApplicationEvent, Recruiter, RecruiterInteraction, utcnow
from ..security.auth import CurrentUser, DB
from .common import IdemKey, with_usage

router = APIRouter(prefix="/api", tags=["crm & tracker"])


# ---------------------------------------------------------------- recruiters
class RecruiterIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    linkedin_url: str | None = Field(None, max_length=500, pattern=r"^https://([a-z]+\.)?linkedin\.com/.*$")
    notes: str | None = Field(None, max_length=5000)


def _rec(r: Recruiter) -> dict:
    return {"id": str(r.id), "name": r.name, "company": r.company, "email": r.email, "linkedin_url": r.linkedin_url,
            "notes": r.notes, "is_synthetic": r.is_synthetic}


def _owned(db, model, user_id, oid: uuid.UUID):
    row = db.get(model, oid)
    if row is None or row.user_id != user_id:
        raise HTTPException(404, f"{model.__name__} not found")
    return row


@router.get("/recruiters")
def list_recruiters(user: CurrentUser, db: DB) -> dict:
    return {"recruiters": [_rec(r) for r in db.scalars(select(Recruiter).where(Recruiter.user_id == user.id).order_by(Recruiter.name))]}


@router.post("/recruiters", status_code=201)
def create_recruiter(body: RecruiterIn, user: CurrentUser, db: DB) -> dict:
    r = Recruiter(user_id=user.id, **body.model_dump())
    db.add(r)
    db.commit()
    return _rec(r)


@router.put("/recruiters/{rid}")
def update_recruiter(rid: uuid.UUID, body: RecruiterIn, user: CurrentUser, db: DB) -> dict:
    r = _owned(db, Recruiter, user.id, rid)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return _rec(r)


class InteractionIn(BaseModel):
    channel: str = Field(pattern="^(email|call|linkedin|meeting)$")
    direction: str = Field(pattern="^(inbound|outbound)$")
    summary: str = Field(min_length=1, max_length=4000)
    follow_up_at: datetime | None = None


@router.get("/recruiters/{rid}/interactions")
def interactions(rid: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    _owned(db, Recruiter, user.id, rid)
    rows = db.scalars(select(RecruiterInteraction).where(RecruiterInteraction.recruiter_id == rid)
                      .order_by(RecruiterInteraction.occurred_at.desc()))
    return {"interactions": [{"id": str(i.id), "channel": i.channel, "direction": i.direction, "summary": i.summary,
                              "occurred_at": i.occurred_at.isoformat(),
                              "follow_up_at": i.follow_up_at.isoformat() if i.follow_up_at else None} for i in rows]}


@router.post("/recruiters/{rid}/interactions", status_code=201)
def add_interaction(rid: uuid.UUID, body: InteractionIn, user: CurrentUser, db: DB) -> dict:
    _owned(db, Recruiter, user.id, rid)
    i = RecruiterInteraction(user_id=user.id, recruiter_id=rid, **body.model_dump())
    db.add(i)
    db.commit()
    return {"id": str(i.id)}


@router.post("/recruiters/{rid}/report")
async def recruiter_report(rid: uuid.UUID, user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    """Recruiter Intelligence + Follow-up Intelligence from the user's own interaction history."""
    async with metered(user.id, "recruiter_intelligence", idem) as m:
        if m.replay is not None:
            return m.replay
        r = _owned(db, Recruiter, user.id, rid)
        rows = list(db.scalars(select(RecruiterInteraction).where(RecruiterInteraction.recruiter_id == rid)
                               .order_by(RecruiterInteraction.occurred_at)))
        now = utcnow()

        def aware(d):
            return d if d.tzinfo else d.replace(tzinfo=now.tzinfo)

        inbound = [i for i in rows if i.direction == "inbound"]
        outbound = [i for i in rows if i.direction == "outbound"]
        last = aware(rows[-1].occurred_at) if rows else None
        days = (now - last).days if last else None
        apps = list(db.scalars(select(Application).where(Application.user_id == user.id, Application.company == r.company))) if r.company else []
        if days is None:
            action = "Send a short introduction referencing a specific open role."
        elif rows[-1].direction == "outbound" and days < 5:
            action = f"Wait — you reached out {days} day(s) ago. Follow up after 5 business days."
        elif rows[-1].direction == "outbound":
            action = "Send one polite follow-up with a new piece of value (a relevant project or update)."
        else:
            action = "Reply promptly — the recruiter was the last to write."
        result = {"recruiter": _rec(r), "interactions": len(rows), "inbound": len(inbound), "outbound": len(outbound),
                  "response_ratio": round(len(inbound) / len(outbound), 2) if outbound else None,
                  "days_since_last_contact": days, "related_applications": [{"id": str(a.id), "title": a.title, "status": a.status} for a in apps],
                  "next_action": action, "referral_tip": f"Ask whether anyone on the {r.company or 'hiring'} team would be open to a short chat." if r.company else None}
        m.set_result(result)
    return with_usage(result, user.id, "recruiter_intelligence")


class EmailDraftIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


@router.post("/recruiters/{rid}/email")
def request_email(rid: uuid.UUID, body: EmailDraftIn, user: CurrentUser, db: DB) -> dict:
    r = _owned(db, Recruiter, user.id, rid)
    req = request_approval(db, user.id, "send_recruiter_email", f"Email {r.name}: {body.subject}",
                           {"recruiter_id": str(r.id), "subject": body.subject, "body": body.body}, "user")
    return {"approval_required": True, "approval_id": str(req.id)}


# ---------------------------------------------------------------- applications
class ApplicationIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    job_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=5000)


class ApplicationPatch(BaseModel):
    status: str | None = Field(None, pattern="^(draft|applied|screening|interviewing|offer|accepted|rejected|withdrawn)$")
    notes: str | None = Field(None, max_length=5000)
    salary_offered: float | None = Field(None, ge=0)


@router.get("/applications")
async def list_applications(user: CurrentUser) -> dict:
    return (await gw.call_tool(user.id, "user", "applications", "list_applications", {})).data


@router.post("/applications", status_code=201)
async def create_application(body: ApplicationIn, user: CurrentUser) -> dict:
    args = {"company": body.company, "title": body.title, "notes": body.notes} | ({"job_id": str(body.job_id)} if body.job_id else {})
    return (await gw.call_tool(user.id, "user", "applications", "create_application", args)).data


@router.patch("/applications/{aid}")
async def patch_application(aid: uuid.UUID, body: ApplicationPatch, user: CurrentUser, db: DB) -> dict:
    """Moving a draft to 'applied' always goes through an approval request."""
    if body.salary_offered is not None:
        a = _owned(db, Application, user.id, aid)
        a.salary_offered = body.salary_offered
        db.commit()
    args = {"application_id": str(aid)} | {k: v for k, v in {"status": body.status, "notes": body.notes}.items() if v is not None}
    return (await gw.call_tool(user.id, "user", "applications", "update_application", args)).data


@router.get("/applications/{aid}/history")
async def history(aid: uuid.UUID, user: CurrentUser) -> dict:
    return (await gw.call_tool(user.id, "user", "applications", "retrieve_application_history", {"application_id": str(aid)})).data


class FollowupIn(BaseModel):
    due_at: datetime
    note: str = Field("", max_length=500)


@router.post("/applications/{aid}/followups", status_code=201)
async def followup(aid: uuid.UUID, body: FollowupIn, user: CurrentUser) -> dict:
    return (await gw.call_tool(user.id, "user", "applications", "schedule_followup",
                               {"application_id": str(aid), "due_at": body.due_at.isoformat(), "note": body.note})).data


class InterviewIn(BaseModel):
    scheduled_at: datetime
    notes: str | None = Field(None, max_length=2000)


@router.post("/applications/{aid}/interviews", status_code=201)
async def add_interview(aid: uuid.UUID, body: InterviewIn, user: CurrentUser) -> dict:
    return (await gw.call_tool(user.id, "user", "applications", "record_interview",
                               {"application_id": str(aid), "scheduled_at": body.scheduled_at.isoformat(), "notes": body.notes})).data


@router.get("/followups")
def upcoming(user: CurrentUser, db: DB) -> dict:
    rows = db.execute(select(ApplicationEvent, Application).join(Application, Application.id == ApplicationEvent.application_id)
                      .where(ApplicationEvent.user_id == user.id, ApplicationEvent.kind == "followup_scheduled")
                      .order_by(ApplicationEvent.due_at)).all()
    return {"followups": [{"id": str(e.id), "application_id": str(a.id), "company": a.company, "title": a.title,
                           "due_at": e.due_at.isoformat() if e.due_at else None, "note": e.detail.get("note")} for e, a in rows]}


class AutomateIn(BaseModel):
    request: str = Field(min_length=5, max_length=1000)


@router.post("/applications/automate")
async def automate(body: AutomateIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    """Application Automation: search → score → tailor → draft → approval request. Nothing is submitted without approval."""
    async with metered(user.id, "application_automation", idem) as m:
        if m.replay is not None:
            return m.replay
        text = body.request if "application package" in body.request.lower() else f"Prepare an application package: {body.request}"
        state = await run_workflow(user.id, text)
        if state.get("status") == "failed" or "autonomous_workflow" not in state.get("results", {}) or \
                "error" in state["results"]["autonomous_workflow"]:
            err = state.get("results", {}).get("autonomous_workflow", {}).get("error") or "; ".join(state.get("notes", []))
            raise HTTPException(422, err or "The workflow could not prepare an application.")
        result = {"cards": state.get("cards", []), "approvals": state.get("approvals", []), "warnings": state.get("warnings", []),
                  "notes": state.get("notes", []), "run_id": state.get("run_id")}
        m.set_result(result)
    return with_usage(result, user.id, "application_automation")


