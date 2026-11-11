"""Versioned REST API (/api/v1). Every endpoint authenticates, checks a permission and scopes data to the caller's tenant."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from florome import architecture_adapter
from florome.actions import service as actions
from florome.api.deps import get_ctx, get_db, get_principal, owned, require
from florome.connectors.base import ConnectorError
from florome.connectors.github import GitHubConnector
from florome.connectors.registry import PLATFORM_CATALOG
from florome.context import AppContext
from florome.governance.policy import effective_policy, validate_policy
from florome.mcp.gateway import MCPGatewayError
from florome.models import (
    ActionExecution,
    Approval,
    AuditEvent,
    Connection,
    CostRecord,
    Evidence,
    Incident,
    MCPServerRecord,
    MCPToolRecord,
    RCAReport,
    RemediationPlan,
    Resource,
    Tenant,
    ValidationResult,
    as_utc,
    utcnow,
)
from florome.rca import service as rca_service
from florome.security import audit
from florome.security.rbac import Principal

router = APIRouter(prefix="/api/v1")


def _iso(dt: Any) -> str | None:
    return as_utc(dt).isoformat() if dt else None


def _tenant(db: Session, p: Principal) -> Tenant:
    return db.get(Tenant, p.tenant_id)


# ----------------------------------------------------------------------------------------------------- identity

@router.get("/me", tags=["identity"])
def me(p: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict[str, Any]:
    t = _tenant(db, p)
    return {"user_id": p.user_id, "name": p.name, "roles": list(p.roles), "permissions": sorted(p.permissions),
            "tenant": {"id": t.id, "name": t.name, "mode": t.mode, "emergency_stop": t.emergency_stop}}


# ------------------------------------------------------------------------------------------ platforms & connections

@router.get("/platforms", tags=["platforms"])
def platforms(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    conns = db.scalars(select(Connection).where(Connection.tenant_id == p.tenant_id)).all()
    verified = {c.platform for c in conns if c.status == "verified"}
    return {"platforms": [{**e, "connected_and_verified": e["platform"] in verified} for e in PLATFORM_CATALOG]}


def _conn_out(c: Connection) -> dict[str, Any]:
    return {"id": c.id, "platform": c.platform, "connector_type": c.connector_type, "display_name": c.display_name, "status": c.status,
            "capabilities": c.capabilities, "verified_at": _iso(c.verified_at), "last_error": c.last_error, "is_demo": c.is_demo}


@router.get("/connections", tags=["connections"])
def connections(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_conn_out(c) for c in db.scalars(select(Connection).where(Connection.tenant_id == p.tenant_id))]


@router.post("/connections/{conn_id}/verify", tags=["connections"])
async def verify_connection(conn_id: str, p: Principal = Depends(require("connections:manage")), db: Session = Depends(get_db),
                            ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    c = owned(db, Connection, conn_id, p)
    if not ctx.registry.has(c.id):
        c.status, c.last_error = "failed", "No connector instance (credentials not configured in this process)"
    else:
        h = await ctx.registry.get(c.id).health()
        c.status = "verified" if h.ok else "failed"
        c.verified_at, c.last_error = (utcnow(), None) if h.ok else (c.verified_at, h.message)
    audit.record(db, p.tenant_id, p.user_id, "connection.verify", c.id, "success" if c.status == "verified" else "failed", {"status": c.status})
    return _conn_out(c)


@router.post("/connections/github", tags=["connections"], status_code=201)
async def add_github_connection(p: Principal = Depends(require("connections:manage")), db: Session = Depends(get_db),
                                ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    """Create a GitHub connection from server-side settings (FLOROME_GITHUB_REPOSITORY / FLOROME_GITHUB_TOKEN). Tokens are never accepted over the API."""
    s = ctx.settings
    if not s.github_repository:
        raise HTTPException(409, "FLOROME_GITHUB_REPOSITORY is not configured on the server")
    conn = Connection(tenant_id=p.tenant_id, platform="github", connector_type="github_rest", display_name=f"GitHub {s.github_repository}")
    connector = GitHubConnector(s.github_repository, s.github_token.get_secret_value() if s.github_token else None, s.github_api_url)
    conn.capabilities = sorted(c.value for c in connector.capabilities())
    db.add(conn)
    db.flush()
    ctx.registry.register(conn.id, connector)
    h = await connector.health()
    conn.status, conn.verified_at, conn.last_error = ("verified", utcnow(), None) if h.ok else ("failed", None, h.message)
    audit.record(db, p.tenant_id, p.user_id, "connection.create", conn.id, "success", {"platform": "github", "status": conn.status})
    return _conn_out(conn)


# -------------------------------------------------------------------------------------------- resources & topology

@router.get("/resources", tags=["resources"])
def resources(platform: str | None = None, kind: str | None = None, p: Principal = Depends(require("read")),
              db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(Resource).where(Resource.tenant_id == p.tenant_id)
    if platform:
        q = q.where(Resource.platform == platform)
    if kind:
        q = q.where(Resource.kind == kind)
    return [{"id": r.id, "name": r.name, "kind": r.kind, "platform": r.platform, "environment": r.environment, "source_ref": r.source_ref,
             "attributes": r.attributes, "connection_id": r.connection_id, "is_demo": r.is_demo} for r in db.scalars(q)]


@router.get("/topology", tags=["topology"])
async def topology(p: Principal = Depends(require("read")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    topo = rca_service.load_topology(db, p.tenant_id)
    overlay: dict[str, dict[str, Any]] = {}
    for inc in db.scalars(select(Incident).where(Incident.tenant_id == p.tenant_id, Incident.status != "resolved")):
        overlay[inc.primary_resource_id] = {"incident_id": inc.id, "role": "symptom"}
        rca = db.scalars(select(RCAReport).where(RCAReport.incident_id == inc.id).order_by(RCAReport.created_at.desc())).first()
        if rca:
            for a in rca.report.get("affected_systems", []):
                role = "root" if a["role"] == "root" else ("symptom" if a["resource_id"] == inc.primary_resource_id else "impacted")
                overlay[a["resource_id"]] = {"incident_id": inc.id, "role": role}
    nodes = []
    for rid, r in topo.resources.items():
        health = "unknown"
        if r.get("connection_id") and ctx.registry.has(r["connection_id"]):
            try:
                health = (await ctx.registry.get(r["connection_id"]).read_status(r["source_ref"])).get("health", "unknown")
            except ConnectorError:
                health = "unknown"
        nodes.append({"id": rid, **{k: r[k] for k in ("name", "kind", "platform", "environment")}, "health": health, "incident": overlay.get(rid)})
    return {"nodes": nodes, "edges": [{"source": s, "target": t, "kind": k} for s, t, k in topo.edges],
            "data_mode": _tenant(db, p).mode}


# ----------------------------------------------------------------------------------------------------- incidents

def _inc_out(i: Incident) -> dict[str, Any]:
    return {"id": i.id, "title": i.title, "severity": i.severity, "status": i.status, "primary_resource_id": i.primary_resource_id,
            "detected_at": _iso(i.detected_at), "resolved_at": _iso(i.resolved_at), "symptoms": i.symptoms, "is_demo": i.is_demo}


@router.get("/incidents", tags=["incidents"])
def incidents(status: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
              p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    q = select(Incident).where(Incident.tenant_id == p.tenant_id)
    if status:
        q = q.where(Incident.status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = db.scalars(q.order_by(Incident.detected_at.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [_inc_out(i) for i in items]}


@router.get("/incidents/{incident_id}", tags=["incidents"])
def incident(incident_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _inc_out(owned(db, Incident, incident_id, p))


@router.get("/incidents/{incident_id}/similar", tags=["incidents"])
def similar(incident_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return rca_service.similar_incidents(db, owned(db, Incident, incident_id, p))


# ----------------------------------------------------------------------------------------------------------- RCA

@router.post("/rca/{incident_id}", tags=["rca"], status_code=201)
async def run_rca(incident_id: str, p: Principal = Depends(require("rca:run")), db: Session = Depends(get_db),
                  ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    rca = await rca_service.run_rca(db, ctx, p, owned(db, Incident, incident_id, p))
    return {"id": rca.id, "report_hash": rca.report_hash, "created_at": _iso(rca.created_at), **rca.report}


@router.get("/rca/{incident_id}", tags=["rca"])
def latest_rca(incident_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    owned(db, Incident, incident_id, p)
    rca = db.scalars(select(RCAReport).where(RCAReport.incident_id == incident_id).order_by(RCAReport.created_at.desc())).first()
    if rca is None:
        raise HTTPException(404, "No RCA has been run for this incident")
    return {"id": rca.id, "report_hash": rca.report_hash, "created_at": _iso(rca.created_at),
            "integrity_ok": audit.sha256(rca.report) == rca.report_hash, **rca.report}


@router.get("/evidence/{evidence_id}", tags=["evidence"])
def evidence(evidence_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    e = owned(db, Evidence, evidence_id, p)
    return {"id": e.id, "incident_id": e.incident_id, "resource_id": e.resource_id, "kind": e.kind, "observed_at": _iso(e.observed_at),
            "summary": e.summary, "payload": e.payload, "source_system": e.source_system, "source_ref": e.source_ref,
            "collected_at": _iso(e.collected_at), "collected_by": e.collected_by, "content_hash": e.content_hash,
            "integrity_ok": rca_service.evidence_hash(e) == e.content_hash, "is_demo": e.is_demo,
            "provenance": "observed fact collected from a connector (not inferred)"}


# ------------------------------------------------------------------------------------------------- remediations

class PlanRequest(BaseModel):
    incident_id: str


def _plan_out(db: Session, pl: RemediationPlan) -> dict[str, Any]:
    approvals = db.scalars(select(Approval).where(Approval.plan_id == pl.id).order_by(Approval.created_at)).all()
    vals = db.scalars(select(ValidationResult).where(ValidationResult.plan_id == pl.id).order_by(ValidationResult.created_at)).all()
    return {"id": pl.id, "incident_id": pl.incident_id, "rca_id": pl.rca_id, "status": pl.status, "steps": pl.steps, "plan_hash": pl.plan_hash,
            "risk": pl.risk, "requires_approval": pl.requires_approval, "policy_decision": pl.policy_decision, "created_by": pl.created_by,
            "created_at": _iso(pl.created_at), "current_step": pl.current_step, "last_error": pl.last_error,
            "approvals": [{"id": a.id, "approver_id": a.approver_id, "decision": a.decision, "plan_hash": a.plan_hash, "comment": a.comment,
                           "created_at": _iso(a.created_at), "expires_at": _iso(a.expires_at)} for a in approvals],
            "validations": [{"id": v.id, "passed": v.passed, "checks": v.checks, "created_at": _iso(v.created_at)} for v in vals]}


def _action_error(exc: actions.ActionError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.post("/remediations", tags=["remediations"], status_code=201)
def create_remediation(body: PlanRequest, p: Principal = Depends(require("plan:create")), db: Session = Depends(get_db),
                       ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        plan = actions.create_plan(db, ctx, p, owned(db, Incident, body.incident_id, p))
    except actions.ActionError as exc:
        raise _action_error(exc) from exc
    return _plan_out(db, plan)


@router.get("/remediations", tags=["remediations"])
def list_remediations(incident_id: str | None = None, status: str | None = None, p: Principal = Depends(require("read")),
                      db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(RemediationPlan).where(RemediationPlan.tenant_id == p.tenant_id)
    if incident_id:
        q = q.where(RemediationPlan.incident_id == incident_id)
    if status:
        q = q.where(RemediationPlan.status == status)
    return [_plan_out(db, pl) for pl in db.scalars(q.order_by(RemediationPlan.created_at.desc()).limit(100))]


@router.get("/remediations/{plan_id}", tags=["remediations"])
def get_remediation(plan_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _plan_out(db, owned(db, RemediationPlan, plan_id, p))


class ApprovalRequest(BaseModel):
    plan_id: str
    decision: Literal["approve", "reject"]
    plan_hash: str = Field(min_length=64, max_length=64)
    nonce: str = Field(min_length=16, max_length=100)
    comment: str = Field(default="", max_length=2000)


@router.post("/approvals", tags=["approvals"], status_code=201)
def approve(body: ApprovalRequest, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
            ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    plan = owned(db, RemediationPlan, body.plan_id, p)
    try:
        actions.decide(db, ctx, p, plan, approve=body.decision == "approve", presented_hash=body.plan_hash, nonce=body.nonce, comment=body.comment)
    except actions.ActionError as exc:
        raise _action_error(exc) from exc
    return _plan_out(db, plan)


@router.get("/approvals/pending", tags=["approvals"])
def pending_approvals(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(RemediationPlan).where(RemediationPlan.tenant_id == p.tenant_id, RemediationPlan.status == "pending_approval")
    return [_plan_out(db, pl) for pl in db.scalars(q)]


class ExecuteRequest(BaseModel):
    plan_id: str


@router.post("/executions", tags=["executions"])
async def execute(body: ExecuteRequest, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
                  ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    plan = owned(db, RemediationPlan, body.plan_id, p)
    try:
        plan = await actions.execute(db, ctx, p, plan)
    except actions.ActionError as exc:
        raise _action_error(exc) from exc
    return _plan_out(db, plan)


@router.get("/executions", tags=["executions"])
def executions(plan_id: str | None = None, limit: int = Query(100, ge=1, le=500), p: Principal = Depends(require("read")),
               db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(ActionExecution).where(ActionExecution.tenant_id == p.tenant_id)
    if plan_id:
        q = q.where(ActionExecution.plan_id == plan_id)
    return [{"id": x.id, "plan_id": x.plan_id, "step_index": x.step_index, "action_id": x.action_id, "target_resource_id": x.target_resource_id,
             "params": x.params, "status": x.status, "attempts": x.attempts, "started_at": _iso(x.started_at), "finished_at": _iso(x.finished_at),
             "result": x.result, "verification": x.verification, "error": x.error, "executed_by": x.executed_by}
            for x in db.scalars(q.order_by(ActionExecution.started_at.desc()).limit(limit))]


@router.get("/actions", tags=["actions"])
def action_catalog(p: Principal = Depends(require("read")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> list[dict[str, Any]]:
    out = []
    for c in db.scalars(select(Connection).where(Connection.tenant_id == p.tenant_id)):
        if ctx.registry.has(c.id):
            try:
                specs = ctx.registry.get(c.id).list_actions()
            except ConnectorError:
                specs = []
            out += [{"connection_id": c.id, "connector_type": c.connector_type, "simulated": c.is_demo, **s.public()} for s in specs]
    return out


# ---------------------------------------------------------------------------------------------------------- MCP

def _tool_out(t: MCPToolRecord) -> dict[str, Any]:
    return {"id": t.id, "server_id": t.server_id, "name": t.name, "description": t.description, "input_schema": t.input_schema,
            "access": t.access, "enabled": t.enabled, "quarantine_reason": t.quarantine_reason, "schema_hash": t.schema_hash}


def _mcp_error(exc: MCPGatewayError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("/mcp/servers", tags=["mcp"])
def mcp_servers(p: Principal = Depends(require("read")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    servers = db.scalars(select(MCPServerRecord).where(MCPServerRecord.tenant_id == p.tenant_id)).all()
    return {"allow_list": sorted(ctx.settings.mcp_allowlist()),
            "servers": [{"id": s.id, "name": s.name, "transport": s.transport, "status": s.status, "server_info": s.server_info,
                         "last_checked": _iso(s.last_checked), "last_error": s.last_error} for s in servers]}


class RegisterServer(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/mcp/servers", tags=["mcp"], status_code=201)
def register_server(body: RegisterServer, p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db),
                    ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        s = ctx.mcp.register(db, p, body.name)
    except MCPGatewayError as exc:
        db.commit()  # keep the audit record of the denial
        raise _mcp_error(exc) from exc
    return {"id": s.id, "name": s.name, "status": s.status}


@router.post("/mcp/servers/{server_id}/discover", tags=["mcp"])
async def discover(server_id: str, p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db),
                   ctx: AppContext = Depends(get_ctx)) -> list[dict[str, Any]]:
    s = owned(db, MCPServerRecord, server_id, p)
    try:
        tools = await ctx.mcp.discover(db, p, s)
    except MCPGatewayError as exc:
        db.commit()
        raise _mcp_error(exc) from exc
    return [_tool_out(t) for t in tools]


@router.post("/mcp/servers/{server_id}/health", tags=["mcp"])
async def mcp_health(server_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db),
                     ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    return await ctx.mcp.health(db, owned(db, MCPServerRecord, server_id, p))


@router.get("/mcp/tools", tags=["mcp"])
def mcp_tools(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_tool_out(t) for t in db.scalars(select(MCPToolRecord).where(MCPToolRecord.tenant_id == p.tenant_id))]


@router.post("/mcp/tools/{tool_id}/enable", tags=["mcp"])
def enable_tool(tool_id: str, p: Principal = Depends(require("mcp:manage")), db: Session = Depends(get_db),
                ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        return _tool_out(ctx.mcp.enable_tool(db, p, owned(db, MCPToolRecord, tool_id, p)))
    except MCPGatewayError as exc:
        db.commit()
        raise _mcp_error(exc) from exc


class InvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.post("/mcp/tools/{tool_id}/invoke", tags=["mcp"])
async def invoke_tool(tool_id: str, body: InvokeRequest, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
                      ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    tool = owned(db, MCPToolRecord, tool_id, p)
    server = owned(db, MCPServerRecord, tool.server_id, p)
    try:
        return await ctx.mcp.invoke(db, p, server, tool, body.arguments)
    except MCPGatewayError as exc:
        db.commit()
        raise _mcp_error(exc) from exc


# --------------------------------------------------------------------------------------------------- governance

@router.get("/governance/policy", tags=["governance"])
def get_policy(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    t = _tenant(db, p)
    return {"policy": effective_policy(t.policy), "emergency_stop": t.emergency_stop}


@router.put("/governance/policy", tags=["governance"])
def put_policy(body: dict[str, Any], p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)) -> dict[str, Any]:
    t = _tenant(db, p)
    new = effective_policy({**t.policy, **body})
    errs = validate_policy(new)
    if errs:
        raise HTTPException(422, "; ".join(errs))
    t.policy = new
    audit.record(db, p.tenant_id, p.user_id, "governance.policy.update", t.id, "success", {"policy": new})
    return {"policy": new, "emergency_stop": t.emergency_stop}


class EmergencyStop(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=500)


@router.post("/governance/emergency-stop", tags=["governance"])
def emergency_stop(body: EmergencyStop, p: Principal = Depends(require("governance:manage")), db: Session = Depends(get_db)) -> dict[str, Any]:
    t = _tenant(db, p)
    t.emergency_stop = body.active
    audit.record(db, p.tenant_id, p.user_id, "governance.emergency_stop", t.id, "success", {"active": body.active, "reason": body.reason})
    return {"emergency_stop": t.emergency_stop}


@router.get("/governance/audit", tags=["governance"])
def audit_log(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), action: str | None = None,
              p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    q = select(AuditEvent).where(AuditEvent.tenant_id == p.tenant_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditEvent.seq.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [{"id": e.id, "seq": e.seq, "at": _iso(e.at), "actor": e.actor, "action": e.action, "target": e.target,
                                       "outcome": e.outcome, "detail": e.detail, "hash": e.hash} for e in rows]}


@router.get("/governance/audit/verify", tags=["governance"])
def audit_verify(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    return audit.verify_chain(db, p.tenant_id)


# ------------------------------------------------------------------------------------------------------- finops

@router.get("/finops/costs", tags=["finops"])
def costs(period: str | None = None, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(CostRecord).where(CostRecord.tenant_id == p.tenant_id)).all()
    periods = sorted({r.period for r in rows})
    sel = period or (periods[-1] if periods else None)
    by_period: dict[str, float] = defaultdict(float)
    for r in rows:
        by_period[r.period] += r.amount
    links: dict[tuple[str, str], float] = defaultdict(float)
    for r in (r for r in rows if r.period == sel):
        chain = [f"provider:{r.provider}", f"account:{r.account}", f"bu:{r.business_unit}", f"app:{r.application}",
                 f"ai:{r.ai_component}", f"outcome:{r.outcome}"]
        for a, b in zip(chain, chain[1:]):
            links[(a, b)] += r.amount
    nodes = sorted({n for pair in links for n in pair})
    return {"period": sel, "periods": periods, "currency": "USD", "is_demo": any(r.is_demo for r in rows),
            "totals_by_period": [{"period": k, "amount": round(v, 2)} for k, v in sorted(by_period.items())],
            "sankey": {"nodes": [{"name": n} for n in nodes], "links": [{"source": a, "target": b, "value": round(v, 2)} for (a, b), v in links.items()]},
            "note": "Synthetic demo cost records." if any(r.is_demo for r in rows) else "From connected cost sources."}


# ------------------------------------------------------------------------------------------------- architecture

@router.get("/architecture/scenarios", tags=["architecture"])
def arch_scenarios(p: Principal = Depends(require("read"))) -> list[dict[str, Any]]:
    try:
        return architecture_adapter.list_scenarios()
    except architecture_adapter.AdvisorUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/architecture/scenarios/{scenario_id}/assessment", tags=["architecture"])
def arch_assess(scenario_id: str, p: Principal = Depends(require("read"))) -> dict[str, Any]:
    try:
        return architecture_adapter.assess_scenario(scenario_id)
    except architecture_adapter.AdvisorUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # Project B raises its own ScenarioNotFound
        if type(exc).__name__ == "ScenarioNotFound":
            raise HTTPException(404, f"Unknown scenario '{scenario_id}'") from exc
        raise


# ---------------------------------------------------------------------------------------------------- analytics

@router.get("/analytics/summary", tags=["analytics"])
def summary(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    t = p.tenant_id
    conns = db.scalars(select(Connection).where(Connection.tenant_id == t)).all()
    incs = db.scalars(select(Incident).where(Incident.tenant_id == t)).all()
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.tenant_id == t)).all()
    rcas = db.scalars(select(RCAReport).where(RCAReport.tenant_id == t)).all()
    execs = db.scalars(select(ActionExecution).where(ActionExecution.tenant_id == t)).all()
    latest_rca = {}
    for r in sorted(rcas, key=lambda r: as_utc(r.created_at)):
        latest_rca[r.incident_id] = r.conclusion_status
    cost = db.scalars(select(CostRecord).where(CostRecord.tenant_id == t)).all()
    periods = sorted({c.period for c in cost})
    tenant = _tenant(db, p)
    return {
        "data_mode": tenant.mode, "emergency_stop": tenant.emergency_stop,
        "connections": {"verified": sum(c.status == "verified" for c in conns), "total": len(conns),
                        "platforms_verified": sorted({c.platform for c in conns if c.status == "verified"})},
        "incidents": {"open": sum(i.status != "resolved" for i in incs), "resolved": sum(i.status == "resolved" for i in incs),
                      "by_status": {s: sum(i.status == s for i in incs) for s in {i.status for i in incs}}},
        "rca": {"by_conclusion": {s: list(latest_rca.values()).count(s) for s in set(latest_rca.values())}},
        "remediation": {"pending_approval": sum(pl.status == "pending_approval" for pl in plans),
                        "by_status": {s: sum(pl.status == s for pl in plans) for s in {pl.status for pl in plans}}},
        "executions": {"succeeded": sum(x.status == "succeeded" for x in execs), "failed": sum(x.status in ("failed", "timed_out") for x in execs)},
        "cost": {"period": periods[-1] if periods else None,
                 "amount": round(sum(c.amount for c in cost if periods and c.period == periods[-1]), 2),
                 "previous": round(sum(c.amount for c in cost if len(periods) > 1 and c.period == periods[-2]), 2),
                 "is_demo": any(c.is_demo for c in cost)},
    }


# ---------------------------------------------------------------------------------------------------------- demo

@router.post("/demo/reset", tags=["demo"])
async def demo_reset(p: Principal = Depends(require("demo:reset")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    from florome.demo.seed import DEMO_TENANTS, seed_demo

    if _tenant(db, p).mode != "demo" or p.tenant_id not in DEMO_TENANTS:
        raise HTTPException(409, "Only demo tenants can be reset")
    for c in db.scalars(select(Connection).where(Connection.tenant_id == p.tenant_id)):
        ctx.registry.remove(c.id)
    await seed_demo(db, ctx, p.tenant_id)
    return {"reset": p.tenant_id}


@router.get("/health", tags=["health"])
def health(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    s = ctx.settings
    return {"status": "ok", "default_mode": s.default_mode, "database": s.database_url.split(":", 1)[0]}
