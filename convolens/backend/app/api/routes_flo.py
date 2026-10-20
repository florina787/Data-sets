"""Flo assistant (SSE streaming, approval resume, cancel), investigations, feedback, actions and observability."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.graph.builder import EDGES, NODE_ORDER
from app.graph.runner import RunError, get_runner
from app.ingestion.jobs import get_jobs
from app.llm.provider import provider_status
from app.models.orm import Action, ActionEvent, EvalRun, Feedback, Investigation, Run
from app.models.schemas import Filters
from app.observability import tracing
from app.retrieval.index import semantic_status
from app.security.sessions import create_session, require_session

router = APIRouter(prefix="/api")


def _sse(gen):
    def stream():
        try:
            for ev in gen:
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except RunError as exc:
            yield f"data: {json.dumps({'type': 'error', 'status': exc.status, 'message': str(exc)})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/flo/sessions")
def new_session(db: Session = Depends(get_db)):
    sid, token = create_session(db)
    return {"session_id": sid, "session_token": token}


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    dataset_id: str = Field(max_length=40)
    mode: str = Field(pattern="^(demo|connected)$")
    page: str | None = Field(default=None, max_length=60)
    filters: Filters = Field(default_factory=Filters)


@router.post("/flo/chat")
def chat(body: ChatIn, session_id: str = Depends(require_session)):
    runner = get_runner()
    gen = runner.start(session_id=session_id, question=body.question, dataset_id=body.dataset_id, mode=body.mode,
                       page=body.page, filters=body.filters.model_dump(mode="json", exclude_defaults=True))
    try:
        first = next(gen)  # surface validation errors (mode/dataset mismatch) as HTTP errors before streaming
    except RunError as exc:
        raise HTTPException(exc.status, str(exc))

    def chain():
        yield first
        yield from gen
    return _sse(chain())


class Decision(BaseModel):
    decision: str = Field(pattern="^(approve|save_as_proposed|reject)$")
    reviewer: str = Field(default="reviewer", max_length=80)
    note: str | None = Field(default=None, max_length=500)
    edits: dict = Field(default_factory=dict)


@router.post("/flo/runs/{request_id}/approval")
def approve(request_id: str, body: Decision, session_id: str = Depends(require_session)):
    gen = get_runner().resume(session_id=session_id, request_id=request_id, decision=body.model_dump())
    try:
        first = next(gen)
    except RunError as exc:
        raise HTTPException(exc.status, str(exc))

    def chain():
        yield first
        yield from gen
    return _sse(chain())


@router.post("/flo/runs/{request_id}/cancel")
def cancel(request_id: str, session_id: str = Depends(require_session)):
    try:
        get_runner().cancel(session_id, request_id)
    except RunError as exc:
        raise HTTPException(exc.status, str(exc))
    return {"cancel_requested": True}


def _run_dict(r: Run, full: bool = False) -> dict:
    d = {"request_id": r.id, "dataset_id": r.dataset_id, "mode": r.mode, "question": r.question, "question_type": r.question_type,
         "status": r.status, "model_id": r.model_id, "prompt_versions": r.prompt_versions, "input_tokens": r.input_tokens,
         "output_tokens": r.output_tokens, "latency_ms": r.latency_ms, "error": r.error, "started_at": r.started_at.isoformat(),
         "langsmith_run_id": r.langsmith_run_id, "tool_count": len(r.tool_calls or [])}
    if full:
        d.update(nodes=r.nodes, tool_calls=r.tool_calls, response=r.response, evidence_ids=r.evidence_ids)
    return d


@router.get("/flo/runs")
def my_runs(session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    rows = db.scalars(select(Run).where(Run.session_id == session_id).order_by(Run.started_at.desc()).limit(50)).all()
    return {"runs": [_run_dict(r) for r in rows]}


@router.get("/flo/runs/{request_id}")
def run_detail(request_id: str, session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    r = db.get(Run, request_id)
    if r is None or r.session_id != session_id:
        raise HTTPException(404, "Run not found for this session")
    return _run_dict(r, full=True)


@router.get("/flo/runs/{request_id}/trace-link")
def trace_link(request_id: str, session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    r = db.get(Run, request_id)
    if r is None or r.session_id != session_id:
        raise HTTPException(404, "Run not found for this session")
    if not tracing.status()["configured"]:
        return {"available": False, "reason": "LangSmith not configured"}
    if not r.langsmith_run_id:
        return {"available": False, "reason": "This run was not traced (tracing was off when it ran)."}
    url = tracing.trace_url(r.langsmith_run_id)
    return {"available": bool(url), "url": url, "langsmith_run_id": r.langsmith_run_id,
            "reason": None if url else "Trace not yet available in LangSmith; retry shortly."}


class FeedbackIn(BaseModel):
    score: int = Field(ge=0, le=1)
    comment: str | None = Field(default=None, max_length=1000)
    correction: str | None = Field(default=None, max_length=2000)


@router.post("/flo/runs/{request_id}/feedback")
def feedback(request_id: str, body: FeedbackIn, session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    r = db.get(Run, request_id)
    if r is None or r.session_id != session_id:
        raise HTTPException(404, "Run not found for this session")
    sent = tracing.send_feedback(r.langsmith_run_id, body.score, body.comment or body.correction) if r.langsmith_run_id else False
    db.add(Feedback(run_id=request_id, score=body.score, comment=body.comment, correction=body.correction, sent_to_langsmith=sent))
    db.commit()
    return {"saved": True, "sent_to_langsmith": sent}


class InvestigationIn(BaseModel):
    request_id: str
    title: str = Field(min_length=1, max_length=200)


@router.post("/flo/investigations")
def save_investigation(body: InvestigationIn, session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    r = db.get(Run, body.request_id)
    if r is None or r.session_id != session_id or not r.response:
        raise HTTPException(404, "Completed run not found for this session")
    inv = Investigation(session_id=session_id, run_id=r.id, dataset_id=r.dataset_id, title=body.title, question=r.question,
                        filters=(r.response.get("scope") or {}).get("filters", {}), response=r.response)
    db.add(inv)
    db.commit()
    return {"id": inv.id}


@router.get("/flo/investigations")
def investigations(session_id: str = Depends(require_session), db: Session = Depends(get_db)):
    rows = db.scalars(select(Investigation).where(Investigation.session_id == session_id).order_by(Investigation.created_at.desc())).all()
    return {"investigations": [{"id": i.id, "title": i.title, "question": i.question, "dataset_id": i.dataset_id, "filters": i.filters,
                                "response": i.response, "run_id": i.run_id, "created_at": i.created_at.isoformat()} for i in rows]}


# ------------------------------------------------------------------------------------------------ actions
STATUSES = ["proposed", "approved", "in_progress", "completed", "rejected"]
TRANSITIONS = {"proposed": {"approved", "rejected"}, "approved": {"in_progress", "rejected"}, "in_progress": {"completed"},
               "completed": set(), "rejected": {"proposed"}}


def _action(a: Action) -> dict:
    return {"id": a.id, "title": a.title, "issue": a.issue, "intervention": a.intervention, "proposed_department": a.proposed_department,
            "owner": a.owner, "owner_confirmed": a.owner_confirmed, "due_date": a.due_date, "intended_outcome": a.intended_outcome,
            "success_measure": a.success_measure, "status": a.status, "investigation": a.investigation, "brief": a.brief,
            "dataset_id": a.dataset_id, "created_at": a.created_at.isoformat(),
            "history": [{"from": h.from_status, "to": h.to_status, "actor": h.actor, "note": h.note, "at": h.created_at.isoformat()} for h in a.history]}


@router.get("/actions")
def list_actions(dataset_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Action).order_by(Action.created_at.desc())
    if dataset_id:
        q = q.where(Action.dataset_id == dataset_id)
    return {"actions": [_action(a) for a in db.scalars(q)], "statuses": STATUSES}


class ActionUpdate(BaseModel):
    actor: str = Field(min_length=1, max_length=80)
    status: str | None = Field(default=None, pattern="^(proposed|approved|in_progress|completed|rejected)$")
    owner: str | None = Field(default=None, max_length=120)
    confirm_owner: bool | None = None
    due_date: date | None = None
    success_measure: str | None = Field(default=None, max_length=600)
    intended_outcome: str | None = Field(default=None, max_length=600)
    note: str | None = Field(default=None, max_length=500)


@router.patch("/actions/{action_id}")
def update_action(action_id: int, body: ActionUpdate, db: Session = Depends(get_db)):
    a = db.get(Action, action_id)
    if a is None:
        raise HTTPException(404, "Action not found")
    if body.status and body.status != a.status:
        if body.status not in TRANSITIONS[a.status]:
            raise HTTPException(409, f"Cannot move from {a.status} to {body.status}")
        if body.status in ("approved", "in_progress") and not (body.owner or a.owner):
            raise HTTPException(409, "An owner must be entered before approval")
        a.history.append(ActionEvent(from_status=a.status, to_status=body.status, actor=body.actor, note=body.note))
        a.status = body.status
    if body.owner is not None:
        a.owner = body.owner or None
        a.owner_confirmed = bool(body.confirm_owner and body.owner)
        a.history.append(ActionEvent(from_status=a.status, to_status=a.status, actor=body.actor, note=f"Owner set to {body.owner or '—'}" + (" (confirmed)" if a.owner_confirmed else "")))
    elif body.confirm_owner and a.owner:
        a.owner_confirmed = True
        a.history.append(ActionEvent(from_status=a.status, to_status=a.status, actor=body.actor, note="Owner confirmed"))
    for f in ("success_measure", "intended_outcome"):
        if getattr(body, f) is not None:
            setattr(a, f, getattr(body, f))
    if body.due_date:
        a.due_date = body.due_date.isoformat()
    db.commit()
    return _action(a)


# ------------------------------------------------------------------------------------------------ observability
@router.get("/status")
def status(db: Session = Depends(get_db)):
    s = get_settings()
    return {"model": provider_status(), "langsmith": tracing.status(), "retrieval": semantic_status(),
            "limits": {"max_tool_calls": s.flo_max_tool_calls, "max_iterations": s.flo_max_iterations,
                       "max_tokens_per_request": s.flo_max_tokens_per_request, "timeout_s": s.flo_timeout_s},
            "auth": "No user authentication, SSO or RBAC is implemented. Run locally; see docs/SECURITY.md."}


@router.get("/observability/summary")
def obs_summary(dataset_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Run.mode, Run.status, func.count(), func.avg(Run.latency_ms), func.sum(Run.input_tokens), func.sum(Run.output_tokens))
    if dataset_id:
        q = q.where(Run.dataset_id == dataset_id)
    rows = db.execute(q.group_by(Run.mode, Run.status)).all()
    tools: dict[str, dict] = {}
    for (calls,) in db.execute(select(Run.tool_calls).where(Run.dataset_id == dataset_id) if dataset_id else select(Run.tool_calls)).all():
        for c in calls or []:
            t = tools.setdefault(c["tool"], {"calls": 0, "errors": 0})
            t["calls"] += 1
            t["errors"] += c.get("status") not in ("ok", "skipped")
    models = db.execute(select(Run.model_id, Run.prompt_versions, func.count()).group_by(Run.model_id, Run.prompt_versions)).all()
    fb = db.execute(select(Feedback.score, func.count()).group_by(Feedback.score)).all()
    return {"runs": [{"mode": m, "status": s, "count": n, "avg_latency_ms": round(l or 0), "input_tokens": int(ti or 0), "output_tokens": int(to or 0)}
                     for m, s, n, l, ti, to in rows],
            "tools": [{"tool": k, **v} for k, v in sorted(tools.items())],
            "models": [{"model_id": m or "rules (no model)", "prompt_versions": pv, "runs": n} for m, pv, n in models],
            "feedback": {("helpful" if s else "not_helpful"): n for s, n in fb},
            "cost": "Token counts are recorded per run. Cost is shown in LangSmith when tracing is configured; it is not estimated here.",
            "langsmith": tracing.status()}


@router.get("/observability/graph")
def graph_structure():
    return {"nodes": NODE_ORDER, "edges": [{"source": a, "target": b, "label": l} for a, b, l in EDGES]}


@router.get("/observability/evals")
def evals(db: Session = Depends(get_db)):
    rows = db.scalars(select(EvalRun).order_by(EvalRun.id.desc()).limit(300)).all()
    latest = {}
    for e in rows:
        latest.setdefault((e.suite, e.language, e.system, e.judgment), e)
    return {"results": [{"suite": e.suite, "judgment": e.judgment, "mode": e.mode, "system": e.system, "language": e.language,
                         "n": e.n, "passed": e.passed, "score": e.score, "details": e.details, "langsmith_experiment": e.langsmith_experiment,
                         "created_at": e.created_at.isoformat()} for e in latest.values()],
            "commands": {"demo": "python -m app.evaluation.run --system rules",
                         "connected": "python -m app.evaluation.run --system llm --dataset <dataset_id> --langsmith"}}


@router.post("/observability/evals/run")
def run_evals(system: str = Query("rules", pattern="^(rules|llm)$"), dataset_id: str | None = None):
    from app.evaluation.run import SUITES, run
    try:
        out = run(SUITES, system, dataset_id, langsmith=False)
    except SystemExit as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Evaluation failed: {type(exc).__name__}: {exc}")
    return out
