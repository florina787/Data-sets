"""Ask Flo, agent/tool registries and AI operations (observability, cost & capacity)."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.graph import ask
from backend import runtime as R
from backend.api.deps import Ctx, authorize, current, require, response_cache
from backend.config import ROOT, get_settings
from backend.db import models as m
from governance import audit
from harness.errors import LoadShed
from harness.registry import REGISTRY
from harness.resilience import all_breakers
from harness.runtime import get_harness
from harness.tools import TOOLS
from integrations.mock.adapters import MockMarketData
from observability.telemetry import get_telemetry

router = APIRouter(prefix="/api")


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=20000)
    context: dict = {}
    language: str | None = Field(None, pattern="^(en|fr|es|hi|ta|ko)$")
    purpose: str | None = Field(None, max_length=40)


@router.post("/ask")
def ask_flo(body: AskIn, ctx: Ctx = Depends(require("ask:use"))):
    rctx = R.run_context(ctx.store, ctx.principal, "ask", purpose=body.purpose)
    ctxd = {k: v for k, v in body.context.items() if k in ("chart_id", "page", "client_id", "portfolio_id", "filters", "draft_language")}
    try:
        return json.loads(json.dumps(ask(rctx, body.question, ctxd, body.language), default=str))
    except LoadShed as e:
        raise HTTPException(503, {"code": "LOAD-SHED", "message": str(e)}, headers={"Retry-After": "5"}) from e


@router.post("/ask/{workflow_id}/cancel")
def cancel(workflow_id: str, ctx: Ctx = Depends(require("ask:use"))):
    ok = get_harness().cancel(workflow_id)
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="workflow.cancel", resource_type="workflow",
                 resource_id=workflow_id, decision="allow" if ok else "noop")
    return {"workflow_id": workflow_id, "cancelled": ok}


@router.get("/agents")
def agents(ctx: Ctx = Depends(current)):
    roles = set(ctx.principal.roles)
    return {"agents": [{**a.spec.contract(), "available_to_you": bool(roles & a.spec.allowed_roles)} for a in REGISTRY.agents.values()],
            "supervisors": ["enterprise_supervisor", "executive_supervisor", "investment_supervisor", "wealth_supervisor",
                            "risk_compliance_supervisor", "ai_operations_supervisor"]}


@router.get("/tools")
def tools(ctx: Ctx = Depends(current)):
    return {"tools": TOOLS.catalog()}


# ------------------------------------------------------------------ AI operations
def _pct(vals: list[int], p: float) -> int:
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(p * (len(v) - 1)))]


@router.get("/aiops/overview")
def overview(include_synthetic: bool = True, ctx: Ctx = Depends(require("aiops:read"))):
    q = select(m.AgentTrace).where(m.AgentTrace.tenant_id == ctx.principal.tenant_id)
    if not include_synthetic:
        q = q.where(m.AgentTrace.synthetic.is_(False))
    rows = list(ctx.db.scalars(q))
    wf = defaultdict(lambda: {"cost": 0.0, "ok": True})
    per = defaultdict(lambda: {"runs": 0, "fail": 0, "lat": [], "tin": 0, "tout": 0, "cost": 0.0, "retries": 0, "cache": 0, "classes": defaultdict(int)})
    models = defaultdict(int)
    daily = defaultdict(lambda: {"runs": 0, "failures": 0, "cost": 0.0, "tokens": 0})
    tool_total = tool_fail = 0
    for r in rows:
        w = wf[r.workflow_id]
        w["cost"] += r.cost_usd
        w["ok"] = w["ok"] and r.status == "succeeded"
        a = per[r.agent_id]
        a["runs"] += 1
        a["fail"] += r.status == "failed"
        a["lat"].append(r.latency_ms)
        a["tin"] += r.tokens_in
        a["tout"] += r.tokens_out
        a["cost"] += r.cost_usd
        a["retries"] += r.retry_count
        a["cache"] += bool(r.cache_hit)
        if r.failure_class:
            a["classes"][r.failure_class] += 1
        models[r.model] += 1
        d = daily[r.started_at.date().isoformat()]
        d["runs"] += 1
        d["failures"] += r.status == "failed"
        d["cost"] += r.cost_usd
        d["tokens"] += r.tokens_in + r.tokens_out
        for t in r.tool_calls or []:
            tool_total += 1
            tool_fail += t.get("status") not in (None, "ok") or t.get("decision") == "deny"
    n_wf = len(wf)
    succ = [w for w in wf.values() if w["ok"]]
    total_cost = sum(w["cost"] for w in wf.values())
    h = get_harness()
    pending_jobs = ctx.db.query(m.Job).filter(m.Job.status == "queued").count()
    return {
        "totals": {"traces": len(rows), "workflows": n_wf, "synthetic_traces": sum(r.synthetic for r in rows), "live_traces": sum(not r.synthetic for r in rows),
                   "cost_usd": round(total_cost, 4), "cost_per_workflow": round(total_cost / n_wf, 6) if n_wf else 0,
                   "cost_per_successful_workflow": round(total_cost / len(succ), 6) if succ else None,
                   "success_rate": round(len(succ) / n_wf, 4) if n_wf else None, "tokens": sum(r.tokens_in + r.tokens_out for r in rows),
                   "cache_hit_rate_traces": round(sum(r.cache_hit for r in rows) / len(rows), 4) if rows else 0,
                   "tool_failure_rate": round(tool_fail / tool_total, 4) if tool_total else 0},
        "agents": sorted([{"agent": k, "runs": v["runs"], "failures": v["fail"], "failure_rate": round(v["fail"] / v["runs"], 4),
                           "p50_ms": _pct(v["lat"], 0.5), "p95_ms": _pct(v["lat"], 0.95), "tokens_in": v["tin"], "tokens_out": v["tout"],
                           "cost_usd": round(v["cost"], 4), "retries": v["retries"], "cache_hits": v["cache"], "failure_classes": dict(v["classes"])}
                          for k, v in per.items()], key=lambda x: -x["failure_rate"]),
        "models": dict(models), "daily": [{"date": k, **v} for k, v in sorted(daily.items())],
        "capacity": {"active_workflows": h.active, "max_concurrent_workflows": h.capacity, "concurrency_utilization": round(h.active / h.capacity, 4),
                     "job_queue_depth": pending_jobs, "agent_result_cache": h.cache.stats(), "response_cache": response_cache.stats()},
        "breakers": all_breakers(), "observability_mode": get_telemetry().mode,
        "note": "Historical traces flagged synthetic=true are generated demo data; live traces come from real executions in this deployment. "
                "Costs for the mock model are 0; synthetic historical costs use illustrative per-token prices."}


@router.get("/aiops/traces")
def traces(agent: str | None = None, status: str | None = None, live_only: bool = False, limit: int = Query(100, le=500),
           ctx: Ctx = Depends(require("aiops:read"))):
    q = select(m.AgentTrace).where(m.AgentTrace.tenant_id == ctx.principal.tenant_id)
    if agent:
        q = q.where(m.AgentTrace.agent_id == agent)
    if status:
        q = q.where(m.AgentTrace.status == status)
    if live_only:
        q = q.where(m.AgentTrace.synthetic.is_(False))
    rows = ctx.db.scalars(q.order_by(m.AgentTrace.started_at.desc()).limit(limit))
    return {"traces": [{c: (getattr(r, c).isoformat() if isinstance(getattr(r, c), datetime) else getattr(r, c))
                        for c in ("id", "workflow_id", "workflow_type", "agent_id", "agent_version", "model", "started_at", "latency_ms", "tokens_in",
                                  "tokens_out", "cost_usd", "status", "failure_class", "retry_count", "eval_score", "tool_calls", "approval_status",
                                  "policy_outcome", "cache_hit", "synthetic", "user_id")} for r in rows]}


@router.get("/aiops/workflows/{workflow_id}")
def workflow(workflow_id: str, ctx: Ctx = Depends(require("aiops:read"))):
    rows = list(ctx.db.scalars(select(m.AgentTrace).where(m.AgentTrace.workflow_id == workflow_id, m.AgentTrace.tenant_id == ctx.principal.tenant_id)
                               .order_by(m.AgentTrace.started_at)))
    if not rows:
        raise HTTPException(404, "workflow not found")
    nodes = [{"id": "enterprise_supervisor", "type": "supervisor"}]
    edges = []
    sups = set()
    for r in rows:
        spec = REGISTRY.agents.get(r.agent_id)
        sup = spec.spec.supervisor if spec else "unknown_supervisor"
        if sup not in sups:
            sups.add(sup)
            nodes.append({"id": sup, "type": "supervisor"})
            edges.append({"from": "enterprise_supervisor", "to": sup})
        nodes.append({"id": r.agent_id, "type": "agent", "status": r.status, "latency_ms": r.latency_ms, "failure_class": r.failure_class})
        edges.append({"from": sup, "to": r.agent_id})
        for t in r.tool_calls or []:
            tid = f"{r.agent_id}:{t.get('tool')}"
            nodes.append({"id": tid, "label": t.get("tool"), "type": "tool", "status": t.get("status") or t.get("decision")})
            edges.append({"from": r.agent_id, "to": tid})
    return {"workflow_id": workflow_id, "nodes": nodes, "edges": edges}


class FaultIn(BaseModel):
    mode: str = Field(pattern="^(none|down|slow)$")


@router.post("/aiops/faults/market-data")
def inject_fault(body: FaultIn, ctx: Ctx = Depends(require("aiops:manage"))):
    if get_settings().is_production:
        raise HTTPException(403, "fault injection disabled in production")
    MockMarketData.FAULTS.update({"mode": "down" if body.mode == "down" else "none", "latency_s": 4.0 if body.mode == "slow" else 0.0})
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="aiops.fault_injection", resource_type="adapter",
                 resource_id="market_data", decision="allow", details={"mode": body.mode})
    return {"market_data_fault": body.mode}


@router.post("/aiops/breakers/reset")
def reset(ctx: Ctx = Depends(require("aiops:manage"))):
    from harness.resilience import reset_breakers
    reset_breakers()
    return {"breakers": all_breakers()}


@router.get("/aiops/data-quality")
def data_quality(ctx: Ctx = Depends(require("aiops:read"))):
    from analytics.data_quality import run_checks
    return run_checks(ctx.adapters)


@router.get("/aiops/evals")
def evals(ctx: Ctx = Depends(require("aiops:read"))):
    out = {}
    for name in ("eval_report.json", "release_gate.json", "load_test_report.json"):
        p = ROOT / "var" / name
        out[name.replace(".json", "")] = json.loads(p.read_text()) if p.exists() else None
    return out


_ = (timedelta, authorize)
