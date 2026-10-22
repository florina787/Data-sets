"""Conversation-first workspace API: personas, conversations, messages (JSON or Server-Sent Events), cancellation,
visualization schema and authorized metrics. Request and response bodies are validated Pydantic models."""
from __future__ import annotations

import asyncio
import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from analytics.semantic import METRICS, SEMANTIC_LAYER_VERSION
from backend import runtime as R
from backend.api.deps import Ctx, current, require
from conversation import personas, service
from conversation.schemas import CHART_TYPES, CONTRACT_VERSION, VIZ_SCHEMA_VERSION, ChartSpec, MessageResponse
from harness.errors import LoadShed

router = APIRouter(prefix="/api")

# permission needed to read each data product's metrics (mirrors the tools that serve them)
PRODUCT_PERMISSION = {"finance": "finance:read", "wealth": "wealth:read", "investment": "investment:read_aggregate", "risk": "risk:read_aggregate",
                      "strategy": "decisions:read"}


class ConversationIn(BaseModel):
    persona: str | None = Field(None, max_length=40)


class ConversationPatch(BaseModel):
    persona: str | None = Field(None, max_length=40)
    title: str | None = Field(None, max_length=200)


class ScenarioIn(BaseModel):
    model_config = {"extra": "forbid"}
    preset: str | None = Field(None, pattern="^(base|bull|bear|severe_stress)$")
    equity_shock: float | None = Field(None, ge=-0.8, le=0.8)
    rate_shock_bps: float | None = Field(None, ge=-500, le=500)


class MessageContext(BaseModel):
    """Structured follow-up controls from the workspace (filters, drill-downs, scenario sliders). Never grants access."""
    model_config = {"extra": "forbid"}
    months: int | None = Field(None, ge=1, le=24)
    group_by: str | None = Field(None, pattern="^(asset_class|vehicle|region|strategy|product|segment|sector|issuer)$")
    client_id: str | None = Field(None, pattern=r"^C-\d{5}$")
    scenario: ScenarioIn | None = None
    focus: str | None = Field(None, max_length=120)
    intent: str | None = Field(None, max_length=40)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    persona: str | None = Field(None, max_length=40)
    client_message_id: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{8,64}$")
    language: str | None = Field(None, pattern="^(en|fr|es|hi|ta|ko)$")
    context: MessageContext = MessageContext()


def _overrides(body: MessageIn) -> dict:
    c = body.context.model_dump(exclude_none=True)
    if "scenario" in c:
        c["scenario"] = {k: v for k, v in c["scenario"].items() if v is not None}
    return c


@router.get("/personas")
def get_personas(ctx: Ctx = Depends(current)):
    return personas.catalogue(ctx.principal.roles)


@router.get("/viz/schema")
def viz_schema(ctx: Ctx = Depends(current)):
    return {"schema_version": VIZ_SCHEMA_VERSION, "contract_version": CONTRACT_VERSION, "chart_types": list(CHART_TYPES),
            "chart_spec": ChartSpec.model_json_schema(), "message_response": MessageResponse.model_json_schema()}


@router.get("/metrics/authorized")
def authorized_metrics(ctx: Ctx = Depends(current)):
    eng = R.engine()
    allowed = {dp: eng.authorize(ctx.principal, perm).allowed for dp, perm in PRODUCT_PERMISSION.items()}
    return {"semantic_layer_version": SEMANTIC_LAYER_VERSION,
            "metrics": [{"id": m.id, "name": m.name, "unit": m.unit, "data_product": m.data_product, "definition": m.definition}
                        for m in METRICS.values() if allowed.get(m.data_product, False)],
            "data_products": allowed}


@router.get("/conversations")
def list_conversations(q: str | None = Query(None, max_length=80), limit: int = Query(50, ge=1, le=100), ctx: Ctx = Depends(require("ask:use"))):
    return {"conversations": service.list_conversations(ctx.principal, q, limit), "recent_questions": service.recent_questions(ctx.principal)}


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationIn, ctx: Ctx = Depends(require("ask:use"))):
    return service.create_conversation(ctx.principal, body.persona)


def _nf(fn):
    try:
        return fn()
    except service.NotFound as e:
        raise HTTPException(404, {"code": "NOT-FOUND", "message": "conversation not found"}) from e


@router.get("/conversations/{cid}")
def get_conversation(cid: str, ctx: Ctx = Depends(require("ask:use"))):
    return _nf(lambda: service.get_conversation(ctx.principal, ctx.store, cid))


@router.patch("/conversations/{cid}")
def patch_conversation(cid: str, body: ConversationPatch, ctx: Ctx = Depends(require("ask:use"))):
    return _nf(lambda: service.update_conversation(ctx.principal, cid, persona=body.persona, title=body.title))


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, ctx: Ctx = Depends(require("ask:use"))):
    _nf(lambda: service.update_conversation(ctx.principal, cid, archived=True))
    return {"id": cid, "archived": True}


@router.post("/conversations/{cid}/messages", response_model=MessageResponse)
def post_message(cid: str, body: MessageIn, ctx: Ctx = Depends(require("ask:use"))):
    try:
        return _nf(lambda: service.process_message(ctx.principal, ctx.store, cid, body.text, body.persona, body.client_message_id,
                                                   _overrides(body), body.language))
    except LoadShed as e:
        raise HTTPException(503, {"code": "LOAD-SHED", "message": str(e)}, headers={"Retry-After": "5"}) from e


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/conversations/{cid}/messages/stream")
async def stream_message(cid: str, body: MessageIn, request: Request, ctx: Ctx = Depends(require("ask:use"))):
    """Server-Sent Events: started, stage, intent, plan, agent, result, error, done. Events are emitted as the backend
    actually reaches each step. A client disconnect cancels the workflow; re-posting with the same client_message_id
    returns the stored result instead of re-running (idempotent retry / reconnection)."""
    _nf(lambda: service.get_conversation(ctx.principal, ctx.store, cid))
    q: queue.Queue = queue.Queue()
    started: dict = {}

    def emit(event: str, data: dict) -> None:
        if event == "started":
            started.update(data)
        q.put((event, data))

    def work() -> None:
        try:
            out = service.process_message(ctx.principal, ctx.store, cid, body.text, body.persona, body.client_message_id, _overrides(body),
                                          body.language, emit=emit)
            q.put(("result", out))
        except LoadShed as e:
            q.put(("error", {"code": "LOAD-SHED", "message": str(e), "retry_after_s": 5}))
        except Exception as e:  # noqa: BLE001 - reported to the client as a typed error event, never as a stack trace
            q.put(("error", {"code": "INTERNAL", "message": e.__class__.__name__}))
        finally:
            q.put(("done", {}))

    threading.Thread(target=work, daemon=True).start()

    async def gen():
        yield ": stream open\n\n"
        while True:
            if await request.is_disconnected():
                if started.get("request_id"):
                    service.cancel(started["request_id"])
                return
            try:
                event, data = await asyncio.to_thread(q.get, True, 0.25)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            yield _sse(event, data)
            if event == "done":
                return

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/conversations/requests/{request_id}/cancel")
def cancel_request(request_id: str, ctx: Ctx = Depends(require("ask:use"))):
    return {"request_id": request_id, "cancelled": service.cancel(request_id, ctx.principal)}
