"""Interview practice endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..agents.interview import CATEGORIES, ROLES
from ..llm.ollama import LLMUnavailable
from ..llm.select import resolve_text_model
from .state import AppState, get_state

router = APIRouter(prefix="/api/interview")


class NewInterview(BaseModel):
    role: str
    focus: str = "mixed"
    resume_collection_id: str | None = None
    job_description: str | None = Field(default=None, max_length=20000)


class GenReq(BaseModel):
    count: int = Field(default=5, ge=1, le=10)


class AnswerReq(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


@router.get("/roles")
async def roles():
    return {"roles": ROLES, "categories": CATEGORIES}


@router.post("")
async def create(body: NewInterview, st: AppState = Depends(get_state)):
    if body.resume_collection_id and not st.kb.get_collection(body.resume_collection_id):
        raise HTTPException(404, "resume collection not found")
    cs = st.store.create_session(f"Practice: {ROLES.get(body.role, body.role)}", "interview")
    try:
        iv = st.coach.create(cs.id, body.role, body.focus, body.resume_collection_id, body.job_description)
    except ValueError as e:
        st.store.delete_session(cs.id)
        raise HTTPException(400, str(e)) from e
    return {"interview": iv.model_dump(mode="json"), "session": cs.model_dump(mode="json")}


async def _model(st: AppState) -> str | None:
    try:
        return resolve_text_model(st.store.get_settings().get("text_model"), await st.catalog.installed())
    except LLMUnavailable:
        return None


def _resume(st: AppState, iv) -> str:
    return st.kb.collection_text(iv.resume_collection_id) if iv.resume_collection_id else ""


@router.post("/{interview_id}/questions")
async def questions(interview_id: str, body: GenReq, st: AppState = Depends(get_state)):
    iv = st.coach.get(interview_id)
    if not iv:
        raise HTTPException(404, "interview not found")
    return await st.coach.generate_questions(iv, await _model(st), _resume(st, iv), body.count)


@router.post("/turns/{turn_id}/evaluate")
async def evaluate(turn_id: int, body: AnswerReq, st: AppState = Depends(get_state)):
    model = await _model(st)
    if not model:
        raise HTTPException(503, "No local model available to evaluate answers. Install one in Setup.")
    from ..memory.db import session as db_session
    from ..memory.tables import InterviewTurn

    with db_session(st.store.engine) as s:
        turn = s.get(InterviewTurn, turn_id)
    if not turn:
        raise HTTPException(404, "turn not found")
    iv = st.coach.get(turn.interview_id)
    try:
        fb = await st.coach.evaluate(turn_id, body.answer, model, _resume(st, iv))
    except ValueError as e:
        raise HTTPException(502, f"model returned an unusable evaluation: {e}") from e
    st.metrics.record("interview.score", fb["score"], unit="score", meta={"model": model, "category": turn.category})
    st.store.add_message(
        iv.chat_session_id, "user", body.answer, intent="practice_answer", meta={"turn_id": turn_id, "question": turn.question}
    )
    return fb


@router.get("/{interview_id}")
async def review(interview_id: str, st: AppState = Depends(get_state)):
    iv = st.coach.get(interview_id)
    if not iv:
        raise HTTPException(404, "interview not found")
    return {"interview": iv.model_dump(mode="json"), **st.coach.review(interview_id)}
