"""Request tracing and metrics.

Every request gets a ``trace_id``. Each stage (auth, routing, retrieval,
rerank, LLM, guardrails, tools) records a span, so a slow or wrong answer can
be reconstructed stage by stage instead of guessed at. In production these
spans are exported via OpenTelemetry; here they are kept in memory so the
platform runs with zero infrastructure.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class Span:
    name: str
    start: float
    end: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def duration_ms(self) -> float:
        return round(((self.end or time.perf_counter()) - self.start) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "duration_ms": self.duration_ms, "attributes": self.attributes, "error": self.error}


@dataclass
class Trace:
    trace_id: str
    principal: str | None = None
    route: str | None = None
    started: float = field(default_factory=time.perf_counter)
    spans: list[Span] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "principal": self.principal,
            "route": self.route,
            "total_ms": round((time.perf_counter() - self.started) * 1000, 2),
            "tokens": {"input": self.tokens_in, "output": self.tokens_out},
            "cost_usd": round(self.cost_usd, 6),
            "spans": [s.to_dict() for s in self.spans],
        }


_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("trace", default=None)


class TraceStore:
    """Bounded in-memory store of recent traces (OTel exporter in production)."""

    def __init__(self, capacity: int = 2000) -> None:
        self._traces: OrderedDict[str, Trace] = OrderedDict()
        self._capacity = capacity

    def put(self, trace: Trace) -> None:
        self._traces[trace.trace_id] = trace
        self._traces.move_to_end(trace.trace_id)
        while len(self._traces) > self._capacity:
            self._traces.popitem(last=False)

    def get(self, trace_id: str) -> Trace | None:
        return self._traces.get(trace_id)


class Metrics:
    """Counters and latency samples; exposes P50/P95/P99 per metric."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.latencies: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, by: int = 1) -> None:
        self.counters[name] += by

    def observe(self, name: str, value_ms: float) -> None:
        samples = self.latencies[name]
        samples.append(value_ms)
        if len(samples) > 5000:
            del samples[: len(samples) - 5000]

    @staticmethod
    def _pct(samples: list[float], p: float) -> float:
        if not samples:
            return 0.0
        ordered = sorted(samples)
        idx = min(len(ordered) - 1, max(0, int(round(p / 100 * (len(ordered) - 1)))))
        return round(ordered[idx], 2)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "latency_ms": {
                name: {"p50": self._pct(s, 50), "p95": self._pct(s, 95), "p99": self._pct(s, 99), "n": len(s)}
                for name, s in self.latencies.items()
            },
        }


trace_store = TraceStore()
metrics = Metrics()


def new_trace(principal: str | None = None, route: str | None = None, trace_id: str | None = None) -> Trace:
    trace = Trace(trace_id=trace_id or uuid.uuid4().hex[:16], principal=principal, route=route)
    _current.set(trace)
    trace_store.put(trace)
    return trace


def current_trace() -> Trace | None:
    return _current.get()


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    trace = _current.get()
    s = Span(name=name, start=time.perf_counter(), attributes=dict(attributes))
    if trace is not None:
        trace.spans.append(s)
    try:
        yield s
    except Exception as exc:  # recorded, then re-raised
        s.error = f"{type(exc).__name__}: {exc}"
        metrics.inc(f"span_error.{name}")
        raise
    finally:
        s.end = time.perf_counter()
        metrics.observe(f"span.{name}", s.duration_ms)


def record_usage(tokens_in: int, tokens_out: int, cost_usd: float) -> None:
    trace = _current.get()
    if trace is not None:
        trace.tokens_in += tokens_in
        trace.tokens_out += tokens_out
        trace.cost_usd += cost_usd
    metrics.inc("llm.tokens_in", tokens_in)
    metrics.inc("llm.tokens_out", tokens_out)
