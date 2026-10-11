"""HTTP API. Actor and tenant come from trusted session context (`current_user`), never from the
request body. Every write commits in one transaction; long work (evaluation) runs as a background
job and is polled."""
from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.agents.agents import CONTRACTS
from app.config import get_settings
from app.connectors import interfaces as connectors
from app.db import SessionLocal
from app.errors import Forbidden, NotFound, Unauthorized
from app.evaluation import jobs, runner
from app.lifecycle.state_machine import S, transition_table
from app.models.orm import AuditEvent, ChangeRequest, EvaluationRun, ImageUpload, Prediction, User
from app.retrieval.knowledge import get_kb
from app.security import uploads
from app.security.rbac import PERMISSIONS, ROLES, require
from app.services import audit, gates, lifecycle, release, views
from app.services.repo import get_change, get_run
from app.workflows import graph

router = APIRouter()
BANNER = "Independent beauty AI prototype — synthetic evaluation data"


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def current_user(db: Session = Depends(get_db), x_demo_user: str | None = Header(default=None),
                 authorization: str | None = Header(default=None)) -> User:
    s = get_settings()
    if s.production:
        if x_demo_user:
            raise Forbidden("persona_selector_disabled", "Demo persona selection is disabled in production mode")
        raise Unauthorized("identity_unconfigured", "Production mode requires the identity (SSO) connector, which is not configured")
    if not x_demo_user:
        raise Unauthorized("no_session", "Select a demo persona (X-Demo-User header)")
    u = db.get(User, x_demo_user)
    if u is None:
        raise Unauthorized("unknown_persona", "Unknown demo persona")
    return u


# --------------------------------------------------------------------- meta

@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    seeded = db.execute(select(User).limit(1)).first() is not None
    kb_docs = len(get_kb().docs)
    ok = seeded and kb_docs > 0
    if not ok:
        raise NotFound("not_ready", "Database not seeded or knowledge base missing")
    return {"status": "ready", "seeded": seeded, "knowledge_documents": kb_docs}


@router.get("/api/meta")
def meta(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    personas = [] if s.production else [{"id": u.id, "display_name": u.display_name, "persona": u.persona, "roles": u.roles,
                                          "tenant_id": u.tenant_id} for u in db.execute(select(User)).scalars()]
    return {"banner": BANNER, "modes": s.modes(), "personas": personas, "persona_selector_enabled": s.persona_selector_enabled,
            "roles": ROLES, "permissions": {k: sorted(v) for k, v in PERMISSIONS.items()}, "states": [x.value for x in S],
            "transitions": transition_table()}


@router.get("/api/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "display_name": user.display_name, "persona": user.persona, "roles": user.roles, "tenant_id": user.tenant_id,
            "permissions": sorted(p for p, r in PERMISSIONS.items() if set(user.roles) & r)}


@router.get("/api/agents/contracts")
def agent_contracts() -> dict:
    return {"agents": CONTRACTS}


@router.get("/api/connectors")
def connector_status() -> dict:
    return {"connectors": connectors.status()}


@router.get("/api/scenarios")
def scenarios() -> dict:
    from app.services import fixtures
    return fixtures.load_json(fixtures.synthetic_dir() / "scenarios.json")


# ------------------------------------------------------------------ changes

class CreateChange(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=10, max_length=4000)


@router.get("/api/changes")
def list_changes(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    rows = db.execute(select(ChangeRequest).where(ChangeRequest.tenant_id == user.tenant_id).order_by(ChangeRequest.created_at)).scalars()
    return {"changes": [views.change_summary(c) for c in rows]}


@router.post("/api/changes", status_code=201)
def create_change(body: CreateChange, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    ch = lifecycle.create_change(db, user, body.title, body.description)
    return views.change_summary(ch)


@router.get("/api/changes/{change_id}")
def get_change_detail(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    return views.change_detail(db, user, change_id)


class ClarificationIn(BaseModel):
    key: str
    answer: str | None = Field(default=None, max_length=2000)
    structured: dict | None = None
    use_suggested: bool = False


@router.post("/api/changes/{change_id}/clarifications")
def answer(change_id: str, body: ClarificationIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    cl = lifecycle.answer_clarification(db, user, change_id, body.key, body.answer, body.structured, body.use_suggested)
    return {"id": cl.id, "key": cl.key, "answer": cl.answer, "cycle": cl.cycle}


@router.post("/api/changes/{change_id}/requirements/approve")
def approve_requirements(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    rv = lifecycle.approve_requirements(db, user, change_id)
    return {"requirement_version_id": rv.id, "version": rv.version, "status": rv.status}


@router.post("/api/changes/{change_id}/investigate")
def investigate(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return lifecycle.investigate(db, user, change_id)


@router.post("/api/changes/{change_id}/impact/accept")
def accept_impact(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    ia = lifecycle.accept_impact(db, user, change_id)
    return {"impact_id": ia.id, "accepted_by": ia.accepted_by}


class CandidateIn(BaseModel):
    model_id: str


@router.post("/api/changes/{change_id}/candidates")
def register_candidate(change_id: str, body: CandidateIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    ch = lifecycle.register_candidate(db, user, change_id, body.model_id)
    return views.change_summary(ch)


@router.post("/api/changes/{change_id}/evaluations", status_code=202)
def request_evaluation(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    run = runner.request_evaluation(db, user, change_id)
    db.commit()
    jobs.submit(run.id)
    db.refresh(run)
    return views.run_dict(run, full=False)


@router.get("/api/evaluations/{run_id}")
def get_evaluation(run_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    return views.run_dict(get_run(db, user.tenant_id, run_id))


@router.post("/api/evaluations/{run_id}/cancel")
def cancel_evaluation(run_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return views.run_dict(runner.cancel(db, user, run_id), full=False)


@router.get("/api/evaluations/{run_id}/predictions")
def predictions(run_id: str, cell: str | None = None, limit: int = Query(50, le=500), db: Session = Depends(get_db),
                user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    run = get_run(db, user.tenant_id, run_id)
    from app.models.orm import DatasetRecord
    q = select(Prediction, DatasetRecord).join(DatasetRecord, DatasetRecord.sample_id == Prediction.sample_id).where(Prediction.run_id == run.id)
    if cell:
        stratum, light = cell.split("|")
        q = q.where(DatasetRecord.tone_stratum == stratum, DatasetRecord.lighting_category == light)
    rows = db.execute(q.order_by(Prediction.sample_id, Prediction.model_id).limit(limit * 2)).all()
    return {"rows": [{"sample_id": p.sample_id, "model_id": p.model_id, "top3": p.top3, "abstained": p.abstained,
                      "expected": r.expected_shade_id, "cell": f"{r.tone_stratum}|{r.lighting_category}", "device": r.device_category}
                     for p, r in rows], "fixture": True}


class ReviewIn(BaseModel):
    kind: str
    decision: str
    comment: str = Field(default="", max_length=2000)


@router.post("/api/changes/{change_id}/reviews", status_code=201)
def review(change_id: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    r = gates.submit_review(db, user, change_id, body.kind, body.decision, body.comment)
    return {"id": r.id, "kind": r.kind, "decision": r.decision}


@router.get("/api/changes/{change_id}/release-readiness")
def readiness(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    ch = get_change(db, user.tenant_id, change_id)
    gs = [g.dict() for g in gates.release_gates(db, ch)]
    return {"gates": gs, "overall": views._overall(gs)}


class ApprovalIn(BaseModel):
    decision: str = "APPROVED"
    comment: str = Field(default="", max_length=2000)


@router.post("/api/changes/{change_id}/release-approvals", status_code=201)
def release_approval(change_id: str, body: ApprovalIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    a = gates.approve_release(db, user, change_id, body.decision, body.comment)
    return {"id": a.id, "decision": a.decision, "expires_at": views.iso(a.expires_at), "binding": a.binding}


class ReleaseIn(BaseModel):
    approval_id: str | None = None


@router.post("/api/changes/{change_id}/releases", status_code=201)
def create_release(change_id: str, body: ReleaseIn, db: Session = Depends(get_db), user: User = Depends(current_user),
                   idempotency_key: str | None = Header(default=None)) -> dict:
    return release.execute_release(db, user, change_id, idempotency_key, body.approval_id)


@router.post("/api/releases/{release_id}/promote")
def promote(release_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return release.promote(db, user, release_id)


@router.post("/api/releases/{release_id}/monitoring/advance")
def advance(release_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return release.advance_window(db, user, release_id)


@router.get("/api/releases/{release_id}/monitoring")
def monitoring(release_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return release.monitoring_view(db, user, release_id)


@router.post("/api/alerts/{alert_id}/investigate")
def investigate_alert(alert_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return release.investigate_alert(db, user, alert_id)


class RollbackIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    alert_id: str | None = None


@router.post("/api/releases/{release_id}/rollback-requests", status_code=201)
def rollback_request(release_id: str, body: RollbackIn, db: Session = Depends(get_db), user: User = Depends(current_user),
                     idempotency_key: str | None = Header(default=None)) -> dict:
    return release.request_rollback(db, user, release_id, body.reason, body.alert_id, idempotency_key)


class DecisionIn(BaseModel):
    decision: str
    comment: str = Field(default="", max_length=2000)


@router.post("/api/rollbacks/{rollback_id}/decision")
def rollback_decision(rollback_id: str, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return release.decide_rollback(db, user, rollback_id, body.decision, body.comment)


@router.post("/api/changes/{change_id}/cancel")
def cancel(change_id: str, body: DecisionIn | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return views.change_summary(lifecycle.cancel(db, user, change_id, body.comment if body else ""))


class ResumeIn(BaseModel):
    thread_id: str


@router.post("/api/changes/{change_id}/workflow/resume")
def resume(change_id: str, body: ResumeIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "investigate.run")
    ch = get_change(db, user.tenant_id, change_id)
    final = graph.resume(db, ch, body.thread_id, user.roles, lifecycle.tool_factory(db, ch), user.id)
    return {"thread_id": body.thread_id, "completed": final.get("completed", []), "errors": final.get("errors", [])}


class CopilotIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/api/changes/{change_id}/copilot")
def copilot(change_id: str, body: CopilotIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    return views.copilot_answer(db, user, change_id, body.message)


@router.get("/api/changes/{change_id}/audit")
def change_audit(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "audit.read")
    ch = get_change(db, user.tenant_id, change_id)
    ev = db.execute(select(AuditEvent).where(AuditEvent.change_id == ch.id).order_by(AuditEvent.id)).scalars()
    return {"events": [{"id": e.id, "at": views.iso(e.created_at), "actor": e.actor_id, "action": e.action, "status": e.status,
                        "reason": e.reason, "version_refs": e.version_refs, "input_refs": e.input_refs, "hash": e.hash,
                        "prev_hash": e.prev_hash} for e in ev],
            "chain": audit.verify_chain(db, user.tenant_id)}


@router.get("/api/changes/{change_id}/traceability")
def trace(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "change.read")
    return views.traceability(db, user, change_id)


@router.get("/api/changes/{change_id}/report")
def report(change_id: str, format: str = "md", db: Session = Depends(get_db), user: User = Depends(current_user)):
    require(user, "change.read")
    if format == "json":
        return views.change_detail(db, user, change_id)
    md = views.report_markdown(db, user, change_id)
    return PlainTextResponse(md, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{change_id}-report.md"'})


@router.get("/api/changes/{change_id}/telemetry")
def change_telemetry(change_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return views.telemetry(db, user, change_id)


@router.get("/api/metrics/process")
def process_metrics(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return views.process_metrics(db, user)


# ---------------------------------------------------------------- knowledge

@router.get("/api/knowledge/documents")
def documents(user: User = Depends(current_user)) -> dict:
    kb = get_kb()
    return {"documents": [{"doc_id": d.doc_id, "version": d.version, "title": d.title, "status": d.status,
                           "effective_date": d.effective_date, "access": d.access, "flags": kb.flags_for(d),
                           "sections": [{"section": s.section, "heading": s.heading} for s in d.sections]}
                          for d in kb.visible_docs(user.roles)], "conflicts": kb.conflicts(),
            "mode": "lexical BM25 (offline); embeddings unconfigured"}


@router.get("/api/knowledge/search")
def search(q: str = Query(min_length=2, max_length=300), include_unapproved: bool = False, user: User = Depends(current_user)) -> dict:
    return {"results": get_kb().search(q, user.roles, k=6, include_unapproved=include_unapproved)}


@router.get("/api/evidence/{source_id}/{version}/{section}")
def excerpt(source_id: str, version: str, section: str, user: User = Depends(current_user)) -> dict:
    return get_kb().get_excerpt(source_id, version, section, user.roles)


# ------------------------------------------------------------- image sandbox

@router.post("/api/images", status_code=201)
async def upload_image(request: Request, purpose: str, consent: bool = False, retention_days: int = 7,
                       training_consent: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    require(user, "image.upload")
    data = await request.body()
    up = uploads.upload(db, user, data, purpose=purpose, consent=consent, retention_days=retention_days, training_consent=training_consent)
    return {"id": up.id, "media_type": up.media_type, "width": up.width, "height": up.height, "metadata_stripped": up.metadata_stripped,
            "delete_after": views.iso(up.delete_after), "training_consent": up.training_consent,
            "note": "Stored privately; no inference of identity or traits is performed; never sent to a language model."}


@router.delete("/api/images/{image_id}")
def delete_image(image_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return uploads.delete(db, user, image_id)


@router.get("/api/images")
def list_images(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    rows = db.execute(select(ImageUpload).where(ImageUpload.tenant_id == user.tenant_id)).scalars()
    return {"enabled": get_settings().image_sandbox_enabled,
            "images": [{"id": i.id, "status": i.status, "purpose": i.purpose, "deletion_report": i.deletion_report} for i in rows]}


# --------------------------------------------------------------------- demo

@router.post("/api/demo/reset")
def demo_reset(user: User = Depends(current_user)) -> dict:
    require(user, "demo.reset")
    if not get_settings().demo:
        raise Forbidden("demo_only", "Reset is only available in demo mode")
    from app.seed import reset
    reset()
    return {"status": "reset", "seeded_change": "BR-101"}
