"""Lightweight request tracing (no paid service required).

Each request produces a :class:`RequestTrace` that is kept in an in-memory
ring buffer (for ``GET /metrics``) and appended to a local JSONL file.

LangSmith: LangGraph/LangChain emit LangSmith traces automatically when
``LANGSMITH_TRACING=true`` and ``LANGSMITH_API_KEY`` are set. The service
passes ``run_name``, ``tags`` and ``metadata`` (including ``request_id``) in
the graph config so both trace systems can be correlated.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCallTrace(BaseModel):
    tool_name: str
    success: bool
    duration_ms: float
    error: str | None = None


class RequestTrace(BaseModel):
    request_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mode: str
    question_preview: str
    intent: str | None = None
    agents_invoked: list[str] = Field(default_factory=list)
    execution_path: list[str] = Field(default_factory=list)
    node_latency_ms: dict[str, float] = Field(default_factory=dict)
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    retrieval_count: int = 0
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    tokens_estimated: bool = False
    confidence: float | None = None
    errors: list[str] = Field(default_factory=list)
    status: str = "ok"


def langsmith_enabled() -> bool:
    flag = os.getenv("LANGSMITH_TRACING", os.getenv("LANGCHAIN_TRACING_V2", "")).lower()
    return flag in {"1", "true", "yes"} and bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))


class TraceStore:
    """Thread-safe trace sink with aggregate metrics."""

    def __init__(self, trace_dir: Path | None, buffer_size: int = 500) -> None:
        self._traces: deque[RequestTrace] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._file: Path | None = None
        if trace_dir is not None:
            trace_dir.mkdir(parents=True, exist_ok=True)
            self._file = trace_dir / "traces.jsonl"

    def record(self, trace: RequestTrace) -> None:
        with self._lock:
            self._traces.append(trace)
            if self._file is not None:
                try:
                    with self._file.open("a", encoding="utf-8") as fh:
                        fh.write(trace.model_dump_json() + "\n")
                except OSError:
                    logger.exception("Could not write trace file %s", self._file)
        logger.info(
            "trace request_id=%s intent=%s path=%s latency_ms=%.0f tools=%d chunks=%d errors=%d",
            trace.request_id,
            trace.intent,
            "→".join(trace.execution_path),
            trace.latency_ms,
            len(trace.tool_calls),
            trace.retrieval_count,
            len(trace.errors),
        )

    def recent(self, limit: int = 20) -> list[RequestTrace]:
        with self._lock:
            return list(self._traces)[-limit:][::-1]

    def summary(self, recent_limit: int = 10) -> dict[str, Any]:
        with self._lock:
            traces = list(self._traces)
        latencies = sorted(t.latency_ms for t in traces)
        p95 = latencies[min(len(latencies) - 1, int(round(0.95 * (len(latencies) - 1))))] if latencies else 0.0
        confidences = [t.confidence for t in traces if t.confidence is not None]
        return {
            "total_requests": len(traces),
            "successful_requests": sum(1 for t in traces if t.status == "ok"),
            "failed_requests": sum(1 for t in traces if t.status != "ok"),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "p95_latency_ms": round(p95, 1),
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            "total_tokens": sum(t.input_tokens + t.output_tokens for t in traces),
            "llm_calls": sum(t.llm_calls for t in traces),
            "intent_counts": dict(Counter(t.intent or "unknown" for t in traces)),
            "tool_usage": dict(Counter(c.tool_name for t in traces for c in t.tool_calls)),
            "agent_usage": dict(Counter(a for t in traces for a in t.agents_invoked)),
            "recent_traces": [t.model_dump() for t in traces[-recent_limit:][::-1]],
        }
