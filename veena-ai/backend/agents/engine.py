"""Runs one conversational turn: orchestrate -> stream -> govern -> persist -> measure."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from ..analytics import metrics as M
from ..llm.ollama import GenerationStats, LLMUnavailable, ModelInfo, OllamaClient
from ..memory.store import Store
from ..models.profiles import PROFILES
from ..rag.service import KnowledgeBase
from . import governance, spine
from .graph import MAX_ANSWER_TOKENS, GraphDeps, UnifiedRequest, build_graph

log = logging.getLogger("veena.engine")


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
        return {"num_ctx": prof["num_ctx"], "temperature": 0.3, "num_predict": MAX_ANSWER_TOKENS}

    def _measure(
        self,
        req: UnifiedRequest,
        state: dict[str, Any],
        history: list[dict[str, str]],
        answer: str,
        gov: dict | None,
        *,
        cancelled: bool,
        failed: bool = False,
        extra_steps: list[dict[str, Any]] | None = None,
        total_ms: float | None = None,
        message_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Scores the turn along the semantic spine and stores it as an agent trace.
        Measurement must never break a conversation, so failures are swallowed."""
        try:
            steps = [*state.get("trace", []), *(extra_steps or [])]
            path = [t["node"] for t in steps]
            outcome = spine.classify_outcome(gov, cancelled, failed)
            evidence = state.get("evidence", [])
            measures = spine.measure_turn(
                question=req.text,
                answer=answer,
                context_blocks={
                    "question": req.text,
                    # Only the user's own words: the model's past answers are not evidence,
                    # or an earlier invention would count as backed later.
                    "history": "\n".join(h.get("content", "") for h in history if h.get("role") == "user"),
                    "transcript": "\n".join(req.transcript_context),
                    "screen": state.get("ocr_text", ""),
                    "documents": "\n\n".join(e.get("text", "") for e in evidence),
                    "resume": state.get("resume_text", ""),
                    "job": req.job_description or "",
                },
                evidence=evidence,
                cited=(gov or {}).get("cited", []),
                path=path,
                has_image=bool(req.image_b64),
                needs_retrieval=bool(req.collection_ids or req.resume_collection_id),
                outcome=outcome,
            )
            flag = spine.unbacked_flag(measures["knowledge"], measures["context"]["sources"])
            if flag and gov is not None:
                gov["flags"].append(flag)
                outcome = spine.classify_outcome(gov, cancelled, failed)
                measures["procedure"]["outcome"] = outcome
            measures["procedure"]["step_ms"] = {t["node"]: t["ms"] for t in steps}
            self.store.add_trace(
                session_id=req.session_id,
                message_id=message_id,
                agent=state.get("agent", "unknown"),
                mode=req.mode,
                outcome=outcome,
                adherent=measures["procedure"]["adherent"],
                support_rate=measures["knowledge"]["support_rate"],
                utilization=measures["context"]["utilization"],
                citation_rate=measures["context"]["citation_rate"],
                total_ms=total_ms,
                path_json=json.dumps(path),
                measures_json=json.dumps(measures),
            )
            return measures
        except Exception:  # noqa: BLE001
            log.exception("agent measurement failed")
            return None

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
            t_gen = time.perf_counter()
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
                    gen_ms = round((time.perf_counter() - t_gen) * 1000, 2)
                    self._measure(
                        req, state, history, "", None, cancelled=False, failed=True, extra_steps=[{"node": "generate", "ms": gen_ms}]
                    )
                    return
            finally:
                await stream.aclose()
            gen_step = {"node": "generate", "ms": round((time.perf_counter() - t_gen) * 1000, 2)}
            answer = "".join(answer_parts)
            t_gov = time.perf_counter()
            gov = governance.review(
                answer,
                evidence=evidence,
                knowledge_requested=bool(req.collection_ids),
                interview_mode=req.mode == "interview",
                resume_evidence=bool(state.get("resume_text")),
                notes=state.get("notes", []),
            )
            gov_ms = round((time.perf_counter() - t_gov) * 1000, 2)
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
            steps = [gen_step] if stats.cancelled else [gen_step, {"node": "govern", "ms": gov_ms}]
            measures = self._measure(
                req, state, history, answer, gov, cancelled=stats.cancelled, extra_steps=steps, total_ms=total_ms, message_id=msg.id
            )
            spine_summary = _spine_summary(measures)
            if spine_summary:
                self.store.merge_message_meta(msg.id, {"spine": spine_summary, "governance": gov})
            yield {
                "type": "done",
                "spine": spine_summary,
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


def _spine_summary(m: dict[str, Any] | None) -> dict[str, Any] | None:
    """The per-answer slice of the spine the UI shows next to an answer."""
    if not m:
        return None
    k, c, p = m["knowledge"], m["context"], m["procedure"]
    return {
        "outcome": p["outcome"],
        "adherent": p["adherent"],
        "path": p["path"],
        "support_rate": k["support_rate"],
        "grounded_context": k["grounded_context"],
        "claims": k["claims"],
        "unsupported": k["unsupported"],
        "utilization": c["utilization"],
        "citation_rate": c["citation_rate"],
        "context_nodes": c["nodes"],
    }
