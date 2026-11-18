"""Regulatory & risk intelligence: policy search, change comparison, control mapping, exceptions, evidence, reports."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend import runtime as R
from backend.api.deps import Ctx, authorize, current, require
from backend.db import models as m
from governance import audit
from governance.audit import audit_session
from retrieval.ingest import IngestError, ingest_bytes
from retrieval.search import compare_documents, get_document, search

router = APIRouter(prefix="/api")


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=20)
    doc_types: list[str] | None = None


@router.post("/docs/search")
def docs_search(body: SearchIn, ctx: Ctx = Depends(require("docs:read"))):
    return search(ctx.db, R.engine(), ctx.principal, body.query, body.k, today=date.today(), doc_types=body.doc_types)


@router.get("/docs/compare")
def docs_compare(old: str, new: str, ctx: Ctx = Depends(require("compliance:read"))):
    try:
        return compare_documents(ctx.db, R.engine(), ctx.principal, old, new)
    except PermissionError:
        raise HTTPException(404, "document not accessible") from None


@router.get("/docs")
def docs_list(ctx: Ctx = Depends(require("docs:read"))):
    from retrieval.search import groups_for, LEVELS
    g = groups_for(ctx.principal)
    rows = ctx.db.scalars(select(m.Document).where(m.Document.tenant_id == ctx.principal.tenant_id))
    return {"documents": [{"id": d.id, "title": d.title, "version": d.version, "classification": d.classification, "doc_type": d.doc_type,
                           "language": d.language, "status": d.status, "effective_date": d.effective_date.isoformat(),
                           "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None, "jurisdiction": d.jurisdiction, "owner": d.owner,
                           "injection_flags": len(d.injection_flags)}
                          for d in rows if set(d.access_groups) & g and LEVELS[d.classification] <= LEVELS[ctx.principal.clearance]]}


@router.get("/docs/{doc_id}")
def doc(doc_id: str, ctx: Ctx = Depends(require("docs:read"))):
    d = get_document(ctx.db, R.engine(), ctx.principal, doc_id)
    if d is None:
        raise HTTPException(404, "document not found")
    return d


@router.post("/docs/upload")
async def upload(file: UploadFile = File(...), doc_id: str = Form(..., pattern=r"^DOC-[A-Z0-9-]{1,20}$"), title: str = Form(..., max_length=200),
                 classification: str = Form(..., pattern="^(public|internal|confidential|restricted)$"), access_groups: str = Form("all-staff"),
                 jurisdiction: str = Form("CA"), doc_type: str = Form("policy"), ctx: Ctx = Depends(require("compliance:write"))):
    data = await file.read(5 * 1024 * 1024 + 1)
    meta = {"id": doc_id, "title": title, "owner": ctx.principal.display_name, "version": "1.0", "classification": classification,
            "tenant": ctx.principal.tenant_id, "access_groups": [g.strip() for g in access_groups.split(",") if g.strip()],
            "effective_date": date.today().isoformat(), "jurisdiction": jurisdiction, "doc_type": doc_type}
    try:
        d = ingest_bytes(ctx.db, file.filename or "upload.md", data, meta, source=f"upload:{ctx.principal.user_id}")
    except IngestError as e:
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="docs.upload", resource_type="document",
                     resource_id=doc_id, decision="deny", reasons=[{"rule": "INGEST-REJECTED", "message": str(e)}])
        raise HTTPException(422, {"code": "INGEST-REJECTED", "message": str(e)}) from e
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="docs.upload", resource_type="document",
                 resource_id=d.id, decision="allow", details={"status": d.status, "classification": d.classification})
    return {"id": d.id, "status": d.status, "classification": d.classification, "injection_flags": d.injection_flags}


@router.get("/compliance/events")
def events(status: str | None = None, ctx: Ctx = Depends(require("compliance:read"))):
    rows = [e for e in ctx.adapters.warehouse.table("compliance_events") if status is None or e["status"] == status]
    # minimization: compliance views reference clients by id only
    return {"events": [{**{k: (v.isoformat() if isinstance(v, date) else v) for k, v in e.items()}} for e in rows]}


@router.get("/compliance/controls")
def controls(ctx: Ctx = Depends(require("compliance:read"))):
    ev = ctx.adapters.warehouse.table("compliance_events")
    out = []
    for c in ctx.adapters.warehouse.table("controls"):
        mine = [e for e in ev if e["control_id"] == c["id"]]
        out.append({**c, "events_total": len(mine), "events_open": sum(e["status"] != "closed" for e in mine),
                    "events_high": sum(e["severity"] in ("high", "critical") for e in mine)})
    return {"controls": out, "note": "Framework references are illustrative and require validation by Compliance; the AI does not make regulatory determinations."}


class EventUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_review|closed)$")
    note: str = Field("", max_length=1000)


@router.post("/compliance/events/{event_id}/status")
def update_event(event_id: str, body: EventUpdate, ctx: Ctx = Depends(require("compliance:write"))):
    e = ctx.db.get(m.ComplianceEvent, event_id)
    if e is None or e.tenant_id != ctx.principal.tenant_id:
        raise HTTPException(404, "event not found")
    prev = e.status
    e.status = body.status
    e.closed_at = date.today() if body.status == "closed" else None
    from integrations.mock.store import invalidate
    invalidate()
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="compliance.exception.update", resource_type="compliance_event",
                 resource_id=event_id, decision="allow", details={"from": prev, "to": body.status, "note": body.note})
    return {"id": event_id, "status": e.status}


@router.get("/compliance/events/{event_id}/evidence")
def evidence(event_id: str, ctx: Ctx = Depends(require("compliance:read"))):
    e = ctx.db.get(m.ComplianceEvent, event_id)
    if e is None or e.tenant_id != ctx.principal.tenant_id:
        raise HTTPException(404, "event not found")
    ctrl = ctx.db.get(m.Control, e.control_id)
    with audit_session() as s:
        trail = [{"ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "decision": a.decision, "details": a.details}
                 for a in s.scalars(select(m.AuditEvent).where(m.AuditEvent.resource_id == event_id).order_by(m.AuditEvent.seq))]
    docs = search(ctx.db, R.engine(), ctx.principal, f"{ctrl.name} {e.event_type}", 3)["results"]
    return {"event": {c.key: (getattr(e, c.key).isoformat() if isinstance(getattr(e, c.key), date) else getattr(e, c.key)) for c in m.ComplianceEvent.__table__.columns},
            "control": {"id": ctrl.id, "name": ctrl.name, "framework_refs": ctrl.framework_refs, "owner": ctrl.owner},
            "audit_trail": trail, "related_policies": [{"document_id": d["document_id"], "title": d["title"], "section": d["section"]} for d in docs],
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@router.get("/compliance/report")
def compliance_report(ctx: Ctx = Depends(require("compliance:read"))):
    ev = ctx.adapters.warehouse.table("compliance_events")
    with audit_session() as s:
        rows = list(s.scalars(select(m.AuditEvent).where(m.AuditEvent.tenant_id == ctx.principal.tenant_id)))
    by_action: dict = {}
    for a in rows:
        k = (a.action.split(":")[0], a.decision)
        by_action[f"{k[0]}|{k[1]}"] = by_action.get(f"{k[0]}|{k[1]}", 0) + 1
    apr = list(ctx.db.scalars(select(m.Approval).where(m.Approval.tenant_id == ctx.principal.tenant_id)))
    from approvals.service import effective_status
    from governance.audit import verify_chain
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "audit_chain": verify_chain(),
            "exceptions": {"total": len(ev), "open": sum(e["status"] != "closed" for e in ev),
                           "by_severity": {s: sum(e["severity"] == s for e in ev) for s in ("low", "medium", "high", "critical")}},
            "approvals": {s: sum(effective_status(a) == s for a in apr) for s in ("pending", "approved", "rejected", "executed", "expired", "invalidated")},
            "policy_decisions": by_action, "policy_version": R.engine().version}


_ = (authorize, current)
