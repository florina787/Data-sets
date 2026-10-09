"""Observability: structured logging with secret redaction, audit log, traces and metrics.

Logs and audit entries contain identifiers, counts, statuses and latencies only —
never claim payloads, PHI or secrets. Designed so OpenTelemetry/LangSmith exporters can
be attached later via :meth:`Tracer.add_exporter` (not required).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.security.sanitizer import redact_secrets


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(str(record.msg))
        if record.args:
            record.args = tuple(redact_secrets(str(a)) for a in record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                   "logger": record.name, "msg": record.getMessage()}
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return redact_secrets(json.dumps(payload, default=str))


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("claimforge")
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


log = configure_logging()


def _safe(detail: dict | None) -> dict:
    """Keep only scalar/short values; redact secrets."""
    out: dict[str, Any] = {}
    for k, v in (detail or {}).items():
        if isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, str):
            out[k] = redact_secrets(v[:200])
        elif isinstance(v, (list, tuple)):
            out[k] = [redact_secrets(str(x))[:80] for x in list(v)[:10]]
        else:
            out[k] = type(v).__name__
    return out


class AuditLog:
    def __init__(self, maxlen: int = 5_000) -> None:
        self._entries: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, actor: str, action: str, request_id: str | None = None, **detail) -> dict:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "request_id": request_id, "actor": actor,
                 "action": action, "detail": _safe(detail)}
        with self._lock:
            self._entries.append(entry)
        log.debug(f"audit {actor} {action}", extra={"structured": {"request_id": request_id, "actor": actor,
                                                                    "action": action}})
        return entry

    def entries(self, limit: int = 200) -> list[dict]:
        with self._lock:
            return list(self._entries)[-limit:]


@dataclass
class TraceEvent:
    node: str
    kind: str
    started_at: float
    latency_ms: float
    status: str
    detail: dict = field(default_factory=dict)


class Tracer:
    """Per-workflow trace collector (agent order, latency, tool calls, errors)."""

    def __init__(self) -> None:
        self._exporters: list[Callable[[dict], None]] = []

    def add_exporter(self, fn: Callable[[dict], None]) -> None:
        self._exporters.append(fn)

    def export(self, trace: dict) -> None:
        for fn in self._exporters:
            try:
                fn(trace)
            except Exception:  # exporters must never break workflows
                log.warning("trace exporter failed")


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.latencies: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self.started = time.time()

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + n

    def observe(self, name: str, ms: float) -> None:
        with self._lock:
            self.latencies.setdefault(name, []).append(ms)
            if len(self.latencies[name]) > 1000:
                self.latencies[name] = self.latencies[name][-1000:]

    def snapshot(self) -> dict:
        with self._lock:
            lat = {k: {"count": len(v), "avg_ms": round(sum(v) / len(v), 1), "max_ms": round(max(v), 1)}
                   for k, v in self.latencies.items() if v}
            return {"uptime_s": round(time.time() - self.started, 1), "counters": dict(self.counters),
                    "latency": lat}


def new_request_id() -> str:
    return "REQ-" + uuid.uuid4().hex[:12].upper()
