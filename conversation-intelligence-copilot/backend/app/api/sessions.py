"""Session memory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.memory.store import get_memory
from app.observability.store import get_telemetry

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(limit: int = 20) -> list[dict]:
    return get_memory().sessions(min(limit, 100))


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    s = get_memory().get_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.get("/{session_id}/responses")
def session_responses(session_id: str) -> list[dict]:
    s = get_memory().get_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    tel = get_telemetry()
    return [r for t in s["turns"] if (r := tel.response(t["request_id"]))]


@router.delete("/{session_id}")
def clear_session(session_id: str) -> dict:
    ok = get_memory().clear_session(session_id)
    get_telemetry().audit("memory", "session_cleared", {"found": ok}, session_id=session_id)
    return {"cleared": ok}
