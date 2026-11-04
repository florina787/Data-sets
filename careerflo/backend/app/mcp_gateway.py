"""MCP gateway: the only path from agents to tools.

Deterministic controls (not delegated to any model):
- discovery over the real MCP protocol (``list_tools``) for every registered server;
- a static per-agent tool allowlist;
- server-side injection of ``user_id`` / ``requested_by`` (a model can never choose whose data it touches);
- JSON-schema validation of arguments by the MCP server, plus size limits here;
- per-user rate limit, per-call timeout, per-run tool-call budget;
- an ``mcp_tool_calls`` audit row (arguments redacted) for every call, allowed or not.

Transport: the servers are in-process ``FastMCP`` instances reached through the SDK's in-memory
transport — real JSON-RPC MCP sessions with no network exposure. Each server can also be run on
stdio for external MCP clients: ``python -m app.mcp_servers.run <name>``.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from .db import SessionLocal
from .mcp_servers import (
    analytics_server,
    applications_server,
    company_server,
    governance_server,
    jobs_server,
    portfolio_server,
    resume_server,
)
from .models import McpToolCall
from .security.ratelimit import limiter
from .security.sanitize import redact_obj

SERVERS: dict[str, tuple[FastMCP, str, str]] = {
    "jobs": (jobs_server.mcp, jobs_server.VERSION, "A — Job Discovery"),
    "resume": (resume_server.mcp, resume_server.VERSION, "B — Resume Intelligence"),
    "applications": (applications_server.mcp, applications_server.VERSION, "C — Application Tracking"),
    "portfolio": (portfolio_server.mcp, portfolio_server.VERSION, "D — GitHub Portfolio"),
    "company": (company_server.mcp, company_server.VERSION, "E — Company Research"),
    "analytics": (analytics_server.mcp, analytics_server.VERSION, "F — Career Analytics"),
    "governance": (governance_server.mcp, governance_server.VERSION, "G — Governance"),
}
INJECTED_ARGS = {"user_id", "requested_by"}

_GOV = {"governance.validate_tool_request", "governance.check_permissions", "governance.redact_sensitive_data",
        "governance.record_audit_event"}
AGENT_ALLOWLIST: dict[str, set[str]] = {
    "job_discovery": {"jobs.search_all_jobs", "jobs.search_jsearch_jobs", "jobs.search_adzuna_jobs", "jobs.fetch_greenhouse_jobs",
                      "jobs.fetch_lever_jobs", "jobs.fetch_ashby_jobs", "jobs.search_indeed_origin_jobs",
                      "jobs.search_linkedin_origin_jobs", "jobs.normalize_job", "jobs.deduplicate_jobs", "jobs.verify_job_url",
                      "jobs.save_job"} | _GOV,
    "job_matching": {"resume.compare_resume_to_job", "resume.analyze_resume", "company.analyze_job_requirements"} | _GOV,
    "resume_intelligence": {"resume.parse_resume", "resume.extract_skills", "resume.analyze_resume", "resume.compare_resume_to_job",
                            "resume.tailor_resume", "resume.validate_resume_claims", "resume.generate_pdf", "resume.generate_docx"} | _GOV,
    "ats_intelligence": {"resume.analyze_resume", "resume.compare_resume_to_job", "company.analyze_job_requirements"} | _GOV,
    "cover_letter": {"resume.analyze_resume", "resume.validate_resume_claims", "company.analyze_job_requirements"} | _GOV,
    "interview": {"company.analyze_job_requirements", "applications.list_applications"} | _GOV,
    "coding_coach": set(_GOV),
    "company_research": {"company.retrieve_company_information", "company.analyze_job_requirements",
                         "company.summarize_public_sources", "company.compare_companies"} | _GOV,
    "recruiter_crm": {"applications.list_applications", "applications.schedule_followup", "governance.request_human_approval"} | _GOV,
    "application_tracker": {"applications.create_application", "applications.update_application", "applications.list_applications",
                            "applications.record_interview", "applications.schedule_followup",
                            "applications.retrieve_application_history"} | _GOV,
    "portfolio": {"portfolio.list_repositories", "portfolio.inspect_repository", "portfolio.analyze_technology_stack",
                  "portfolio.match_project_to_job", "portfolio.generate_portfolio_summary"} | _GOV,
    "salary": {"analytics.analyze_salary_distribution", "jobs.search_all_jobs"} | _GOV,
    "career_analytics": {"analytics.calculate_application_metrics", "analytics.calculate_interview_conversion",
                         "analytics.analyze_salary_distribution", "analytics.identify_skill_gaps",
                         "analytics.generate_dashboard_data"} | _GOV,
    "autonomous_workflow": {"jobs.search_all_jobs", "jobs.save_job", "resume.compare_resume_to_job", "resume.tailor_resume",
                            "resume.validate_resume_claims", "applications.create_application",
                            "applications.update_application", "governance.request_human_approval"} | _GOV,
    "governance": {"governance.validate_tool_request", "governance.check_permissions", "governance.redact_sensitive_data",
                   "governance.request_human_approval", "governance.record_audit_event"},
    # Used by REST endpoints that call tools directly on the user's behalf.
    "user": {f"{s}.{t}" for s in ("jobs", "resume", "applications", "portfolio", "company", "analytics") for t in ("*",)},
}

MAX_ARG_BYTES = 120_000
CALL_TIMEOUT_S = 45.0
USER_TOOL_CALLS_PER_MINUTE = 120


class ToolDenied(PermissionError):
    pass


class ToolFailed(RuntimeError):
    pass


@dataclass
class ToolResult:
    server: str
    tool: str
    data: Any
    duration_ms: int


_catalog_cache: dict[str, list[dict[str, Any]]] | None = None


async def discover() -> dict[str, list[dict[str, Any]]]:
    """List tools from every server through the MCP protocol."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    out: dict[str, list[dict[str, Any]]] = {}
    for name, (server, version, _label) in SERVERS.items():
        async with create_connected_server_and_client_session(server) as session:
            tools = await session.list_tools()
            out[name] = [{"name": t.name, "description": t.description, "version": version,
                          "input_schema": _public_schema(t.inputSchema)} for t in tools.tools]
    _catalog_cache = out
    return out


def _public_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Hide server-injected arguments from anything a model sees."""
    s = json.loads(json.dumps(schema))
    for k in INJECTED_ARGS:
        s.get("properties", {}).pop(k, None)
    if "required" in s:
        s["required"] = [r for r in s["required"] if r not in INJECTED_ARGS]
    return s


def is_allowed(agent: str, server: str, tool: str) -> bool:
    allowed = AGENT_ALLOWLIST.get(agent, set())
    return f"{server}.{tool}" in allowed or f"{server}.*" in allowed


async def call_tool(user_id: uuid.UUID, agent: str, server: str, tool: str, arguments: dict[str, Any] | None = None,
                    *, run_id: uuid.UUID | None = None, timeout: float = CALL_TIMEOUT_S) -> ToolResult:
    args = {k: v for k, v in (arguments or {}).items() if k not in INJECTED_ARGS}
    version = SERVERS[server][1] if server in SERVERS else "?"
    t0 = time.perf_counter()

    def record(status: str, error: str | None = None) -> None:
        with SessionLocal() as db:
            db.add(McpToolCall(user_id=user_id, agent_run_id=run_id, server=server, tool=tool, tool_version=version,
                               agent=agent, status=status, duration_ms=int((time.perf_counter() - t0) * 1000),
                               arguments=redact_obj(args), error=error and error[:1000]))
            db.commit()

    if server not in SERVERS:
        record("denied", "unknown server")
        raise ToolDenied(f"Unknown MCP server '{server}'")
    if not is_allowed(agent, server, tool):
        record("denied", "not in agent allowlist")
        raise ToolDenied(f"Agent '{agent}' may not call {server}.{tool}")
    if len(json.dumps(args, default=str)) > MAX_ARG_BYTES:
        record("denied", "arguments too large")
        raise ToolDenied("Tool arguments too large")
    try:
        limiter.check(f"mcp:{user_id}", USER_TOOL_CALLS_PER_MINUTE)
    except Exception:
        record("denied", "rate limited")
        raise ToolDenied("Tool rate limit reached; try again in a minute") from None

    catalog = await discover()
    schema_props = next((t["input_schema"] for t in catalog[server] if t["name"] == tool), None)
    if schema_props is None:
        record("denied", "unknown tool")
        raise ToolDenied(f"Unknown tool {server}.{tool}")
    full = await _full_schema(server, tool)
    if "user_id" in full.get("properties", {}):
        args["user_id"] = str(user_id)
    if "requested_by" in full.get("properties", {}):
        args["requested_by"] = agent

    try:
        with anyio.fail_after(timeout):
            async with create_connected_server_and_client_session(SERVERS[server][0]) as session:
                res = await session.call_tool(tool, args)
    except TimeoutError:
        record("timeout", f"exceeded {timeout}s")
        raise ToolFailed(f"{server}.{tool} timed out") from None
    if res.isError:
        msg = " ".join(getattr(c, "text", "") for c in res.content)[:500]
        record("error", msg)
        raise ToolFailed(msg or f"{server}.{tool} failed")
    data: Any = res.structuredContent
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    if data is None:
        text = " ".join(getattr(c, "text", "") for c in res.content)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"text": text}
    record("ok")
    return ToolResult(server, tool, data, int((time.perf_counter() - t0) * 1000))


_full_schemas: dict[tuple[str, str], dict[str, Any]] = {}


async def _full_schema(server: str, tool: str) -> dict[str, Any]:
    key = (server, tool)
    if key not in _full_schemas:
        for t in await SERVERS[server][0].list_tools():
            _full_schemas[(server, t.name)] = t.inputSchema
    return _full_schemas.get(key, {})
