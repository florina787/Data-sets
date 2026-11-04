"""MCP Server F — Career Analytics."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from ..careers import analytics as A
from ..careers.context import as_uuid, candidate_profile
from ..careers.salary import salary_distribution
from ..db import SessionLocal
from ..jobs.normalize import to_dict
from ..models import Application, Interview, Job

VERSION = "1.0.0"
mcp = FastMCP("careerflo-analytics")


@mcp.tool(description="Application funnel and response/interview/offer rates.")
def calculate_application_metrics(user_id: str) -> dict:
    with SessionLocal() as db:
        return A.application_metrics(list(db.scalars(select(Application).where(Application.user_id == as_uuid(user_id)))))


@mcp.tool(description="Interview counts, mock-interview trend and interview-to-offer conversion.")
def calculate_interview_conversion(user_id: str) -> dict:
    with SessionLocal() as db:
        uid = as_uuid(user_id)
        return A.interview_conversion(list(db.scalars(select(Interview).where(Interview.user_id == uid))),
                                      list(db.scalars(select(Application).where(Application.user_id == uid))))


@mcp.tool(description="Distribution of published salaries for jobs matching a title keyword and currency.")
def analyze_salary_distribution(title_keyword: str = "", currency: str | None = None, city: str | None = None) -> dict:
    with SessionLocal() as db:
        stmt = select(Job).where(Job.salary_verified.is_(True))
        if title_keyword:
            stmt = stmt.where(Job.title.ilike(f"%{title_keyword[:80]}%"))
        if city:
            stmt = stmt.where(Job.location.ilike(f"%{city[:80]}%"))
        return salary_distribution([to_dict(j) for j in db.scalars(stmt.limit(1000))], currency)


@mcp.tool(description="Skills most demanded by stored jobs that the user's verified profile lacks.")
def identify_skill_gaps(user_id: str, title_keyword: str = "") -> dict:
    with SessionLocal() as db:
        cand = candidate_profile(db, as_uuid(user_id))
        stmt = select(Job)
        if title_keyword:
            stmt = stmt.where(Job.title.ilike(f"%{title_keyword[:80]}%"))
        jobs = [to_dict(j) for j in db.scalars(stmt.limit(500))]
        return {"gaps": A.skill_gaps(cand["skills"], jobs), "based_on_jobs": len(jobs)}


@mcp.tool(description="All dashboard data for the user.")
def generate_dashboard_data(user_id: str) -> dict:
    with SessionLocal() as db:
        return A.dashboard(db, as_uuid(user_id))
