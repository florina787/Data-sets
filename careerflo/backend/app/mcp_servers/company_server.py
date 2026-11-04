"""MCP Server E — Company Research."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from ..careers import company as C
from ..careers.context import get_job
from ..db import SessionLocal
from ..jobs.normalize import to_dict
from ..models import Job

VERSION = "1.0.0"
mcp = FastMCP("careerflo-company")


def _company_jobs(company: str) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(select(Job).where(Job.company.ilike(f"%{company[:100]}%")).limit(200))
        return [to_dict(j) for j in rows]


@mcp.tool(description="Company brief from stored postings and Wikipedia, with citations.")
async def retrieve_company_information(company: str, use_web: bool = True) -> dict:
    return await C.research_company(company, _company_jobs(company), use_web)


@mcp.tool(description="Structured requirements of a job (skills, seniority, arrangement, published salary).")
def analyze_job_requirements(job_id: str) -> dict:
    with SessionLocal() as db:
        j = get_job(db, job_id)
    keys = ("title", "company", "seniority", "work_arrangement", "required_skills", "preferred_skills", "salary_min",
            "salary_max", "salary_currency", "salary_verified", "apply_url", "source", "is_synthetic")
    return {k: j.get(k) for k in keys}


@mcp.tool(description="Summarise public sources (Wikipedia + postings) for a company.")
async def summarize_public_sources(company: str) -> dict:
    r = await C.research_company(company, _company_jobs(company), True)
    return {"company": company, "citations": r["citations"], "overview": (r.get("overview") or {}).get("extract")}


@mcp.tool(description="Compare several companies side by side.")
async def compare_companies(companies: list[str], use_web: bool = False) -> dict:
    reports = [await C.research_company(c, _company_jobs(c), use_web) for c in companies[:5]]
    return {"comparison": C.compare_companies(reports)}
