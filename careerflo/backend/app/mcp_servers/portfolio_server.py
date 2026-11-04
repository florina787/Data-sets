"""MCP Server D — GitHub Portfolio."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..careers import portfolio as G
from ..careers.context import as_uuid, get_job
from ..db import SessionLocal
from ..models import Portfolio, PortfolioProject, utcnow

VERSION = "1.0.0"
mcp = FastMCP("careerflo-portfolio")


@mcp.tool(description="List a GitHub user's public, non-fork repositories with languages and topics.")
async def list_repositories(username: str, limit: int = 20) -> dict:
    return {"username": username, "repositories": await G.list_repositories(username, min(limit, 30))}


@mcp.tool(description="Inspect one public repository.")
async def inspect_repository(username: str, repository: str) -> dict:
    repos = await G.list_repositories(username, 30)
    repo = next((r for r in repos if r["name"].lower() == repository.lower()), None)
    if repo is None:
        raise LookupError("Repository not found among the user's public repositories")
    return repo | {"skills": sorted(G.project_skills(repo))}


@mcp.tool(description="Summarise languages and skills across a user's public repositories.")
async def analyze_technology_stack(username: str) -> dict:
    return G.analyze_stack(await G.list_repositories(username, 30))


@mcp.tool(description="Find the repositories that best evidence a job's skills.")
async def match_project_to_job(username: str, job_id: str) -> dict:
    repos = await G.list_repositories(username, 30)
    with SessionLocal() as db:
        job = get_job(db, job_id)
    return {"job": {"title": job["title"], "company": job["company"]}, "projects": G.match_projects(repos, job)}


@mcp.tool(description="Analyse a portfolio and save it to the user's account.")
async def generate_portfolio_summary(user_id: str, username: str) -> dict:
    repos = await G.list_repositories(username, 30)
    stack = G.analyze_stack(repos)
    with SessionLocal() as db:
        uid = as_uuid(user_id)
        p = Portfolio(user_id=uid, github_username=username, summary=stack, analyzed_at=utcnow())
        db.add(p)
        db.flush()
        for r in repos:
            db.add(PortfolioProject(user_id=uid, portfolio_id=p.id, name=r["name"], url=r["url"], description=r.get("description"),
                                    languages=r.get("languages") or {}, topics=r.get("topics") or [], stars=r.get("stars", 0)))
        db.commit()
        return {"portfolio_id": str(p.id), **stack, "repositories": repos}
