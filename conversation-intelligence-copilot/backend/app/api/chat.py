"""Chat endpoints: synchronous and Server-Sent Events streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.graph import run_chat, stream_chat
from app.schemas.api_response import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
def chat(req: ChatRequest) -> dict:
    return run_chat(req.question, req.session_id, req.dataset_mode, req.selected_conversation_id)


@router.post("/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Streams real node_start / node_end events as the graph executes, then the final response.

    Closing the connection cancels the run at the next node boundary.
    """

    def gen():
        for event in stream_chat(req.question, req.session_id, req.dataset_mode, req.selected_conversation_id):
            yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
