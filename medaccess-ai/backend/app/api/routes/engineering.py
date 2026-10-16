"""Engineering, governance, telemetry and administration API (role-restricted)."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config.settings import PROJECT_DIR, get_settings
from app.copilot import llm
from app.database.session import DEMO_USERS, ROLE_PERMISSIONS, session_scope
from app.governance import approvals, audit, builds
from app.graphs import patient_graph, sdlc_graph
from app.harness.core import AGENTS, TOOLS, breaker_states, registry_snapshot, reset_breakers
from app.mcp.servers import mcp_catalog
from app.models import db as m
from app.sdlc_engine import architecture, monitoring, qa, rca, release, requirements, security_scan, simulation
from app.security.auth import Principal, require
from app.telemetry import metrics as tm
from app.telemetry.tracing import status as tracing_status

router = APIRouter(prefix="/api/v1")


# ------------------------------------------------------------------ agents & graphs
@router.get("/agents", tags=["agents"])
def agents(p: Principal = Depends(require("agents:read"))):
    return registry_snapshot()


@router.get("/agents/metrics", tags=["agents"])
def agent_metrics(p: Principal = Depends(require("agents:read"))):
    with session_scope() as s:
        rows = s.execute(select(m.AgentExecution.agent, m.AgentExecution.status, func.count(),
                                func.avg(m.AgentExecution.duration_ms))
                         .group_by(m.AgentExecution.agent, m.AgentExecution.status)).all()
        tools = s.execute(select(m.ToolExecution.tool, m.ToolExecution.status, func.count(),
                                 func.avg(m.ToolExecution.duration_ms))
                          .group_by(m.ToolExecution.tool, m.ToolExecution.status)).all()
        wfs = s.execute(select(m.WorkflowExecution.status, func.count()).group_by(m.WorkflowExecution.status)).all()
    by_agent: dict[str, dict] = {}
    for agent, status, n, avg in rows:
        d = by_agent.setdefault(agent, {"agent": agent, "executions": 0, "failures": 0, "avg_ms": 0.0})
        d["avg_ms"] = round((d["avg_ms"] * d["executions"] + (avg or 0) * n) / (d["executions"] + n), 2)
        d["executions"] += n
        if status != "completed":
            d["failures"] += n
    for d in by_agent.values():
        d["success_rate"] = round(1 - d["failures"] / d["executions"], 4) if d["executions"] else None
    return {"measured": True, "agents": sorted(by_agent.values(), key=lambda d: d["agent"]),
            "tools": [{"tool": t, "status": st, "count": n, "avg_ms": round(a or 0, 2)} for t, st, n, a in tools],
            "workflows": {st: n for st, n in wfs}, "circuit_breakers": breaker_states()}


@router.get("/graphs/patient", tags=["agents"])
def patient_graph_def(p: Principal = Depends(require("patient:search"))):
    g = patient_graph.build_graph().compile().get_graph()
    return {"mermaid": patient_graph.mermaid(),
            "nodes": [{"id": n, "agent": patient_graph.NODE_AGENT.get(n)} for n in g.nodes],
            "edges": [{"source": e.source, "target": e.target, "conditional": e.conditional} for e in g.edges]}


# ------------------------------------------------------------------ SDLC
class AnalyzeIn(BaseModel):
    requirement: str = Field(min_length=10, max_length=2000)


@router.get("/sdlc/requirements", tags=["sdlc"])
def sdlc_requirements(p: Principal = Depends(require("sdlc:read"))):
    with session_scope() as s:
        rows = s.query(m.SdlcArtifact).filter(m.SdlcArtifact.stage == "requirements_analysis") \
            .order_by(m.SdlcArtifact.created_at.desc()).limit(20).all()
        items = [r.content for r in rows]
    return {"demo_requirement": sdlc_graph.DEMO_REQUIREMENT,
            "demo_analysis": requirements.analyze(sdlc_graph.DEMO_REQUIREMENT), "recent": items}


@router.post("/sdlc/requirements/analyze", tags=["sdlc"])
def analyze(body: AnalyzeIn, p: Principal = Depends(require("sdlc:write"))):
    res = requirements.analyze(body.requirement)
    audit.record("REQUIREMENT_ANALYZED", p.user_id, {"id": res["id"], "ambiguities": len(res["ambiguities"])})
    return res


@router.get("/sdlc/architecture", tags=["sdlc"])
def arch(p: Principal = Depends(require("sdlc:read"))):
    return architecture.all_diagrams()


class TestRunIn(BaseModel):
    build_version: str | None = None
    ids: list[str] | None = None


@router.post("/sdlc/tests/run", tags=["sdlc"])
def run_tests(body: TestRunIn, p: Principal = Depends(require("sdlc:write"))):
    if body.build_version and body.build_version not in builds.BUILDS:
        raise HTTPException(422, "unknown build")
    rep = qa.run_suite(body.build_version, body.ids)
    tm.STORE.add("test_pass_rate", rep["pass_rate"] or 0, {"build": rep["build_version"]})
    audit.record("QA_SUITE_EXECUTED", p.user_id, {"build": rep["build_version"], "passed": rep["passed"],
                                                  "failed": rep["failed"]})
    return rep


@router.get("/sdlc/tests/pytest-report", tags=["sdlc"])
def pytest_report(p: Principal = Depends(require("sdlc:read"))):
    path = PROJECT_DIR / "sdlc" / "qa" / "pytest-report.xml"
    if not path.exists():
        return {"available": False, "hint": "Run `make test` to produce sdlc/qa/pytest-report.xml"}
    root = ET.parse(path).getroot()  # noqa: S314 - locally generated pytest report, not untrusted input
    suites = [root] if root.tag == "testsuite" else list(root)
    agg: Counter[str] = Counter()
    failures = []
    for su in suites:
        for k in ("tests", "failures", "errors", "skipped"):
            agg[k] += int(su.get(k, 0))
        for tc in su.iter("testcase"):
            if tc.find("failure") is not None or tc.find("error") is not None:
                failures.append(f"{tc.get('classname')}::{tc.get('name')}")
    return {"available": True, "generated": time.ctime(path.stat().st_mtime), **agg, "failed_tests": failures[:50],
            "passed": agg["tests"] - agg["failures"] - agg["errors"] - agg["skipped"]}


@router.post("/sdlc/security/scan", tags=["sdlc"])
def security(p: Principal = Depends(require("sdlc:write"))):
    res = security_scan.run_all()
    tm.STORE.add("security_open_findings", res["open_findings"])
    audit.record("SECURITY_SCAN", p.user_id, {"open_findings": res["open_findings"]})
    return res


class SimIn(BaseModel):
    volume: int = Field(200, ge=1, le=5000)
    build_version: str | None = None
    environment: str = "demo-production"
    outage_rate: float = Field(0.05, ge=0, le=1)
    seed: int = 7


@router.post("/sdlc/simulations", tags=["sdlc"])
def simulate(body: SimIn, p: Principal = Depends(require("sdlc:write"))):
    if body.environment not in builds.ENVIRONMENTS:
        raise HTTPException(422, "unknown environment")
    if body.build_version and body.build_version not in builds.BUILDS:
        raise HTTPException(422, "unknown build")
    return simulation.simulate(body.volume, body.build_version, body.environment, body.seed, body.outage_rate)


@router.get("/sdlc/anomalies", tags=["sdlc"])
def anomalies(p: Principal = Depends(require("sdlc:read"))):
    return {"items": monitoring.list_anomalies(), "rules": [r[0] for r in monitoring.RULES]}


@router.post("/sdlc/anomalies/detect", tags=["sdlc"])
def detect(window_minutes: int = Query(60, ge=1, le=1440), p: Principal = Depends(require("sdlc:write"))):
    return {"detected": monitoring.detect(since=time.time() - window_minutes * 60)}


class RcaIn(BaseModel):
    suspect_build: str
    baseline_build: str = "1.4.0"


@router.post("/sdlc/rca", tags=["sdlc"])
def run_rca(body: RcaIn, p: Principal = Depends(require("sdlc:write"))):
    if body.suspect_build not in builds.BUILDS or body.baseline_build not in builds.BUILDS:
        raise HTTPException(422, "unknown build")
    return rca.analyze(None, body.suspect_build, body.baseline_build)


@router.get("/sdlc/builds", tags=["sdlc"])
def get_builds(p: Principal = Depends(require("sdlc:read"))):
    return builds.state()


@router.get("/sdlc/releases", tags=["sdlc"])
def releases(p: Principal = Depends(require("sdlc:read"))):
    return {"releases": release.list_releases(), "builds": builds.state()}


class DeployIn(BaseModel):
    version: str
    environment: str
    approval_id: str | None = None


@router.post("/sdlc/releases/deploy", tags=["sdlc"])
def deploy(body: DeployIn, p: Principal = Depends(require("approval:release"))):
    if body.environment == "demo-production":
        if not body.approval_id:
            raise HTTPException(403, "Production deployment requires an approved PRODUCTION_DEPLOYMENT request.")
        try:
            a = approvals.get(body.approval_id)
        except approvals.ApprovalError as e:
            raise HTTPException(404, str(e)) from e
        if a["action_type"] != "PRODUCTION_DEPLOYMENT" or a["status"] != "APPROVED" or \
                a["payload"].get("version") != body.version:
            raise HTTPException(403, "Approval does not authorize this deployment.")
    try:
        d = builds.deploy(body.version, body.environment, p.user_id, body.approval_id)
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, str(e)) from e
    release.mark_deployed(body.version, body.environment, p.user_id)
    audit.record("DEPLOYMENT", p.user_id, d)
    return d


class DemoIn(BaseModel):
    requirement: str | None = Field(default=None, max_length=2000)
    simulation_volume: int = Field(200, ge=10, le=2000)


@router.post("/sdlc/demo/start", tags=["sdlc"])
def demo_start(body: DemoIn, p: Principal = Depends(require("sdlc:write"))):
    builds.reset()
    return sdlc_graph.start(p.user_id, body.requirement, body.simulation_volume)


@router.get("/sdlc/demo/{run_id}", tags=["sdlc"])
def demo_get(run_id: str, p: Principal = Depends(require("sdlc:read"))):
    r = sdlc_graph.get(run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@router.get("/sdlc/demo/{run_id}/traceability", tags=["sdlc"])
def demo_trace(run_id: str, p: Principal = Depends(require("sdlc:read"))):
    return {"run_id": run_id, "chain": sdlc_graph.traceability(run_id)}


@router.get("/sdlc/demo/{run_id}/artifacts/{stage}", tags=["sdlc"])
def demo_artifact(run_id: str, stage: str, p: Principal = Depends(require("sdlc:read"))):
    a = sdlc_graph.artifact(run_id, stage)
    if a is None:
        raise HTTPException(404, "artifact not found")
    return a


@router.get("/sdlc/runs", tags=["sdlc"])
def sdlc_runs(p: Principal = Depends(require("sdlc:read"))):
    with session_scope() as s:
        rows = s.query(m.WorkflowExecution).filter(m.WorkflowExecution.workflow_type == "sdlc_demo") \
            .order_by(m.WorkflowExecution.created_at.desc()).limit(20).all()
        return {"items": [{"run_id": r.id, "status": r.status, "user_id": r.user_id,
                           "created_at": r.created_at.isoformat()} for r in rows]}


# ------------------------------------------------------------------ telemetry
@router.get("/telemetry", tags=["telemetry"])
def telemetry(window_minutes: int = Query(60, ge=1, le=1440), p: Principal = Depends(require("telemetry:read"))):
    since = time.time() - window_minutes * 60
    snap = monitoring.health_snapshot(since)
    with session_scope() as s:
        usage = s.execute(select(m.ModelUsage.model, func.sum(m.ModelUsage.input_tokens),
                                 func.sum(m.ModelUsage.output_tokens), func.sum(m.ModelUsage.cached_tokens),
                                 func.sum(m.ModelUsage.estimated_cost_usd), func.count())
                          .group_by(m.ModelUsage.model)).all()
        wf_count = s.scalar(select(func.count()).select_from(m.WorkflowExecution)) or 0
        open_appr = s.scalar(select(func.count()).select_from(m.ApprovalRequest)
                             .where(m.ApprovalRequest.status == "PENDING")) or 0
    return {**snap, "window_minutes": window_minutes, "tracing": tracing_status(),
            "llm": {"configured": llm.available(), "usage": [
                {"model": mo, "input_tokens": i or 0, "output_tokens": o or 0, "cached_tokens": c or 0,
                 "estimated_cost_usd": round(cost or 0, 6), "calls": n} for mo, i, o, c, cost, n in usage],
                "note": "Cost is computed only when per-model prices are configured; deterministic mode uses 0 tokens."},
            "workflows_total": wf_count, "pending_approvals": open_appr, "builds": builds.state()["active"],
            "anomalies_open": sum(1 for a in monitoring.list_anomalies() if a["resolution_status"] == "OPEN")}


@router.get("/telemetry/token-benchmark", tags=["telemetry"])
def token_benchmark(p: Principal = Depends(require("telemetry:read"))):
    """Compares prompt payload size for a comparable workload with and without optimisation.

    Without an API key this measures characters actually assembled for the request (an
    approximation of tokens), and is labelled as such. Real token counts are reported from
    model_usage once an LLM is configured."""
    facts: dict = {"status": "COMPLETED", "summary": {"confirmed_count": 5, "potential_days_saved": 85},
             "recommendations": [{"facility": f"Facility {i}", "days": i, "km": i * 2.1, "status": "VERIFIED"}
                                 for i in range(10)], "message": "My name is Jane, I need an MRI near M5V 2T6"}
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i} " + "x" * 200} for i in range(12)]
    base = llm.prompt_payload_size(facts, history, optimized=False)
    opt = llm.prompt_payload_size({"summary": facts["summary"], "top3": facts["recommendations"][:3]}, history,
                                  optimized=True)
    return {"measurement": "characters of assembled prompt payload (proxy for tokens; not provider token counts)",
            "baseline_chars": base, "optimized_chars": opt,
            "savings_pct": round((base - opt) / base * 100, 2),
            "techniques": ["prompt caching of system prompt", "context compression", "retrieval filtering (top-3)",
                           "redaction", "deterministic tools (no LLM for decisions)"],
            "real_token_measurements_available": llm.available()}


@router.get("/metrics", include_in_schema=False)
def prom_metrics():
    return PlainTextResponse(tm.prometheus_text(), media_type="text/plain; version=0.0.4")


# ------------------------------------------------------------------ governance
@router.get("/governance/overview", tags=["governance"])
def governance(p: Principal = Depends(require("governance:read"))):
    s_ = get_settings()
    with session_scope() as s:
        appr = s.execute(select(m.ApprovalRequest.action_type, m.ApprovalRequest.status, func.count())
                         .group_by(m.ApprovalRequest.action_type, m.ApprovalRequest.status)).all()
        recent = s.scalars(select(m.ApprovalRequest).order_by(m.ApprovalRequest.created_at.desc()).limit(15)).all()
        provenance = s.execute(select(m.ProviderIntegration)).scalars().all()
        recent_rows = [{"id": r.id, "action_type": r.action_type, "status": r.status, "decided_by": r.decided_by,
                        "requesting_agent": r.requesting_agent, "created_at": r.created_at.isoformat()} for r in recent]
        prov = [{"id": i.id, "name": i.name, "adapter_type": i.adapter_type, "reliability": i.reliability,
                 "data_mode": i.data_mode, "authorized": i.authorized} for i in provenance]
    return {
        "agent_permissions": [{"agent": a.name, "title": a.title, "workflow": a.workflow, "tools": sorted(a.allowed_tools),
                               "version": a.version, "prompt_version": a.prompt_version, "uses_llm": a.uses_llm}
                              for a in AGENTS.values()],
        "tool_permissions": [{"tool": t.name, "permission": t.permission, "side_effect": t.side_effect,
                              "untrusted_output": t.untrusted_output, "mcp_server": t.mcp_server}
                             for t in TOOLS.values() if not t.name.startswith("qa.")],
        "role_permissions": {r: sorted(v) for r, v in ROLE_PERMISSIONS.items()},
        "workflow_versions": {"patient_search": "patient-graph-v1", "sdlc_demo": "sdlc-graph-v1"},
        "model_versions": {"router": s_.llm_router_model, "explainer": s_.llm_explainer_model,
                           "enabled": llm.available(), "prompt_version": llm.PROMPT_VERSION},
        "approvals": [{"action_type": a, "status": st, "count": n} for a, st, n in appr],
        "recent_approvals": recent_rows, "data_provenance": prov, "mcp_servers": mcp_catalog(),
        "release_history": builds.history(), "audit_chain": audit.verify_chain(),
    }


@router.get("/governance/audit", tags=["governance"])
def audit_events(workflow_id: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 p: Principal = Depends(require("governance:read"))):
    return {"items": audit.list_events(workflow_id, limit, offset)}


@router.get("/governance/audit/verify", tags=["governance"])
def audit_verify(p: Principal = Depends(require("governance:read"))):
    return audit.verify_chain()


# ------------------------------------------------------------------ admin
@router.post("/admin/demo/reset", tags=["admin"])
def demo_reset(p: Principal = Depends(require("admin:all"))):
    builds.reset()
    reset_breakers()
    tm.STORE.clear(synthetic_only=True)
    audit.record("DEMO_RESET", p.user_id, {})
    return {"reset": True, "builds": builds.state()["active"]}


@router.post("/admin/retention/run", tags=["admin"])
def retention(p: Principal = Depends(require("admin:all"))):
    from datetime import datetime, timedelta

    s_ = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=s_.search_retention_days)
    with session_scope() as s:
        n = s.query(m.SearchRequest).filter(m.SearchRequest.created_at < cutoff,
                                            m.SearchRequest.saved.is_(False)).delete()
    audit.record("RETENTION_RUN", p.user_id, {"search_requests_deleted": n, "cutoff": cutoff.isoformat()})
    return {"search_requests_deleted": n, "cutoff": cutoff.isoformat()}


@router.get("/admin/users", tags=["admin"])
def users(p: Principal = Depends(require("admin:all"))):
    return {"items": [{"id": u, "email": e, "name": n, "role": r} for u, e, n, r in DEMO_USERS]}
