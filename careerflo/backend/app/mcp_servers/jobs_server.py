"""MCP Server A — Job Discovery."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..careers.context import as_uuid
from ..db import SessionLocal
from ..jobs import providers as P
from ..jobs.normalize import NormalizedJob, deduplicate, enrich, to_dict
from ..jobs.search import search_jobs, upsert_jobs
from ..models import Job, SavedJob

VERSION = "1.0.0"
mcp = FastMCP("careerflo-jobs")


def _filters(**kw: Any) -> P.SearchFilters:
    return P.SearchFilters(**{k: v for k, v in kw.items() if v is not None})


async def _run(f: P.SearchFilters, synthetic: bool | None = None) -> dict[str, Any]:
    with SessionLocal() as db:
        return await search_jobs(db, f, include_synthetic=synthetic)


@mcp.tool(description="Search all configured providers (aggregators, employer boards, demo data) with filters; de-duplicated.")
async def search_all_jobs(query: str = "", city: str | None = None, country: str | None = "ca", work_arrangement: str | None = None,
                          salary_min: float | None = None, currency: str | None = None, seniority: str | None = None,
                          skills: list[str] | None = None, company: str | None = None, industry: str | None = None,
                          posted_within_days: int | None = None, employment_type: str | None = None, limit: int = 25) -> dict:
    return await _run(_filters(query=query, city=city, country=country, work_arrangement=work_arrangement, salary_min=salary_min,
                               currency=currency, seniority=seniority, skills=skills or [], company=company, industry=industry,
                               posted_within_days=posted_within_days, employment_type=employment_type, limit=min(limit, 100)))


@mcp.tool(description="Search JSearch (RapidAPI) only.")
async def search_jsearch_jobs(query: str, city: str | None = None, country: str = "ca", limit: int = 25) -> dict:
    f = _filters(query=query, city=city, country=country, limit=limit)
    jobs = await P.search_jsearch(f)
    with SessionLocal() as db:
        rows = upsert_jobs(db, jobs)
        return {"jobs": [to_dict(r) for r in rows][:limit], "source": "jsearch"}


@mcp.tool(description="Search Adzuna only.")
async def search_adzuna_jobs(query: str, city: str | None = None, country: str = "ca", salary_min: float | None = None, limit: int = 25) -> dict:
    jobs = await P.search_adzuna(_filters(query=query, city=city, country=country, salary_min=salary_min, limit=limit))
    with SessionLocal() as db:
        rows = upsert_jobs(db, jobs)
        return {"jobs": [to_dict(r) for r in rows][:limit], "source": "adzuna"}


async def _board(kind: str, token: str, company: str | None) -> dict:
    jobs = await P.BOARD_FETCHERS[kind](token, company)
    with SessionLocal() as db:
        rows = upsert_jobs(db, jobs)
        return {"jobs": [to_dict(r) for r in rows][:100], "source": kind, "board": token}


@mcp.tool(description="Fetch all open jobs from one employer's Greenhouse board (board token required).")
async def fetch_greenhouse_jobs(board_token: str, company: str | None = None) -> dict:
    return await _board("greenhouse", board_token, company)


@mcp.tool(description="Fetch all open jobs from one employer's Lever postings site.")
async def fetch_lever_jobs(site: str, company: str | None = None) -> dict:
    return await _board("lever", site, company)


@mcp.tool(description="Fetch all open jobs from one employer's Ashby job board.")
async def fetch_ashby_jobs(board_name: str, company: str | None = None) -> dict:
    return await _board("ashby", board_name, company)


@mcp.tool(description="Indeed-origin postings via the authorised JSearch aggregator (no direct Indeed access).")
async def search_indeed_origin_jobs(query: str, city: str | None = None, country: str = "ca", salary_min: float | None = None,
                                    currency: str | None = None, limit: int = 25) -> dict:
    return await _run(_filters(query=query, city=city, country=country, salary_min=salary_min, currency=currency, origin="indeed", limit=limit))


@mcp.tool(description="LinkedIn-origin postings via the authorised JSearch aggregator (no direct LinkedIn access).")
async def search_linkedin_origin_jobs(query: str, city: str | None = None, country: str = "ca", salary_min: float | None = None,
                                      currency: str | None = None, limit: int = 25) -> dict:
    return await _run(_filters(query=query, city=city, country=country, salary_min=salary_min, currency=currency, origin="linkedin", limit=limit))


@mcp.tool(description="Normalise one raw posting (already in the common schema or close to it).")
def normalize_job(job: dict) -> dict:
    nj = enrich(NormalizedJob(**{k: v for k, v in job.items() if k in NormalizedJob.model_fields}))
    return nj.model_dump(mode="json") | {"dedupe_key": nj.dedupe_key}


@mcp.tool(description="De-duplicate a list of normalised postings across providers.")
def deduplicate_jobs(jobs: list[dict]) -> dict:
    items = [NormalizedJob(**{k: v for k, v in j.items() if k in NormalizedJob.model_fields}) for j in jobs[:500]]
    out = deduplicate(items)
    return {"input": len(items), "output": len(out), "jobs": [j.model_dump(mode="json") for j in out]}


@mcp.tool(description="Check that an application URL is reachable.")
async def verify_job_url(url: str) -> dict:
    return await P.verify_url(url)


@mcp.tool(description="Save a job to the user's saved list.")
def save_job(user_id: str, job_id: str, note: str | None = None) -> dict:
    with SessionLocal() as db:
        uid, jid = as_uuid(user_id), as_uuid(job_id, "job id")
        if db.get(Job, jid) is None:
            return {"saved": False, "error": "job not found"}
        existing = db.query(SavedJob).filter_by(user_id=uid, job_id=jid).first()
        if existing:
            return {"saved": True, "id": str(existing.id), "already": True}
        row = SavedJob(user_id=uid, job_id=jid, note=note)
        db.add(row)
        db.commit()
        return {"saved": True, "id": str(row.id)}
