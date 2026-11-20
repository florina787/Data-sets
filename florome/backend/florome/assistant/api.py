"""Assistant API: /api/v1/assistant. Read permission is enough; answers only ever contain the caller's tenant data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from florome.api.deps import get_ctx, get_db, require
from florome.assistant import service
from florome.context import AppContext
from florome.security.rbac import Principal

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    page: str = Field(pattern=r"^[a-z]{2,20}$")
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=64)
    context: dict[str, str] = Field(default_factory=dict)


@router.get("/pages/{page}")
def page(page: str, p: Principal = Depends(require("read"))) -> dict[str, Any]:
    try:
        return service.page_config(page)
    except KeyError as exc:
        raise HTTPException(404, "Unknown page") from exc


@router.post("/ask")
async def ask(body: AskRequest, request: Request, p: Principal = Depends(require("read")), db: Session = Depends(get_db),
              ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    try:
        conv, ans = await service.answer(db, ctx, p, body.page, body.question, body.conversation_id, body.context,
                                         list(request.app.state.request_samples))
    except KeyError as exc:
        raise HTTPException(404, "Unknown page") from exc
    except LookupError as exc:
        raise HTTPException(404, "Conversation not found") from exc
    return {"conversation_id": conv.id, **ans}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, p: Principal = Depends(require("read")), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        return service.history(db, p, conversation_id)
    except LookupError as exc:
        raise HTTPException(404, "Conversation not found") from exc
