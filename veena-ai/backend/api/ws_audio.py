"""Real-time audio WebSocket: PCM in, VAD/partial/final/question events out.

Client -> server
    binary: audio frame (see audio/pcm.py)
    text:   {"type": "pause"} | {"type": "resume"} | {"type": "stop"}
Server -> client
    {"type": "status", "state": "loading_model" | "ready" | "paused" | "listening" | "stopped", ...}
    {"type": "vad" | "partial" | "final" | "discard" | "question" | "error", ...}
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..agents.question_detection import QuestionDetector
from ..analytics import metrics as M
from ..audio.pcm import FrameError, decode_frame
from ..llm.ollama import LLMUnavailable
from ..llm.select import resolve_text_model
from ..security.auth import authorize_websocket
from ..transcription.streaming import StreamingTranscriber
from ..transcription.vad import make_vad

router = APIRouter()
log = logging.getLogger("veena.audio")


@router.websocket("/ws/audio")
async def audio_ws(ws: WebSocket):
    st = ws.app.state.veena
    if not await authorize_websocket(ws, st.settings.token, st.settings.allowed_origins):
        return
    session_id = ws.query_params.get("session_id", "")
    source = ws.query_params.get("source", "mic")
    if source not in ("mic", "system") or not st.store.get_session(session_id):
        await ws.send_json({"type": "error", "where": "setup", "message": "unknown session or audio source"})
        await ws.close(code=4400)
        return
    settings = st.store.get_settings()
    send_lock = asyncio.Lock()

    async def send(ev: dict) -> None:
        async with send_lock:
            try:
                await ws.send_json(ev)
            except (RuntimeError, WebSocketDisconnect):
                pass

    detector = QuestionDetector(llm=st.llm)
    try:
        detector.model = resolve_text_model(settings.get("text_model"), await st.catalog.installed())
    except LLMUnavailable:
        detector.model = None

    async def sink(ev: dict) -> None:
        if ev["type"] == "final" and ev.get("text"):
            msg = st.store.add_message(
                session_id,
                "transcript",
                ev["text"],
                meta={"source": source, "utterance_id": ev["utterance_id"], "start_s": ev["start_s"], "end_s": ev["end_s"]},
            )
            ev["message_id"] = msg.id
            await send(ev)
            with st.metrics.timer(M.QUESTION_DETECT):
                q = await detector.detect(
                    ev["text"],
                    context_ref=str(msg.id),
                    has_history=True,
                    escalate=bool(settings.get("question_escalation")),
                )
            if q.is_question and not q.duplicate:
                await send({"type": "question", **q.to_dict(), "source": source})
            return
        await send(ev)

    asr = st.asr(settings.get("asr_model") or "base", settings.get("asr_language"))
    if not asr.loaded:
        await send({"type": "status", "state": "loading_model", "model": asr.model_size})
        try:
            await asyncio.to_thread(asr.load)
        except Exception as e:  # noqa: BLE001
            await send({"type": "error", "where": "asr_load", "message": f"Could not load speech model: {e}"})
            await ws.close(code=1011)
            return
    vad = make_vad()
    tr = StreamingTranscriber(asr, vad, sink, metrics=st.metrics)
    tr.start()
    await send({"type": "status", "state": "ready", "vad": vad.name, "asr": asr.model_size, "device": asr.device})
    bad_frames = 0
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                try:
                    ts, pcm = decode_frame(msg["bytes"])
                except FrameError as e:
                    bad_frames += 1
                    if bad_frames > 20:
                        await send({"type": "error", "where": "frame", "message": str(e)})
                        break
                    continue
                tr.submit(ts, pcm)
            elif msg.get("text"):
                try:
                    cmd = json.loads(msg["text"]).get("type")
                except (json.JSONDecodeError, AttributeError):
                    continue
                if cmd == "pause":
                    tr.pause()
                    await send({"type": "status", "state": "paused"})
                elif cmd == "resume":
                    tr.resume()
                    await send({"type": "status", "state": "listening"})
                elif cmd == "stop":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await tr.stop()
        await send({"type": "status", "state": "stopped", "dropped_frames": tr.dropped_frames})
        try:
            await ws.close()
        except RuntimeError:
            pass
