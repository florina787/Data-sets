"""Lightweight, dependency-free tracing and metrics.

Captures request ID, timestamp, workflow path, agents invoked, per-node
latency, model/tool calls, errors and the decision. Exporters are pluggable so
LangSmith or OpenTelemetry can be attached later without code changes to the
workflow (see ``register_exporter``). No paid observability platform is needed.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import Counter, deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from app.config.logging_config import get_logger
from app.models.outputs import TraceSpan, TraceSummary

logger = get_logger("observability")


class Tracer:
    """Per-request trace recorder."""

    def __init__(self, mode: str) -> None:
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.mode = mode
        self.spans: list[TraceSpan] = []
        self.workflow_path: list[str] = []
        self.agents: list[str] = []
        self.model_calls = 0
        self.paid_model_calls = 0
        self.tool_calls = 0
        self.errors: list[str] = []
        self._start = time.perf_counter()

    @contextmanager
    def span(self, node: str, agent: str | None = None) -> Iterator[None]:
        start = time.perf_counter()
        self.workflow_path.append(node)
        if agent and agent not in self.agents:
            self.agents.append(agent)
        status, detail = "ok", ""
        try:
            yield
        except Exception as exc:
            status, detail = "error", f"{type(exc).__name__}: {exc}"
            self.errors.append(f"{node}: {detail}")
            raise
        finally:
            self.spans.append(TraceSpan(node=node, duration_ms=round((time.perf_counter() - start) * 1000, 3), status=status, detail=detail))

    def record_model_call(self, *, paid: bool) -> None:
        self.model_calls += 1
        if paid:
            self.paid_model_calls += 1
            METRICS.increment("paid_llm_calls_total")
        METRICS.increment("llm_calls_total")

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def summary(self) -> TraceSummary:
        return TraceSummary(
            request_id=self.request_id,
            timestamp=self.timestamp,
            mode=self.mode,
            workflow_path=list(self.workflow_path),
            agents_invoked=list(self.agents),
            spans=list(self.spans),
            model_calls=self.model_calls,
            paid_model_calls=self.paid_model_calls,
            tool_calls=self.tool_calls,
            total_latency_ms=round((time.perf_counter() - self._start) * 1000, 3),
            errors=list(self.errors),
        )


class MetricsRegistry:
    """Thread-safe in-process counters and recent decision log."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self._latencies: deque[float] = deque(maxlen=500)
        self._recent: deque[dict[str, Any]] = deque(maxlen=50)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def get(self, name: str) -> int:
        with self._lock:
            return self._counters[name]

    def record_assessment(self, trace: TraceSummary, decision: dict[str, Any]) -> None:
        with self._lock:
            self._counters["assessments_total"] += 1
            self._counters[f"architecture:{decision.get('primary_architecture')}"] += 1
            self._counters[f"agentic:{decision.get('agentic_verdict')}"] += 1
            self._latencies.append(trace.total_latency_ms)
            self._recent.append({"request_id": trace.request_id, "timestamp": trace.timestamp, "latency_ms": trace.total_latency_ms, **decision})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            lat = list(self._latencies)
            return {
                "counters": dict(self._counters),
                "assessment_latency_ms": {
                    "count": len(lat),
                    "avg": round(sum(lat) / len(lat), 3) if lat else 0.0,
                    "max": round(max(lat), 3) if lat else 0.0,
                },
                "recent_decisions": list(self._recent)[-10:],
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._latencies.clear()
            self._recent.clear()


METRICS = MetricsRegistry()

Exporter = Callable[[TraceSummary, dict[str, Any]], None]
_exporters: list[Exporter] = []


def register_exporter(exporter: Exporter) -> None:
    """Attach an exporter (e.g. an OpenTelemetry or LangSmith bridge)."""
    _exporters.append(exporter)


def export(trace: TraceSummary, decision: dict[str, Any]) -> None:
    logger.info(
        "assessment_trace",
        extra={"extra_fields": {"request_id": trace.request_id, "latency_ms": trace.total_latency_ms, "path": trace.workflow_path, "paid_model_calls": trace.paid_model_calls, **decision}},
    )
    for exporter in _exporters:
        try:
            exporter(trace, decision)
        except Exception:  # noqa: BLE001 - exporters must never break assessments
            logger.exception("exporter_failed")
