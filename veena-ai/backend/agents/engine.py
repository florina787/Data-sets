"""Runs one conversational turn: orchestrate -> stream -> govern -> persist -> measure."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ..analytics import metrics as M
from ..llm.ollama import GenerationStats, LLMUnavailable, ModelInfo, OllamaClient
from ..memory.store import Store
from ..models.profiles import PROFILES
from ..rag.service import KnowledgeBase
from . import governance
from .graph import GraphDeps, UnifiedRequest, build_graph


class ModelCatalog:
    """Short-lived cache of installed models so each turn does not re-query Ollama."""

    def __init__(self, llm: OllamaClient, ttl: float = 15.0):
        self.llm = llm
        self.ttl = ttl
        self._at = 0.0
        self._models: list[ModelInfo] = []

    async def installed(self, refresh: bool = False) -> list[ModelInfo]:
        if refresh or time.monotonic() - self._at > self.ttl:
            self._models = await self.llm.list_models()
            self._at = time.monotonic()
        return self._models

    def invalidate(self) -> None:
        self._at = 0.0


class Engine:
    def __init__(self, store: Store, llm: OllamaClient, kb: KnowledgeBase | None, metrics: M.Metrics, catalog: ModelCatalog):
        self.store = store
        self.llm = llm
        self.kb = kb
        self.metrics = metrics
        self.catalog = catalog
        self._cancel: dict[str, asyncio.Event] = {}

    def cancel(self, request_id: str) -> bool:
        ev = self._cancel.get(request_id)
        if ev:
            ev.set()
        return ev is not None

    def _options(self, settings: dict[str, Any]) -> dict[str, Any]:
        prof = PROFILES.get(settings.get("profile") or "balanced", PROFILES["balanced"])
        return {"num_ctx": prof["num_ctx"], "temperature": 0.3}

    async def run(self, req: UnifiedRequest, request_id: str) -> AsyncIterator[dict[str, Any]]:
        cancel = self._cancel.setdefault(request_id, asyncio.Event())
        settings = self.store.get_settings()
        t_start = time.perf_counter()
        answer_parts: list[str] = []
        state: dict[str, Any] = {}
        stats: GenerationStats | None = None
        saved = False
        try:
            if not self.store.get_session(req.session_id):
                yield {"type": "error", "code": "no_session", "message": "Session not found."}
                return
            history = self.store.recent_history(req.session_id, int(settings.get("context_turns", 8)))
            user_msg = self.store.add_message(
                req.session_id,
                "user",
                req.text,
                intent=req.intent,
                meta={"source": req.source, "screen_action": req.screen_action, "has_image": bool(req.image_b64)},
            )
            yield {"type": "accepted", "request_id": request_id, "user_message_id": user_msg.id}
            try:
                installed = await self.catalog.installed()
            except LLMUnavailable as e:
                yield {"type": "error", "code": "llm_unavailable", "message": str(e)}
                return
            prof = settings.get("profile") or "balanced"
            deps = GraphDeps(
                kb=self.kb,
                settings=settings,
                installed=installed,
                history=history,
                max_image_side=1024 if prof == "lite" else 1280,
            )
            try:
                state = await build_graph(deps).ainvoke({"request": req.model_dump()})
            except LLMUnavailable as e:
                yield {"type": "error", "code": "llm_unavailable", "message": str(e)}
                return
            except ValueError as e:  # bad image and similar input errors
                yield {"type": "error", "code": "bad_input", "message": str(e)}
                return
            if req.continuous and state.get("sensitive") and settings.get("pause_on_sensitive", True):
                yield {"type": "paused_sensitive", "message": "Sensitive content detected on screen; continuous analysis paused."}
                return
            timings = state.get("timings", {})
            if "retrieval_ms" in timings:
                self.metrics.record(M.RETRIEVAL, timings["retrieval_ms"])
                if state.get("evidence"):
                    self.metrics.record(M.RETRIEVAL_TOP_SCORE, state["evidence"][0]["score"], unit="cosine")
            if "ocr_ms" in timings:
                self.metrics.record(M.OCR, timings["ocr_ms"])
            evidence = state.get("evidence", [])
            citations = [{k: v for k, v in e.items() if k != "text"} for e in evidence]
            yield {
                "type": "meta",
                "agent": state["agent"],
                "style": state["style"],
                "model": state["model"],
                "vision": bool(state.get("image_b64")),
                "citations": citations,
                "notes": state.get("notes", []),
                "redaction": state.get("redaction"),
                "timings": timings,
            }
            stats = GenerationStats(model=state["model"])
            stream = self.llm.chat_stream(state["model"], state["messages"], options=self._options(settings), stats=stats)
            try:
                async for delta in stream:
                    if cancel.is_set():
                        stats.cancelled = True
                        break
                    answer_parts.append(delta)
                    yield {"type": "token", "t": delta}
            except LLMUnavailable as e:
                yield {"type": "error", "code": "llm_unavailable", "message": str(e)}
                if not answer_parts:
                    return
            finally:
                await stream.aclose()
            answer = "".join(answer_parts)
            gov = governance.review(
                answer,
                evidence=evidence,
                knowledge_requested=bool(req.collection_ids),
                interview_mode=req.mode == "interview",
                resume_evidence=bool(state.get("resume_text")),
                notes=state.get("notes", []),
            )
            total_ms = (time.perf_counter() - t_start) * 1000
            meta = {"model": stats.model}
            if stats.first_token_ms is not None:
                self.metrics.record(M.FIRST_TOKEN, stats.first_token_ms, meta=meta)
            self.metrics.record(M.TOTAL_RESPONSE, total_ms, meta=meta)
            if stats.tokens_per_second:
                self.metrics.record(M.TOKENS_PER_SEC, stats.tokens_per_second, unit="tok/s", meta=meta)
            if req.image_b64:
                self.metrics.record(M.SCREEN_ANALYSIS, total_ms, meta=meta)
            msg = self.store.add_message(
                req.session_id,
                "assistant",
                answer or "_(no answer generated)_",
                intent=req.intent,
                answer_style=state["style"],
                model=stats.model,
                citations=citations,
                meta={
                    "agent": state["agent"],
                    "governance": gov,
                    "stats": stats.to_dict(),
                    "total_ms": total_ms,
                    "notes": state.get("notes", []),
                    "cancelled": stats.cancelled,
                },
            )
            saved = True
            yield {
                "type": "done",
                "message_id": msg.id,
                "stats": stats.to_dict(),
                "total_ms": total_ms,
                "governance": gov,
                "cancelled": stats.cancelled,
            }
        finally:
            # Client disconnected mid-stream: keep what was generated, marked as cancelled.
            if not saved and answer_parts and state.get("model"):
                self.store.add_message(
                    req.session_id,
                    "assistant",
                    "".join(answer_parts),
                    intent=req.intent,
                    answer_style=state.get("style"),
                    model=state.get("model"),
                    meta={"agent": state.get("agent"), "cancelled": True},
                )
            self._cancel.pop(request_id, None)
