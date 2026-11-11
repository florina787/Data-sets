"""Agent Mission Control, MCP tool registry, Governance Center, system health."""
from __future__ import annotations

import uuid
from collections import Counter

import psutil
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .. import mcp_gateway as gw
from ..agents.graph import run_workflow
from ..agents.intents import AGENT_LABELS
from ..billing.metering import metered
from ..governance.approvals import CONSEQUENTIAL_ACTIONS, decide, list_requests
from ..llm.qwen import get_llm
from ..models import AgentRun, AuditEvent, InferenceMetric, McpToolCall
from ..security.auth import CurrentUser, DB
from .common import IdemKey, with_usage

router = APIRouter(prefix="/api", tags=["mission control & governance"])


@router.get("/health")
def health() -> dict:
    """Liveness: the process is up. Cheap and dependency-free (used by the container HEALTHCHECK)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> JSONResponse:
    """Readiness: database must answer; inference and payment providers are reported, and degrade gracefully."""
    from sqlalchemy import text

    from ..config import get_settings
    from ..db import SessionLocal

    s = get_settings()
    checks: dict = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        checks["database"] = {"ok": False, "error": type(exc).__name__}
    llm = await get_llm().health()
    checks["inference"] = {"ok": bool(llm.get("ok")), "provider": llm.get("provider"), "model": llm.get("model"),
                           "fallback": "deterministic features keep working; Qwen narrative/polish is skipped" if not llm.get("ok") else None}
    checks["auth"] = {"mode": s.auth_mode, "configured": s.auth_mode == "local" or bool(s.supabase_url)}
    checks["payments"] = {"configured": bool(s.stripe_secret_key and s.stripe_webhook_secret),
                          "mode": "live" if s.stripe_secret_key.startswith("sk_live") else "test" if s.stripe_secret_key else "off"}
    checks["job_providers"] = {"jsearch": bool(s.jsearch_api_key), "adzuna": bool(s.adzuna_app_id and s.adzuna_app_key),
                               "synthetic_demo": s.enable_synthetic_jobs}
    db_ok = checks["database"]["ok"]
    status = "ok" if db_ok and checks["inference"]["ok"] else ("degraded" if db_ok else "down")
    return JSONResponse({"status": status, "checks": checks}, status_code=200 if db_ok else 503)


@router.get("/system/llm")
async def llm_status() -> dict:
    llm = get_llm()
    return await llm.health() | {"queue_depth": llm.queue_depth}


@router.get("/agents/catalog")
def agents_catalog() -> dict:
    return {"agents": [{"id": k, "label": v, "tools": sorted(gw.AGENT_ALLOWLIST.get(k, set()))} for k, v in AGENT_LABELS.items()]}


@router.get("/agents/runs")
def runs(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(AgentRun).where(AgentRun.user_id == user.id).order_by(AgentRun.created_at.desc()).limit(50))
    return {"runs": [{"id": str(r.id), "intent": r.intent, "agents": r.agents, "status": r.status, "steps": r.steps, "error": r.error,
                      "duration_ms": r.duration_ms, "created_at": r.created_at.isoformat(), "is_synthetic": r.is_synthetic} for r in rows]}


@router.get("/agents/metrics")
def metrics(user: CurrentUser, db: DB) -> dict:
    inf = list(db.scalars(select(InferenceMetric).where(InferenceMetric.user_id == user.id)
                          .order_by(InferenceMetric.created_at.desc()).limit(200)))
    calls = list(db.scalars(select(McpToolCall).where(McpToolCall.user_id == user.id).order_by(McpToolCall.created_at.desc()).limit(500)))
    ok_inf = [m for m in inf if m.ok]

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    vm = psutil.virtual_memory()
    return {
        "inference": {"requests": len(inf), "errors": len(inf) - len(ok_inf), "avg_ttft_ms": avg([m.ttft_ms for m in ok_inf]),
                      "avg_total_ms": avg([m.total_ms for m in ok_inf]), "avg_tokens_per_second": avg([m.tokens_per_second for m in ok_inf]),
                      "tokens": sum(m.prompt_tokens + m.completion_tokens for m in inf),
                      "recent": [{"at": m.created_at.isoformat(), "model": m.model, "purpose": m.purpose, "ttft_ms": m.ttft_ms,
                                  "total_ms": m.total_ms, "tps": m.tokens_per_second, "ok": m.ok} for m in inf[:30]][::-1]},
        "tools": {"calls": len(calls), "by_status": dict(Counter(c.status for c in calls)),
                  "by_tool": Counter(f"{c.server}.{c.tool}" for c in calls).most_common(12),
                  "avg_ms": avg([c.duration_ms for c in calls]),
                  "error_rate": round(sum(c.status != "ok" for c in calls) / len(calls), 3) if calls else 0.0},
        "system": {"cpu_percent": psutil.cpu_percent(interval=0.1), "memory_percent": vm.percent,
                   "memory_used_gb": round(vm.used / 1e9, 2), "memory_total_gb": round(vm.total / 1e9, 2),
                   "disk_percent": psutil.disk_usage("/").percent, "llm_queue_depth": get_llm().queue_depth},
    }


class WorkflowIn(BaseModel):
    request: str = Field(min_length=5, max_length=2000)


@router.post("/agents/workflow")
async def workflow(body: WorkflowIn, user: CurrentUser, idem: IdemKey = None) -> dict:
    """Run a supervisor workflow outside chat (one Multi-Agent Workflow use)."""
    async with metered(user.id, "multi_agent_workflow", idem) as m:
        if m.replay is not None:
            return m.replay
        state = await run_workflow(user.id, body.request)
        result = {k: state.get(k) for k in ("run_id", "intent", "plan", "cards", "notes", "warnings", "approvals", "steps", "status")}
        m.set_result(result)
    return with_usage(result, user.id, "multi_agent_workflow")


@router.get("/mcp/tools")
async def mcp_tools() -> dict:
    catalog = await gw.discover()
    return {"servers": [{"id": k, "label": gw.SERVERS[k][2], "version": gw.SERVERS[k][1], "tools": v} for k, v in catalog.items()],
            "transport": "in-process MCP (memory streams); stdio via `python -m app.mcp_servers.run <server>`"}


@router.get("/mcp/calls")
def mcp_calls(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(McpToolCall).where(McpToolCall.user_id == user.id).order_by(McpToolCall.created_at.desc()).limit(100))
    return {"calls": [{"id": str(c.id), "server": c.server, "tool": c.tool, "version": c.tool_version, "agent": c.agent, "status": c.status,
                       "duration_ms": c.duration_ms, "arguments": c.arguments, "error": c.error, "at": c.created_at.isoformat()} for c in rows]}


@router.get("/approvals")
def approvals(user: CurrentUser, db: DB, status: str | None = None) -> dict:
    return {"actions": CONSEQUENTIAL_ACTIONS,
            "requests": [{"id": str(r.id), "action": r.action, "summary": r.summary, "status": r.status, "requested_by": r.requested_by,
                          "payload": r.payload, "result": r.result, "created_at": r.created_at.isoformat()} for r in list_requests(db, user.id, status)]}


class DecisionIn(BaseModel):
    approve: bool


@router.post("/approvals/{rid}/decision")
def decision(rid: uuid.UUID, body: DecisionIn, user: CurrentUser, db: DB) -> dict:
    """Only the authenticated user (never an agent or MCP tool) can reach this endpoint."""
    r = decide(db, user.id, rid, body.approve)
    return {"id": str(r.id), "status": r.status, "result": r.result}


@router.get("/governance/audit")
def audit_events(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(AuditEvent).where(AuditEvent.user_id == user.id).order_by(AuditEvent.created_at.desc()).limit(200))
    return {"events": [{"actor": e.actor, "action": e.action, "target": e.target, "detail": e.detail, "severity": e.severity,
                        "at": e.created_at.isoformat()} for e in rows]}


@router.get("/governance/summary")
def governance_summary(user: CurrentUser, db: DB) -> dict:
    denied = db.scalar(select(func.count()).select_from(McpToolCall).where(McpToolCall.user_id == user.id, McpToolCall.status == "denied"))
    total = db.scalar(select(func.count()).select_from(McpToolCall).where(McpToolCall.user_id == user.id))
    pending = len(list_requests(db, user.id, "pending"))
    return {"tool_calls": total, "denied_tool_calls": denied, "pending_approvals": pending,
            "controls": ["Static per-agent MCP tool allowlists", "Server-injected user identity on every tool call",
                         "Per-user tool rate limits and per-call timeouts", "Bounded agent plans and tool budgets",
                         "Prompt-injection neutralisation of external text", "Fact-checking of generated resumes and letters",
                         "Human approval for consequential actions", "Redacted audit log of every tool call"]}
