from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import mcp_gateway as gw
from ..billing.metering import metered
from ..jobs.normalize import to_dict
from ..jobs.providers import SearchFilters
from ..jobs.search import SOURCES, configured_sources
from ..models import EmployerBoard, Job, JobSource, SavedJob, utcnow
from ..security.auth import AdminUser, CurrentUser, DB
from .common import IdemKey, with_usage

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class SearchIn(SearchFilters):
    limit: int = Field(25, ge=1, le=100)


@router.post("/search")
async def search(body: SearchIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    feature = "job_board_search" if body.origin else "job_discovery"
    async with metered(user.id, feature, idem) as m:
        if m.replay is not None:
            return m.replay
        if body.origin:
            tool = "search_indeed_origin_jobs" if body.origin == "indeed" else "search_linkedin_origin_jobs"
            if body.origin not in ("indeed", "linkedin"):
                raise HTTPException(422, "origin must be indeed or linkedin")
            args = {k: v for k, v in body.model_dump().items() if k in ("query", "city", "country", "salary_min", "currency", "limit") and v is not None}
        else:
            tool = "search_all_jobs"
            args = {k: v for k, v in body.model_dump().items() if v not in (None, [], "") and k != "origin"}
        res = await gw.call_tool(user.id, "user", "jobs", tool, args)
        data = res.data
        if body.origin and data.get("providers", {}).get("jsearch") == "not_configured":
            data["notice"] = ("Indeed/LinkedIn-origin search uses the licensed JSearch aggregator. Set JSEARCH_API_KEY to enable it; "
                              "Career_flo never scrapes Indeed or LinkedIn directly.")
            # Not a successful execution: the reservation is released and no trial is consumed.
            raise HTTPException(503, data["notice"])
        m.set_result(data)
    return with_usage(data, user.id, feature)


@router.get("/radar")
async def hidden_job_radar(user: CurrentUser, db: DB, idem: IdemKey = None) -> dict:
    """Hidden Job Radar + Early Applicant Intelligence: postings straight from employer boards and
    anything first seen in the last 72 hours, freshest first."""
    async with metered(user.id, "job_discovery", idem) as m:
        if m.replay is not None:
            return m.replay
        boards = db.scalars(select(EmployerBoard)).all()
        refreshed = []
        for b in boards[:10]:
            tool = {"greenhouse": "fetch_greenhouse_jobs", "lever": "fetch_lever_jobs", "ashby": "fetch_ashby_jobs"}[b.source_id]
            key = "board_token" if b.source_id == "greenhouse" else "site" if b.source_id == "lever" else "board_name"
            try:
                await gw.call_tool(user.id, "user", "jobs", tool, {key: b.board_token, "company": b.company_name})
                refreshed.append(b.company_name)
            except (gw.ToolFailed, gw.ToolDenied):
                pass
        cutoff = utcnow() - timedelta(hours=72)
        rows = db.scalars(select(Job).where(Job.posted_at >= cutoff).order_by(Job.posted_at.desc()).limit(60)).all()
        jobs = []
        for j in rows:
            d = to_dict(j)
            pa = j.posted_at if j.posted_at.tzinfo else j.posted_at.replace(tzinfo=cutoff.tzinfo)
            hours = int((utcnow() - pa).total_seconds() // 3600)
            d["hours_since_posted"] = hours
            d["early_applicant"] = hours <= 48
            d["direct_from_employer"] = j.source in ("greenhouse", "lever", "ashby")
            jobs.append(d)
        jobs.sort(key=lambda d: (not d["direct_from_employer"], d["hours_since_posted"]))
        result = {"jobs": jobs, "boards_refreshed": refreshed,
                  "explanation": "Early applicant = first published ≤48h ago. Employer-board postings often appear before aggregators index them."}
        m.set_result(result)
    return with_usage(result, user.id, "job_discovery")


@router.get("/sources")
def sources(db: DB) -> dict:
    conf = configured_sources()
    boards = db.scalars(select(EmployerBoard)).all()
    return {"sources": [{"id": k, **v, "configured": conf.get(k, False)} for k, v in SOURCES.items()],
            "boards": [{"id": str(b.id), "source": b.source_id, "board_token": b.board_token, "company": b.company_name} for b in boards]}


class BoardIn(BaseModel):
    source: str = Field(pattern="^(greenhouse|lever|ashby)$")
    board_token: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
    company_name: str = Field(min_length=1, max_length=200)


@router.post("/boards", status_code=201)
def add_board(body: BoardIn, admin: AdminUser, db: DB) -> dict:
    if not db.get(JobSource, body.source):
        raise HTTPException(400, "Unknown source")
    b = EmployerBoard(source_id=body.source, board_token=body.board_token, company_name=body.company_name)
    db.add(b)
    db.commit()
    return {"id": str(b.id)}


@router.get("/saved")
def saved(user: CurrentUser, db: DB) -> dict:
    rows = db.execute(select(SavedJob, Job).join(Job, Job.id == SavedJob.job_id).where(SavedJob.user_id == user.id)
                      .order_by(SavedJob.created_at.desc())).all()
    return {"jobs": [to_dict(j) | {"saved_id": str(s.id), "note": s.note} for s, j in rows]}


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return to_dict(j) | {"description": j.description}


@router.post("/{job_id}/save")
async def save(job_id: uuid.UUID, user: CurrentUser) -> dict:
    return (await gw.call_tool(user.id, "user", "jobs", "save_job", {"job_id": str(job_id)})).data


@router.delete("/{job_id}/save")
def unsave(job_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    s = db.scalar(select(SavedJob).where(SavedJob.user_id == user.id, SavedJob.job_id == job_id))
    if s:
        db.delete(s)
        db.commit()
    return {"saved": False}


@router.post("/{job_id}/verify")
async def verify(job_id: uuid.UUID, user: CurrentUser, db: DB) -> dict:
    j = db.get(Job, job_id)
    if not j or not j.apply_url:
        raise HTTPException(404, "Job or URL not found")
    if j.is_synthetic:
        return {"url": j.apply_url, "reachable": False, "reason": "synthetic demo posting"}
    res = (await gw.call_tool(user.id, "user", "jobs", "verify_job_url", {"url": j.apply_url})).data
    j.verification_status = "verified" if res.get("reachable") else "unreachable"
    db.commit()
    return res
