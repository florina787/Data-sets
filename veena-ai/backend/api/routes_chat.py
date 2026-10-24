"""Sessions, streaming chat, question detection and summaries."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..agents.graph import UnifiedRequest
from ..agents.meeting import summarize, to_markdown
from ..llm.ollama import LLMUnavailable
from ..llm.select import resolve_text_model
from ..security.prompt_guard import SECURITY_PREAMBLE, wrap_untrusted
from .state import AppState, get_state

router = APIRouter(prefix="/api")


class NewSession(BaseModel):
    title: str = Field(default="New conversation", max_length=200)
    mode: str = Field(default="conversation", pattern="^(conversation|screen|interview|meeting)$")


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.get("/sessions")
async def list_sessions(q: str | None = None, mode: str | None = None, st: AppState = Depends(get_state)):
    return st.store.list_sessions(query=q, mode=mode)


@router.post("/sessions")
async def create_session(body: NewSession, st: AppState = Depends(get_state)):
    return st.store.create_session(body.title, body.mode).model_dump(mode="json")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, st: AppState = Depends(get_state)):
    cs = st.store.get_session(session_id)
    if not cs:
        raise HTTPException(404, "session not found")
    return {"session": cs.model_dump(mode="json"), "messages": st.store.messages(session_id)}


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: Rename, st: AppState = Depends(get_state)):
    cs = st.store.rename_session(session_id, body.title)
    if not cs:
        raise HTTPException(404, "session not found")
    return cs.model_dump(mode="json")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, st: AppState = Depends(get_state)):
    if not st.store.delete_session(session_id):
        raise HTTPException(404, "session not found")
    return {"deleted": session_id}


@router.delete("/sessions")
async def clear_all(confirm: bool = False, st: AppState = Depends(get_state)):
    if not confirm:
        raise HTTPException(400, "pass confirm=true to delete all history")
    return {"deleted_sessions": st.store.clear_history()}


@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str, fmt: str = "markdown", st: AppState = Depends(get_state)):
    if fmt not in ("markdown", "json"):
        raise HTTPException(400, "fmt must be markdown or json")
    out = st.store.export_session(session_id, fmt)
    if out is None:
        raise HTTPException(404, "session not found")
    return PlainTextResponse(out, media_type="application/json" if fmt == "json" else "text/markdown")


class TranscriptLine(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="typed", pattern="^(typed|mic|system)$")


@router.post("/sessions/{session_id}/transcript")
async def add_transcript(session_id: str, body: TranscriptLine, st: AppState = Depends(get_state)):
    """Manually added transcript lines (e.g. pasted meeting notes)."""
    if not st.store.get_session(session_id):
        raise HTTPException(404, "session not found")
    m = st.store.add_message(session_id, "transcript", body.text, meta={"source": body.source})
    return st.store._message_dict(m)


@router.post("/chat")
async def chat(req: UnifiedRequest, st: AppState = Depends(get_state)):
    request_id = uuid.uuid4().hex

    async def gen():
        async for ev in st.engine.run(req, request_id):
            yield json.dumps(ev) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"x-request-id": request_id})


@router.post("/chat/{request_id}/cancel")
async def cancel(request_id: str, st: AppState = Depends(get_state)):
    return {"cancelled": st.engine.cancel(request_id)}


class DetectReq(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    has_history: bool = False


@router.post("/questions/detect")
async def detect(body: DetectReq, st: AppState = Depends(get_state)):
    s = st.store.get_settings()
    try:
        st.detector.model = resolve_text_model(s.get("text_model"), await st.catalog.installed())
    except LLMUnavailable:
        st.detector.model = None
    with st.metrics.timer("question.detect_ms"):
        res = await st.detector.detect(body.text, has_history=body.has_history, escalate=bool(s.get("question_escalation")), remember=False)
    return res.to_dict()


async def _text_model(st: AppState) -> str:
    try:
        return resolve_text_model(st.store.get_settings().get("text_model"), await st.catalog.installed())
    except LLMUnavailable as e:
        raise HTTPException(503, str(e)) from e


@router.post("/sessions/{session_id}/summary")
async def session_summary(session_id: str, st: AppState = Depends(get_state)):
    if not st.store.get_session(session_id):
        raise HTTPException(404, "session not found")
    msgs = st.store.messages(session_id)
    if not msgs:
        raise HTTPException(400, "nothing to summarise yet")
    model = await _text_model(st)
    convo = "\n".join(f"{m['role']}: {m['content'][:1500]}" for m in msgs[-60:])
    summary = await st.llm.chat(
        model,
        [
            {
                "role": "system",
                "content": "Summarise this conversation in 3-6 bullet points, then list up to 3 suggested follow-up questions under 'Follow-ups'.\n\n"
                + SECURITY_PREAMBLE,
            },
            {"role": "user", "content": wrap_untrusted("conversation", convo)},
        ],
        options={"temperature": 0.2, "num_predict": 400},
    )
    st.store.set_summary(session_id, summary)
    return {"summary": summary, "model": model}


@router.post("/sessions/{session_id}/followups")
async def followups(session_id: str, st: AppState = Depends(get_state)):
    msgs = [m for m in st.store.messages(session_id, limit=6) if m["role"] in ("user", "assistant")]
    if not msgs:
        return {"followups": []}
    model = await _text_model(st)
    convo = "\n".join(f"{m['role']}: {m['content'][:1200]}" for m in msgs)
    raw = await st.llm.chat(
        model,
        [
            {
                "role": "system",
                "content": 'Suggest 3 short, specific follow-up questions the user might ask next. Return JSON only: {"followups": [string]}',
            },
            {"role": "user", "content": wrap_untrusted("conversation", convo)},
        ],
        fmt="json",
        options={"temperature": 0.5, "num_predict": 160},
    )
    try:
        items = [str(x)[:200] for x in json.loads(raw).get("followups", [])][:3]
    except (json.JSONDecodeError, AttributeError):
        items = []
    return {"followups": items}


@router.post("/meeting/{session_id}/summarize")
async def meeting_summary(session_id: str, st: AppState = Depends(get_state)):
    if not st.store.get_session(session_id):
        raise HTTPException(404, "session not found")
    lines = [f"[{m['created_at'][11:19]}] {m['content']}" for m in st.store.messages(session_id) if m["role"] == "transcript"]
    if not lines:
        raise HTTPException(400, "no transcript in this session yet")
    model = await _text_model(st)
    notes = await summarize(st.llm, model, lines)
    md = to_markdown(notes)
    st.store.set_summary(session_id, md)
    st.store.add_message(
        session_id, "assistant", md, answer_style="meeting_summary", model=model, meta={"agent": "meeting", "notes_json": notes}
    )
    return {"notes": notes, "markdown": md, "model": model}
