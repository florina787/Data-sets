"""Florome Shield REST API (/api/v1/shield). Every route authenticates, and every state change passes control.authorize."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.api.deps import get_ctx, get_db, get_principal, owned, require
from florome.context import AppContext
from florome.models import MCPServerRecord, Tenant, as_utc
from florome.security.rbac import Principal
from florome.shield import evaluation, mcp_security, research
from florome.shield.containment.scenarios import SCENARIOS
from florome.shield.containment.supervisor import run_scenario
from florome.shield.control import ShieldDenied, tool_path
from florome.shield.models import (
    AgentExecution,
    BenchmarkRun,
    CodeRelationship,
    CodeSymbol,
    ContainmentEvent,
    FindingEvidence,
    MCPServerManifest,
    RemediationPatch,
    Repository,
    RepositorySnapshot,
    ScanRun,
    SecurityHypothesis,
    SecurityPolicyDecision,
    TrustBoundary,
    VerificationRun,
    VulnerabilityFinding,
)
from florome.shield.range.sandbox import netns_available

router = APIRouter(prefix="/api/v1/shield", tags=["shield"])


def _iso(dt: Any) -> str | None:
    return as_utc(dt).isoformat() if dt else None


def _err(exc: Exception) -> HTTPException:
    return HTTPException(getattr(exc, "status", 400), str(exc))


# ------------------------------------------------------------------------------------------------- overview

@router.get("/summary")
def summary(p: Principal = Depends(require("read")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    t = p.tenant_id
    hyps = db.scalars(select(SecurityHypothesis).where(SecurityHypothesis.tenant_id == t)).all()
    findings = db.scalars(select(VulnerabilityFinding).where(VulnerabilityFinding.tenant_id == t)).all()
    cont = db.scalars(select(ContainmentEvent).where(ContainmentEvent.tenant_id == t)).all()
    patches = db.scalars(select(RemediationPatch).where(RemediationPatch.tenant_id == t)).all()
    decisions = db.scalars(select(SecurityPolicyDecision).where(SecurityPolicyDecision.tenant_id == t)).all()
    s = ctx.settings
    return {
        "repositories": db.query(Repository).filter_by(tenant_id=t).count(),
        "hypotheses": {"total": len(hyps), "by_status": dict(Counter(h.status for h in hyps))},
        "findings": {"confirmed": sum(f.status == "confirmed" for f in findings),
                     "by_severity": dict(Counter(f.severity for f in findings if f.status == "confirmed")),
                     "by_class": dict(Counter(h.vuln_class for h in hyps if h.status == "confirmed")),
                     "incidents_opened": sum(1 for f in findings if f.incident_id)},
        "patches": dict(Counter(x.status for x in patches)),
        "containment": {"sessions": len(cont), "contained": sum(c.outcome == "contained" for c in cont),
                        "by_violation": dict(Counter(c.violation for c in cont if c.violation))},
        "policy": {"decisions": len(decisions), "denied": sum(not d.allowed for d in decisions)},
        "controls": {
            "opengrep": bool(tool_path(s, "opengrep")), "trivy": bool(tool_path(s, "trivy")), "opa": bool(tool_path(s, "opa")),
            "opa_mode": s.shield_opa_mode, "network_namespace": netns_available(), "emergency_stop": db.get(Tenant, t).emergency_stop,
            "authorized_roots": len(s.shield_authorized_roots), "rate_limit_per_minute": s.rate_limit_per_minute,
        },
        "data_class": "benchmark (synthetic training target)",
    }


# --------------------------------------------------------------------------------------------- repositories

class RegisterRepo(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")
    path: str = Field(min_length=1, max_length=1000)


def _repo_out(db: Session, r: Repository) -> dict[str, Any]:
    snap = db.scalars(select(RepositorySnapshot).where(RepositorySnapshot.repository_id == r.id).order_by(RepositorySnapshot.created_at.desc())).first()
    return {"id": r.id, "name": r.name, "data_class": r.data_class, "authorized_by": r.authorized_by, "authorized_at": _iso(r.authorized_at),
            "latest_snapshot": {"id": snap.id, "commit": snap.commit, "dirty": snap.dirty, "tree_hash": snap.tree_hash, "stats": snap.stats,
                                "created_at": _iso(snap.created_at)} if snap else None}


@router.get("/repositories")
def repositories(p: Principal = Depends(require("read")), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    roots = [Path(r) for r in ctx.settings.shield_authorized_roots]
    candidates = sorted({str(d) for r in roots if r.is_dir() for d in r.iterdir() if d.is_dir()})
    return {"authorized_targets": [{"name": Path(c).name, "path": c} for c in candidates],
            "repositories": [_repo_out(db, r) for r in db.scalars(select(Repository).where(Repository.tenant_id == p.tenant_id))]}


@router.post("/repositories", status_code=201)
def register(body: RegisterRepo, p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        return _repo_out(db, research.register_repository(db, ctx.settings, p, body.name, body.path))
    except ShieldDenied as exc:
        raise _err(exc) from exc


@router.post("/repositories/{repo_id}/ingest")
def ingest(repo_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        research.ingest(db, ctx.settings, p, owned(db, Repository, repo_id, p))
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return _repo_out(db, owned(db, Repository, repo_id, p))


@router.post("/repositories/{repo_id}/scan")
def scan(repo_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    repo = owned(db, Repository, repo_id, p)
    snap = db.scalars(select(RepositorySnapshot).where(RepositorySnapshot.repository_id == repo.id).order_by(RepositorySnapshot.created_at.desc())).first()
    if snap is None:
        raise HTTPException(409, "Ingest the repository before scanning")
    try:
        run = research.scan(db, ctx.settings, p, repo, snap)
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return {"id": run.id, "status": run.status, "tools": run.tools, "hypotheses": db.query(SecurityHypothesis).filter_by(scan_id=run.id).count()}


@router.get("/repositories/{repo_id}/graph")
def graph(repo_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = owned(db, Repository, repo_id, p)
    snap = db.scalars(select(RepositorySnapshot).where(RepositorySnapshot.repository_id == repo.id).order_by(RepositorySnapshot.created_at.desc())).first()
    if snap is None:
        return {"nodes": [], "edges": [], "snapshot": None}
    syms = db.scalars(select(CodeSymbol).where(CodeSymbol.snapshot_id == snap.id)).all()
    rels = db.scalars(select(CodeRelationship).where(CodeRelationship.snapshot_id == snap.id)).all()
    tbs = {b.route_symbol_id: b.kind for b in db.scalars(select(TrustBoundary).where(TrustBoundary.snapshot_id == snap.id))}
    hyps = db.scalars(select(SecurityHypothesis).where(SecurityHypothesis.snapshot_id == snap.id)).all()
    by_sym: dict[str, list[dict[str, str]]] = {}
    for h in hyps:
        by_sym.setdefault(h.symbol_id, []).append({"id": h.id, "class": h.vuln_class, "status": h.status})
    used = {r.source_id for r in rels} | {r.target_id for r in rels}
    nodes = [{"id": s.id, "kind": s.kind, "name": s.name, "qualname": s.qualname, "file": s.file, "line": s.start_line,
              "route": s.attrs.get("route"), "trust_boundary": tbs.get(s.id), "auth_provider": s.attrs.get("auth_provider", False),
              "findings": by_sym.get(s.id, [])} for s in syms if s.id in used or s.kind != "external"]
    return {"snapshot": {"id": snap.id, "commit": snap.commit, "tree_hash": snap.tree_hash, "analyzer": snap.analyzer},
            "nodes": nodes, "edges": [{"id": r.id, "kind": r.kind, "source": r.source_id, "target": r.target_id, "file": r.file, "line": r.line,
                                        "attrs": r.attrs, "provenance": r.provenance} for r in rels]}


# --------------------------------------------------------------------------------------------- hypotheses

def _hyp_out(db: Session, h: SecurityHypothesis, detail: bool = False) -> dict[str, Any]:
    f = db.scalars(select(VulnerabilityFinding).where(VulnerabilityFinding.hypothesis_id == h.id)).first()
    out = {"id": h.id, "vuln_class": h.vuln_class, "function": h.function, "file": h.file, "line": h.line, "status": h.status,
           "status_basis": h.status_basis, "assumption": h.assumption, "weakness": h.weakness, "verification_method": h.verification_method,
           "supporting": h.supporting, "contradicting": h.contradicting, "fingerprint": h.fingerprint, "model_provenance": h.model_provenance,
           "severity": f.severity if f else None, "severity_basis": f.severity_basis if f else None, "incident_id": f.incident_id if f else None}
    if detail:
        runs = db.scalars(select(VerificationRun).where(VerificationRun.hypothesis_id == h.id).order_by(VerificationRun.created_at)).all()
        out["verification_runs"] = [{"id": r.id, "purpose": r.purpose, "attempt": r.attempt, "method": r.method, "outcome": r.outcome,
                                     "isolation": r.isolation, "transcript": r.transcript, "seconds": round(r.seconds, 3),
                                     "created_at": _iso(r.created_at)} for r in runs]
        out["patches"] = [{"id": x.id, "status": x.status, "diff": x.diff, "generator": x.generator, "regression": x.regression,
                           "requested_by": x.requested_by, "reviewed_by": x.reviewed_by, "patch_hash": x.patch_hash}
                          for x in db.scalars(select(RemediationPatch).where(RemediationPatch.hypothesis_id == h.id))]
        snap = db.get(RepositorySnapshot, h.snapshot_id)
        repo = db.get(Repository, snap.repository_id)
        src = Path(repo.root) / h.file
        if src.is_file() and src.resolve().is_relative_to(Path(repo.root).resolve()):
            lines = src.read_text(errors="replace").splitlines()
            start = max(0, h.line - 8)
            out["source"] = {"start_line": start + 1, "lines": lines[start:h.line + 6], "highlight": h.line, "commit": snap.commit}
    return out


@router.get("/hypotheses")
def hypotheses(repository_id: str | None = None, status: str | None = None, limit: int = Query(200, ge=1, le=500),
               p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(SecurityHypothesis).where(SecurityHypothesis.tenant_id == p.tenant_id)
    if repository_id:
        snaps = [s.id for s in db.scalars(select(RepositorySnapshot).where(RepositorySnapshot.repository_id == repository_id,
                                                                            RepositorySnapshot.tenant_id == p.tenant_id))]
        q = q.where(SecurityHypothesis.snapshot_id.in_(snaps))
    if status:
        q = q.where(SecurityHypothesis.status == status)
    return [_hyp_out(db, h) for h in db.scalars(q.order_by(SecurityHypothesis.created_at.desc()).limit(limit))]


@router.get("/hypotheses/{hyp_id}")
def hypothesis(hyp_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    return _hyp_out(db, owned(db, SecurityHypothesis, hyp_id, p), detail=True)


@router.post("/hypotheses/{hyp_id}/verify")
def verify(hyp_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    h = owned(db, SecurityHypothesis, hyp_id, p)
    try:
        research.verify(db, ctx.settings, p, h)
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return _hyp_out(db, h, detail=True)


@router.post("/hypotheses/{hyp_id}/patch")
def patch(hyp_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    h = owned(db, SecurityHypothesis, hyp_id, p)
    try:
        research.generate_patch(db, ctx.settings, p, h)
    except (ShieldDenied, research.ResearchError) as exc:
        raise _err(exc) from exc
    return _hyp_out(db, h, detail=True)


class PatchReview(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    patch_hash: str = Field(min_length=64, max_length=64)


@router.post("/patches/{patch_id}/review")
def review(patch_id: str, body: PatchReview, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
           ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    x = owned(db, RemediationPatch, patch_id, p)
    try:
        research.review_patch(db, ctx.settings, p, x, body.decision == "approve", body.patch_hash)
    except (ShieldDenied, research.ResearchError) as exc:
        raise _err(exc) from exc
    return {"id": x.id, "status": x.status, "reviewed_by": x.reviewed_by}


@router.get("/evidence")
def evidence(scan_id: str | None = None, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(FindingEvidence).where(FindingEvidence.tenant_id == p.tenant_id)
    if scan_id:
        q = q.where(FindingEvidence.scan_id == scan_id)
    return [{"id": e.id, "tool": e.tool, "tool_version": e.tool_version, "rule_id": e.rule_id, "vuln_class": e.vuln_class, "cwe": e.cwe,
             "severity": e.severity, "file": e.file, "line": e.line, "message": e.message, "fingerprint": e.fingerprint} for e in db.scalars(q.limit(500))]


@router.get("/scans")
def scans(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": r.id, "status": r.status, "tools": r.tools, "started_by": r.started_by, "started_at": _iso(r.started_at),
             "finished_at": _iso(r.finished_at)} for r in db.scalars(select(ScanRun).where(ScanRun.tenant_id == p.tenant_id).order_by(ScanRun.started_at.desc()))]


# ---------------------------------------------------------------------------------------------- agents & range

@router.get("/agents")
def agents(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> dict[str, Any]:
    execs = db.scalars(select(AgentExecution).where(AgentExecution.tenant_id == p.tenant_id).order_by(AgentExecution.created_at.desc()).limit(200)).all()
    return {"registry": research.AGENTS,
            "executions": [{"id": e.id, "agent": e.agent, "subject": e.subject, "status": e.status, "tools": e.tools_used,
                            "seconds": round(e.seconds, 3), "summary": e.output_summary, "error": e.error, "at": _iso(e.created_at)} for e in execs]}


@router.get("/range/runs")
def range_runs(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(VerificationRun).where(VerificationRun.tenant_id == p.tenant_id).order_by(VerificationRun.created_at.desc()).limit(300)).all()
    return [{"id": r.id, "hypothesis_id": r.hypothesis_id, "purpose": r.purpose, "method": r.method, "attempt": r.attempt, "outcome": r.outcome,
             "seconds": round(r.seconds, 3), "network_namespace": r.isolation.get("network_namespace"), "at": _iso(r.created_at)} for r in rows]


@router.get("/containment/scenarios")
def scenarios(p: Principal = Depends(require("read"))) -> list[dict[str, str]]:
    return [{"id": k, "description": v["description"], "expected": v["expected"], "code": v["code"]} for k, v in SCENARIOS.items()]


class ContainmentRequest(BaseModel):
    scenario: str


@router.post("/containment/run")
def containment_run(body: ContainmentRequest, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
                    ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    if body.scenario not in SCENARIOS:
        raise HTTPException(404, "Unknown scenario")
    try:
        e = run_scenario(db, ctx.settings, p, body.scenario)
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return _cont_out(e)


def _cont_out(e: ContainmentEvent) -> dict[str, Any]:
    return {"id": e.id, "session_id": e.session_id, "scenario": e.scenario, "violation": e.violation, "outcome": e.outcome,
            "actions_taken": e.actions_taken, "forensics": e.forensics, "at": _iso(e.created_at)}


@router.get("/containment/events")
def containment_events(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(ContainmentEvent).where(ContainmentEvent.tenant_id == p.tenant_id).order_by(ContainmentEvent.created_at.desc()).limit(200)
    return [_cont_out(e) for e in db.scalars(q)]


# ------------------------------------------------------------------------------------------------------ MCP

@router.get("/mcp/manifests")
def manifests(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    out = []
    for s in db.scalars(select(MCPServerRecord).where(MCPServerRecord.tenant_id == p.tenant_id)):
        m = db.scalars(select(MCPServerManifest).where(MCPServerManifest.server_id == s.id)).first()
        out.append({"server_id": s.id, "server": s.name, "status": s.status, "pinned": bool(m and m.manifest_hash),
                    "manifest_hash": m.manifest_hash if m else None, "identity": m.server_identity if m else None,
                    "revoked": bool(m and m.revoked), "revoked_reason": m.revoked_reason if m else None})
    return out


@router.post("/mcp/servers/{server_id}/pin")
async def pin_manifest(server_id: str, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
                       ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        m = await mcp_security.pin(db, ctx, p, owned(db, MCPServerRecord, server_id, p))
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return {"manifest_hash": m.manifest_hash, "identity": m.server_identity, "revoked": m.revoked}


class RevokeRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


@router.post("/mcp/servers/{server_id}/revoke")
def revoke_server(server_id: str, body: RevokeRequest, p: Principal = Depends(get_principal), db: Session = Depends(get_db),
                  ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        m = mcp_security.revoke(db, ctx, p, owned(db, MCPServerRecord, server_id, p), body.reason)
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return {"revoked": m.revoked, "reason": m.revoked_reason}


# ------------------------------------------------------------------------------------------ policy & evaluation

@router.get("/policy/decisions")
def decisions(limit: int = Query(100, ge=1, le=500), p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    q = select(SecurityPolicyDecision).where(SecurityPolicyDecision.tenant_id == p.tenant_id).order_by(SecurityPolicyDecision.created_at.desc()).limit(limit)
    return [{"id": d.id, "actor": d.actor, "action": d.action, "resource": d.resource, "allowed": d.allowed, "engines": d.engines,
             "at": _iso(d.created_at)} for d in db.scalars(q)]


@router.post("/evaluation/run")
def run_evaluation(p: Principal = Depends(get_principal), db: Session = Depends(get_db), ctx: AppContext = Depends(get_ctx)) -> list[dict[str, Any]]:
    try:
        evaluation.run(db, ctx.settings, p)
    except ShieldDenied as exc:
        raise _err(exc) from exc
    return evaluations(p, db)


@router.get("/evaluation")
def evaluations(p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(BenchmarkRun).where(BenchmarkRun.tenant_id == p.tenant_id).order_by(BenchmarkRun.created_at.desc()).limit(40)).all()
    return [{"id": r.id, "corpus": r.corpus, "pipeline": r.pipeline, "status": r.status, "sample_size": r.sample_size, "metrics": r.metrics,
             "per_site": r.per_site, "note": r.note, "at": _iso(r.created_at)} for r in rows]

