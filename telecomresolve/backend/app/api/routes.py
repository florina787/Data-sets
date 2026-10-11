"""HTTP API. Identity, role and tenant always come from the server-side
session, never from request bodies."""
from __future__ import annotations

import asyncio
import json
import statistics
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import seed as seed_mod
from ..agents import qa
from ..agents.providers import ProviderUnavailable, get_provider
from ..auth.permissions import ROLE_PERMISSIONS, Perm, Role
from ..auth.session import Principal, get_principal, issue_token, require, verify_token
from ..config import get_settings
from ..connectors.enterprise import ENTERPRISE_CONNECTORS
from ..connectors.synthetic import TOOL_SPECS
from ..db import get_db, session_factory, utcnow
from ..models.orm import (
    Account, ActionExecution, Approval, AuditEvent, Case, CaseMessage, EvidenceSnapshot, Hypothesis,
    Incident, Recommendation, RecoveryObservation, Tenant, User,
)
from ..observability import audit
from ..policies.catalog import load_catalog
from ..policies.state_machine import TRANSITIONS
from ..retrieval import citations, knowledge
from ..workflows import graph as wf
from ..workflows import service
from ..workflows.scope import scoped_case, visible_case_filter
from . import serializers as ser

router = APIRouter()
DISCLAIMER = "Independent telecom prototype — synthetic data"


# ------------------------------------------------------------------ system
@router.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


@router.get("/ready", tags=["system"])
def ready(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
        checks["seeded"] = "ok" if db.get(Tenant, "tenant-north") else "not seeded"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        wf.get_graph()
        checks["workflow"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["workflow"] = f"error: {type(exc).__name__}"
    p = get_provider()
    s = get_settings()
    checks["generation"] = ("deterministic demo provider" if not p.is_live else
                            ("configured" if s.llm_api_key else "LIVE selected but no API key configured"))
    ok = checks["database"] == "ok" and checks["workflow"] == "ok" and checks.get("seeded") == "ok"
    if not ok:
        raise HTTPException(503, detail={"code": "NOT_READY", "checks": checks})
    return {"status": "ready", "checks": checks}


@router.get("/api/system", tags=["system"])
def system_info():
    s = get_settings()
    p = get_provider()
    ds = seed_mod.load_dataset()
    return {"disclaimer": DISCLAIMER, "app_mode": s.app_mode, "generation": p.describe(),
            "connector_mode": s.connector_mode, "policy_version": load_catalog().version,
            "dataset_version": ds["dataset_version"],
            "limits": {"max_evidence_iterations": s.max_evidence_iterations,
                       "diagnostic_freshness_hours": s.diagnostic_freshness_hours,
                       "approval_ttl_minutes": s.approval_ttl_minutes,
                       "recovery_window_minutes": s.recovery_window_minutes,
                       "recovery_min_samples": s.recovery_min_samples,
                       "llm_case_token_budget": s.llm_case_token_budget},
            "state_machine": {k.value: sorted(v2.value for v2 in v) for k, v in TRANSITIONS.items()}}


@router.get("/api/connectors", tags=["system"])
def connectors(principal: Principal = Depends(get_principal)):
    tools = [{"name": t.name, "description": t.description, "classification": t.classification,
              "required_permission": t.required_permission, "input_schema": t.input_schema,
              "timeout_seconds": t.timeout_seconds, "idempotency": t.idempotency, "errors": list(t.errors),
              "audit_fields": list(t.audit_fields), "requires_approval": t.requires_approval,
              "mode": "SIMULATED", "available": True} for t in TOOL_SPECS.values()]
    return {"simulated_tools": tools, "enterprise_connectors": [c.status() for c in ENTERPRISE_CONNECTORS],
            "action_catalog": {"version": load_catalog().version,
                               "actions": [vars(a) for a in load_catalog().actions.values()]}}


# ------------------------------------------------------------------ auth
class LoginBody(BaseModel):
    persona_id: str


@router.get("/api/auth/personas", tags=["auth"])
def personas(db: Session = Depends(get_db)):
    if not get_settings().is_demo:
        raise HTTPException(404, detail={"code": "DEMO_ONLY", "message": "Personas exist only in demo mode"})
    users = db.scalars(select(User).order_by(User.id)).all()
    return [{"id": u.id, "display_name": u.display_name, "role": u.role, "tenant_id": u.tenant_id} for u in users]


@router.post("/api/auth/demo-login", tags=["auth"])
def demo_login(body: LoginBody, db: Session = Depends(get_db)):
    if not get_settings().is_demo:
        raise HTTPException(403, detail={"code": "DEMO_ONLY",
                                         "message": "Persona login is disabled outside demo mode"})
    user = db.get(User, body.persona_id)
    if user is None or not user.active:
        raise HTTPException(404, detail={"code": "UNKNOWN_PERSONA", "message": "Unknown persona"})
    audit.record(db, tenant_id=user.tenant_id, actor_id=user.id, actor_role=user.role,
                 event_type="DEMO_LOGIN", detail={"note": "demo persona selection; not production auth"})
    db.commit()
    return {"token": issue_token(user.id), "user": {"id": user.id, "display_name": user.display_name,
                                                     "role": user.role, "tenant_id": user.tenant_id}}


@router.get("/api/auth/me", tags=["auth"])
def me(principal: Principal = Depends(get_principal)):
    return {"id": principal.user_id, "display_name": principal.display_name, "role": principal.role,
            "tenant_id": principal.tenant_id, "account_segments": list(principal.account_segments),
            "permissions": sorted(p.value for p in ROLE_PERMISSIONS[Role(principal.role)])}


# ------------------------------------------------------------------ cases
@router.get("/api/cases", tags=["cases"])
def list_cases(principal: Principal = Depends(require(Perm.CASE_READ)), db: Session = Depends(get_db)):
    cases = db.scalars(visible_case_filter(db, principal).order_by(Case.id)).all()
    return [ser.case_summary(c) for c in cases]


class CreateCaseBody(BaseModel):
    account_id: str
    title: str = Field(min_length=3, max_length=300)
    complaint_text: str = Field(min_length=5, max_length=4000)


@router.post("/api/cases", status_code=201, tags=["cases"])
def create_case(body: CreateCaseBody, principal: Principal = Depends(require(Perm.CASE_CREATE)),
                db: Session = Depends(get_db)):
    account = db.scalar(select(Account).where(Account.id == body.account_id,
                                              Account.tenant_id == principal.tenant_id))
    if account is None or account.segment not in principal.account_segments:
        raise HTTPException(404, detail={"code": "ACCOUNT_NOT_FOUND", "message": "Account not found in your scope"})
    from ..models.orm import Service

    svc = db.scalar(select(Service).where(Service.account_id == account.id, Service.product == "home_internet"))
    if svc is None:
        raise HTTPException(422, detail={"code": "NO_SERVICE", "message": "No home internet service on account"})
    now = utcnow()
    n = db.scalar(select(func.count()).select_from(Case)) or 0
    case = Case(id=f"C-{2000 + n + 1}-{uuid.uuid4().hex[:4]}", tenant_id=principal.tenant_id,
                account_id=account.id, service_id=svc.id, title=body.title, complaint_text=body.complaint_text,
                reported_symptoms={}, status="NEW", version=1, created_by=principal.user_id, created_at=now,
                updated_at=now, simulation_profile={"post_action": "telemetry_gap"})
    db.add(case)
    db.flush()
    audit.record(db, tenant_id=principal.tenant_id, actor_id=principal.user_id, actor_role=principal.role,
                 event_type="CASE_CREATED", case_id=case.id, to_status="NEW", detail={"source": "api"})
    db.commit()
    return ser.case_summary(case)


@router.get("/api/cases/{case_id}", tags=["cases"])
def get_case(case_id: str, principal: Principal = Depends(require(Perm.CASE_READ)), db: Session = Depends(get_db)):
    return ser.case_detail(db, principal, scoped_case(db, principal, case_id))


@router.post("/api/cases/{case_id}/investigate", status_code=202, tags=["workflow"])
def investigate(case_id: str, wait: bool = Query(False),
                principal: Principal = Depends(require(Perm.CASE_INVESTIGATE)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    job = service.start_investigation(db, principal, case, wait=wait)
    db.expire_all()
    return {**job, "case": ser.case_summary(db.get(Case, case_id))}


class ClarifyBody(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    rerun: bool = True
    wait: bool = False


@router.post("/api/cases/{case_id}/clarifications", tags=["workflow"])
def clarify(case_id: str, body: ClarifyBody, principal: Principal = Depends(require(Perm.CASE_CLARIFY)),
            db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    msg = service.add_clarification(db, principal, case, body.text)
    job = None
    if body.rerun:
        db.refresh(case)
        job = service.start_investigation(db, principal, case, wait=body.wait, after_clarification=True)
    return {"message_id": msg.id, "job": job}


class MessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.get("/api/cases/{case_id}/messages", tags=["copilot"])
def list_messages(case_id: str, principal: Principal = Depends(require(Perm.CASE_READ)),
                  db: Session = Depends(get_db)):
    scoped_case(db, principal, case_id)
    rows = db.scalars(select(CaseMessage).where(CaseMessage.case_id == case_id).order_by(CaseMessage.created_at))
    return [{"id": m.id, "role": m.role, "kind": m.kind, "text": m.text, "citations": m.citations,
             "generation_mode": m.generation_mode, "author_id": m.author_id, "created_at": ser.iso(m.created_at)}
            for m in rows]


@router.post("/api/cases/{case_id}/messages", tags=["copilot"])
def ask(case_id: str, body: MessageBody, principal: Principal = Depends(require(Perm.EVIDENCE_READ)),
        db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    snap = db.scalar(select(EvidenceSnapshot).where(EvidenceSnapshot.case_id == case.id)
                     .order_by(EvidenceSnapshot.created_at.desc()).limit(1))
    bundle = wf.load_bundle(db, snap.id) if snap else None
    etr = None
    if case.linked_incident_id:
        inc = db.get(Incident, case.linked_incident_id)
        etr = ser.iso(inc.estimated_restoration_at) if inc else None
    now = utcnow()
    db.add(CaseMessage(id=f"MSG-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id,
                       author_id=principal.user_id, role="user", kind="question", text=body.text,
                       citations=[], generation_mode="n/a", created_at=now))
    try:
        answer, cites, mode, usage = qa.answer(db, question=body.text, tenant_id=principal.tenant_id,
                                               role=principal.role, bundle=bundle, provider=get_provider(),
                                               incident_etr=etr)
    except ProviderUnavailable as exc:
        answer, cites, mode, usage = (f"Live generation unavailable ({exc.code}). No answer was generated.",
                                      [], "UNAVAILABLE", None)
    reply = CaseMessage(id=f"MSG-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id,
                        author_id="copilot", role="assistant", kind="answer", text=answer, citations=cites,
                        generation_mode=mode, created_at=now + timedelta(microseconds=1))
    db.add(reply)
    audit.record(db, tenant_id=principal.tenant_id, actor_id=principal.user_id, actor_role=principal.role,
                 event_type="COPILOT_QUESTION", case_id=case.id, generation_mode=mode,
                 usage=usage.to_dict() if usage else {},
                 detail={"cited": [c["id"] for c in cites], "mode": mode})
    db.commit()
    return {"id": reply.id, "role": "assistant", "text": answer, "citations": cites, "generation_mode": mode}


# ------------------------------------------------------------------ evidence
@router.get("/api/cases/{case_id}/evidence", tags=["evidence"])
def get_evidence(case_id: str, snapshot_id: str | None = None,
                 principal: Principal = Depends(require(Perm.EVIDENCE_READ)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    q = select(EvidenceSnapshot).where(EvidenceSnapshot.case_id == case.id)
    q = q.where(EvidenceSnapshot.id == snapshot_id) if snapshot_id else q.order_by(EvidenceSnapshot.created_at.desc())
    snap = db.scalar(q.limit(1))
    if snap is None:
        return {"snapshot": None, "items": [], "hypotheses": [], "diagnosis": None, "snapshots": []}
    hyps = db.scalars(select(Hypothesis).where(Hypothesis.snapshot_id == snap.id).order_by(Hypothesis.rank)).all()
    diag = db.scalar(select(AuditEvent).where(AuditEvent.case_id == case.id,
                                              AuditEvent.event_type == "DIAGNOSIS_COMPLETED")
                     .order_by(AuditEvent.id.desc()).limit(1))
    all_snaps = db.scalars(select(EvidenceSnapshot.id).where(EvidenceSnapshot.case_id == case.id)
                           .order_by(EvidenceSnapshot.created_at)).all()
    return {"snapshot": {"id": snap.id, "created_at": ser.iso(snap.created_at), "content_hash": snap.content_hash,
                         "window_start": snap.bundle["window_start"], "window_end": snap.bundle["window_end"],
                         "facts": snap.bundle["facts"], "missing_evidence": snap.bundle["missing_evidence"],
                         "prior_actions": snap.bundle["prior_actions"]},
            "items": snap.bundle["items"],
            "hypotheses": [{"rank": h.rank, "category": h.category, "statement": h.statement,
                            "sufficiency": h.sufficiency, "supporting_refs": h.supporting_refs,
                            "opposing_refs": h.opposing_refs} for h in hyps],
            "diagnosis": diag.detail if diag else None, "snapshots": list(all_snaps)}


@router.get("/api/cases/{case_id}/evidence/{ref_id}", tags=["evidence"])
def get_evidence_item(case_id: str, ref_id: str, snapshot_id: str | None = None,
                      principal: Principal = Depends(require(Perm.EVIDENCE_READ)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    q = select(EvidenceSnapshot).where(EvidenceSnapshot.case_id == case.id)
    q = q.where(EvidenceSnapshot.id == snapshot_id) if snapshot_id else q.order_by(EvidenceSnapshot.created_at.desc())
    snap = db.scalar(q.limit(1))
    item = next((i for i in (snap.bundle["items"] if snap else []) if i["ref_id"] == ref_id), None)
    if item is None:
        raise HTTPException(404, detail={"code": "REF_NOT_FOUND", "message": "Evidence reference not found"})
    res = citations.resolve(db, principal.tenant_id, item)
    record = res["record"]
    if item["source_type"] == "support_interaction" and "prompt_injection" in item["flags"]:
        record = {**record, "warning": "This record contains instruction-like text that was quarantined. "
                                       "It is shown for human review only and was not used as evidence."}
    return {"item": item, "snapshot_id": snap.id, "resolves": res["ok"], "problem": res["problem"], "record": record}


@router.get("/api/cases/{case_id}/citations/validate", tags=["evidence"])
def validate_citations(case_id: str, principal: Principal = Depends(require(Perm.EVIDENCE_READ)),
                       db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    return citations.validate_case(db, principal.tenant_id, case.id)


@router.get("/api/knowledge/search", tags=["evidence"])
def kb_search(q: str = Query(min_length=2, max_length=200),
              principal: Principal = Depends(require(Perm.KNOWLEDGE_READ)), db: Session = Depends(get_db)):
    hits = knowledge.search(db, q, tenant_id=principal.tenant_id, role=principal.role, k=8)
    return {"mode": "lexical BM25 (semantic retrieval not configured)",
            "results": [vars(h) for h in hits]}


# ------------------------------------------------------------------ recommendations / approvals
@router.get("/api/cases/{case_id}/recommendations", tags=["workflow"])
def get_recommendations(case_id: str, principal: Principal = Depends(require(Perm.RECOMMENDATION_READ)),
                        db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    recs = db.scalars(select(Recommendation).where(Recommendation.case_id == case.id)
                      .order_by(Recommendation.created_at.desc())).all()
    return {"current": ser.recommendation(db.get(Recommendation, case.current_recommendation_id))
            if case.current_recommendation_id else None,
            "history": [ser.recommendation(r) for r in recs]}


class AlternativeBody(BaseModel):
    action_type: str


@router.post("/api/cases/{case_id}/recommendations", tags=["workflow"])
def choose_alternative(case_id: str, body: AlternativeBody,
                       principal: Principal = Depends(require(Perm.CASE_INVESTIGATE)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    rec = service.select_alternative(db, principal, case, body.action_type)
    return ser.recommendation(rec)


class ApprovalBody(BaseModel):
    action: Literal["request", "approve", "reject"]
    approval_id: str | None = None
    recommendation_id: str | None = None
    payload_hash: str | None = None
    reason: str = ""


@router.post("/api/cases/{case_id}/approvals", tags=["workflow"])
def approvals(case_id: str, body: ApprovalBody, principal: Principal = Depends(get_principal),
              db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    if body.action == "request":
        if not principal.can(Perm.CASE_INVESTIGATE):
            raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Cannot request approval"})
        appr = service.request_new_approval(db, principal, case, body.recommendation_id or "")
        db.commit()
        return ser.approval(appr)
    if not principal.can(Perm.APPROVAL_DECIDE):
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": f"Role '{principal.role}' cannot decide approvals"})
    if not body.approval_id or not body.payload_hash:
        raise HTTPException(422, detail={"code": "MISSING_FIELDS", "message": "approval_id and payload_hash required"})
    appr = service.decide_approval(db, principal, case, approval_id=body.approval_id,
                                   decision=body.action, payload_hash=body.payload_hash, reason=body.reason)
    return ser.approval(appr)


@router.get("/api/approvals", tags=["workflow"])
def approval_queue(principal: Principal = Depends(require(Perm.CASE_READ)), db: Session = Depends(get_db)):
    visible = {c.id: c for c in db.scalars(visible_case_filter(db, principal)).all()}
    rows = db.scalars(select(Approval).where(Approval.tenant_id == principal.tenant_id)
                      .order_by(Approval.requested_at.desc())).all()
    now = utcnow()
    out = []
    for a in rows:
        if a.case_id not in visible:
            continue
        d = ser.approval(a)
        rec = db.get(Recommendation, a.recommendation_id)
        d["case_title"] = visible[a.case_id].title
        d["case_status"] = visible[a.case_id].status
        d["can_decide"] = (a.status == "pending" and principal.role in a.required_roles and
                           not (a.separation_of_duties and rec.proposed_by == principal.user_id))
        d["expired"] = bool(a.expires_at and now > a.expires_at)
        d["wait_minutes"] = round(((a.decided_at or now) - a.requested_at).total_seconds() / 60, 1)
        out.append(d)
    return out


class ExecuteBody(BaseModel):
    approval_id: str


@router.post("/api/cases/{case_id}/execute", tags=["workflow"])
def execute(case_id: str, body: ExecuteBody, idempotency_key: str = Header(default="", alias="Idempotency-Key"),
            principal: Principal = Depends(require(Perm.ACTION_EXECUTE)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    exe, replayed = service.execute(db, principal, case, approval_id=body.approval_id,
                                    idempotency_key=idempotency_key)
    db.expire_all()
    return {"execution": ser.execution(db.get(ActionExecution, exe.id)), "replayed": replayed,
            "case": ser.case_summary(db.get(Case, case_id))}


class VerifyBody(BaseModel):
    customer_report: str | None = Field(default=None, max_length=1000)


@router.post("/api/cases/{case_id}/verify", tags=["workflow"])
def verify(case_id: str, body: VerifyBody | None = None,
           principal: Principal = Depends(require(Perm.RECOVERY_VERIFY)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    obs = service.verify(db, principal, case, customer_report=body.customer_report if body else None)
    db.expire_all()
    return {"recovery": ser.recovery(obs), "case": ser.case_summary(db.get(Case, case_id))}


class CancelBody(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/api/cases/{case_id}/cancel", tags=["workflow"])
def cancel(case_id: str, body: CancelBody, principal: Principal = Depends(require(Perm.CASE_CANCEL)),
           db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    service.cancel(db, principal, case, body.reason)
    return ser.case_summary(case)


# ------------------------------------------------------------------ audit
@router.get("/api/cases/{case_id}/audit", tags=["audit"])
def case_audit(case_id: str, principal: Principal = Depends(require(Perm.CASE_READ)), db: Session = Depends(get_db)):
    case = scoped_case(db, principal, case_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id)).all()
    return [ser.audit_event(e) for e in rows]


@router.get("/api/cases/{case_id}/audit/replay", tags=["audit"])
def audit_replay(case_id: str, principal: Principal = Depends(require(Perm.CASE_READ)),
                 db: Session = Depends(get_db)):
    """Re-derive the case history from the audit log and verify it."""
    from ..policies.state_machine import can_transition

    case = scoped_case(db, principal, case_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id)).all()
    chain_ok, chain_problems = audit.verify_chain(rows)
    status, steps, illegal = None, [], []
    for e in rows:
        if e.to_status:
            if status is not None and e.from_status != status:
                illegal.append(f"{e.event_id}: from_status {e.from_status} != replayed {status}")
            if status is not None and not can_transition(status, e.to_status):
                illegal.append(f"{e.event_id}: illegal {status}->{e.to_status}")
            status = e.to_status
            steps.append({"seq": e.id, "at": ser.iso(e.occurred_at), "actor": e.actor_id, "node": e.node,
                          "from": e.from_status, "to": e.to_status, "reason": e.detail.get("reason")})
    recs = db.scalars(select(Recommendation).where(Recommendation.case_id == case.id)
                      .order_by(Recommendation.created_at)).all()
    reconstructed = []
    for r in recs:
        snap = db.get(EvidenceSnapshot, r.snapshot_id)
        items = {i["ref_id"]: i for i in snap.bundle["items"]}
        reconstructed.append({"recommendation_id": r.id, "action_type": r.action_type, "snapshot_id": snap.id,
                              "snapshot_hash": snap.content_hash, "policy_version": r.policy_version,
                              "evidence": [{"ref_id": ref, "excerpt": items[ref]["excerpt"],
                                            "source_version": items[ref]["source_version"]}
                                           for ref in r.evidence_refs if ref in items]})
    return {"case_id": case.id, "replayed_status": status, "current_status": case.status,
            "status_matches": status == case.status, "hash_chain_valid": chain_ok,
            "chain_problems": chain_problems, "illegal_transitions": illegal, "steps": steps,
            "recommendations": reconstructed, "event_count": len(rows),
            "limits": "Tamper-evident hash chain within the application database; not tamper-proof storage."}


@router.get("/api/audit", tags=["audit"])
def tenant_audit(limit: int = Query(200, le=1000), event_type: str | None = None,
                 principal: Principal = Depends(require(Perm.AUDIT_READ)), db: Session = Depends(get_db)):
    q = select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    rows = db.scalars(q.order_by(AuditEvent.id.desc()).limit(limit)).all()
    return [ser.audit_event(e) for e in rows]


@router.get("/api/cases/{case_id}/events", tags=["audit"])
async def case_events(case_id: str, request: Request, access_token: str = Query(...), after: int = 0):
    """Server-sent events streamed from persisted audit records. EventSource
    cannot send headers, so the session token is passed as a query param."""
    user_id = verify_token(access_token)
    SessionLocal = session_factory()
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(401, detail={"code": "INVALID_SESSION"})
        principal = Principal(user.id, user.tenant_id, user.role, user.display_name,
                              tuple(user.account_segments or []))
        if not principal.can(Perm.CASE_READ):
            raise HTTPException(403, detail={"code": "FORBIDDEN"})
        scoped_case(db, principal, case_id)

    async def stream():
        last = after
        idle = 0
        while idle < 600:
            if await request.is_disconnected():
                break
            with SessionLocal() as db:
                rows = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case_id, AuditEvent.id > last,
                                                           AuditEvent.tenant_id == principal.tenant_id)
                                  .order_by(AuditEvent.id)).all()
                for e in rows:
                    last = e.id
                    yield f"id: {e.id}\nevent: audit\ndata: {json.dumps(ser.audit_event(e))}\n\n"
            idle = 0 if rows else idle + 1
            if not rows:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ------------------------------------------------------------------ dashboard / metrics
@router.get("/api/dashboard", tags=["metrics"])
def dashboard(principal: Principal = Depends(require(Perm.DASHBOARD_READ)), db: Session = Depends(get_db)):
    """All figures derive from persisted cases, approvals, executions and audit
    events. Durations here are wall-clock times of this prototype's runs;
    recovery windows use simulated (fast-forwarded) time."""
    cases = db.scalars(visible_case_filter(db, principal)).all()
    ids = [c.id for c in cases]
    by_status: dict[str, int] = {}
    for c in cases:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    events = db.scalars(select(AuditEvent).where(AuditEvent.case_id.in_(ids)).order_by(AuditEvent.id)).all() if ids else []
    starts, ready_times, escal, conn_err, usage_cost, usage_tokens, usage_unavail = {}, [], [], [], 0.0, 0, 0
    for e in events:
        if e.event_type == "INVESTIGATION_STARTED":
            starts[e.case_id] = e.occurred_at
        if e.to_status in ("RECOMMENDATION_READY", "NEEDS_INFORMATION", "ESCALATED") and e.case_id in starts \
                and e.from_status in ("ASSESSING", "COLLECTING_EVIDENCE"):
            ready_times.append((e.occurred_at - starts.pop(e.case_id)).total_seconds())
        if e.to_status == "ESCALATED":
            escal.append({"case_id": e.case_id, "reason": e.detail.get("summary") or e.detail.get("reason"),
                          "at": ser.iso(e.occurred_at)})
        if e.event_type in ("EXECUTION_OUTCOME_UNKNOWN", "WORKFLOW_ERROR") or (
                e.event_type == "EVIDENCE_COLLECTED" and any("error" in t for t in e.detail.get("tool_calls", []))):
            conn_err.append({"case_id": e.case_id, "event": e.event_type, "at": ser.iso(e.occurred_at)})
        if e.usage:
            if e.usage.get("usage_available"):
                usage_tokens += int(e.usage.get("input_tokens") or 0) + int(e.usage.get("output_tokens") or 0)
                usage_cost += float(e.usage.get("estimated_cost_usd") or 0)
            elif e.usage.get("calls"):
                usage_unavail += 1

    def pct(values, p):
        if not values:
            return None
        v = sorted(values)
        return round(v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))], 2)

    approvals = db.scalars(select(Approval).where(Approval.case_id.in_(ids))).all() if ids else []
    now = utcnow()
    waits = [{"approval_id": a.id, "case_id": a.case_id, "action_type": a.action_type,
              "waiting_minutes": round((now - a.requested_at).total_seconds() / 60, 1),
              "expired": bool(a.expires_at and now > a.expires_at)} for a in approvals if a.status == "pending"]
    turnaround = [(a.decided_at - a.requested_at).total_seconds() / 60 for a in approvals if a.decided_at]
    obs = db.scalars(select(RecoveryObservation).where(RecoveryObservation.case_id.in_(ids))).all() if ids else []
    stale = [{"case_id": e.case_id, "snapshot_id": e.detail.get("snapshot_id")} for e in events
             if e.event_type == "EVIDENCE_COLLECTED" and "stale_only" in e.detail.get("facts", [])]
    resolved = [c for c in cases if c.status == "RESOLVED"]
    verified_times = []
    for c in resolved:
        o = max((x for x in obs if x.case_id == c.id and x.outcome == "RESOLVED"), key=lambda x: x.checked_at, default=None)
        if o:
            verified_times.append((o.checked_at - c.created_at).total_seconds() / 60)
    investigated = len({e.case_id for e in events if e.event_type == "INVESTIGATION_STARTED"})
    executions = db.scalars(select(ActionExecution).where(ActionExecution.case_id.in_(ids))).all() if ids else []
    return {
        "generated_at": ser.iso(now), "case_count": len(cases), "by_status": by_status,
        "unresolved": [ser.case_summary(c) for c in cases if c.status not in ("RESOLVED", "CANCELLED")],
        "investigation_seconds": {"n": len(ready_times), "median": round(statistics.median(ready_times), 3) if ready_times else None,
                                  "p95": pct(ready_times, 95),
                                  "definition": "wall-clock from INVESTIGATION_STARTED to the first of RECOMMENDATION_READY / NEEDS_INFORMATION / ESCALATED"},
        "time_to_verified_resolution_minutes": {
            "n": len(verified_times), "median": round(statistics.median(verified_times), 2) if verified_times else None,
            "definition": "case created -> RESOLVED recovery check; includes demo seed offsets and simulated recovery windows, so it is not a real-world duration"},
        "escalations": escal, "escalation_rate": {"numerator": len({x['case_id'] for x in escal}), "denominator": investigated},
        "approval_waits": waits,
        "approval_turnaround_minutes": {"n": len(turnaround), "median": round(statistics.median(turnaround), 2) if turnaround else None},
        "connector_errors": conn_err, "stale_evidence": stale,
        "recovery_failures": [ser.recovery(o) for o in obs if o.outcome != "RESOLVED"],
        "executions": {"total": len(executions), "succeeded": sum(1 for x in executions if x.status == "succeeded"),
                       "unknown": sum(1 for x in executions if x.status == "unknown")},
        "model_usage": {"tokens": usage_tokens, "estimated_cost_usd": round(usage_cost, 4),
                        "calls_without_usage_data": usage_unavail,
                        "cost_per_investigated_case_usd": round(usage_cost / investigated, 4) if investigated and usage_tokens else None,
                        "note": "DEMO mode makes no model calls, so token usage is zero."
                        if not get_provider().is_live else "Live provider usage as reported by the API."},
        "repeat_contacts": _repeat_contacts(db, principal),
    }


def _repeat_contacts(db: Session, principal: Principal) -> dict:
    from ..models.orm import SupportInteraction

    s = get_settings()
    since = utcnow() - timedelta(days=s.repeat_contact_window_days)
    accts = [a.id for a in db.scalars(select(Account).where(Account.tenant_id == principal.tenant_id,
                                                            Account.segment.in_(principal.account_segments)))]
    rows = db.scalars(select(SupportInteraction).where(SupportInteraction.account_id.in_(accts),
                                                       SupportInteraction.occurred_at >= since)).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.account_id] = counts.get(r.account_id, 0) + 1
    cases = db.scalars(select(Case).where(Case.account_id.in_(accts))).all()
    for c in cases:
        counts[c.account_id] = counts.get(c.account_id, 0) + 1
    with_contact = [a for a, n in counts.items() if n >= 1]
    repeat = [a for a, n in counts.items() if n >= 2]
    return {"window_days": s.repeat_contact_window_days, "numerator": len(repeat), "denominator": len(with_contact),
            "definition": "accounts with >= 2 contacts (support interactions + cases) in the window / accounts with >= 1 contact"}


# ------------------------------------------------------------------ evaluation / demo
@router.get("/api/evaluations", tags=["evaluation"])
def evaluations(principal: Principal = Depends(require(Perm.EVAL_READ))):
    d = get_settings().evaluation_dir / "results"
    out = []
    for p in sorted(d.glob("eval-*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


@router.post("/api/demo/reset", tags=["demo"])
def demo_reset(principal: Principal = Depends(require(Perm.EVAL_RUN))):
    if not get_settings().is_demo:
        raise HTTPException(403, detail={"code": "DEMO_ONLY", "message": "Reset is disabled outside demo mode"})
    wf.reset_graph()
    result = seed_mod.reset_demo()
    wf.reset_graph()
    return {"reset": True, **result}
