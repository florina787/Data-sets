"""OpenTelemetry tracing, structured JSON logging, live request metrics and budget alerts.

Live metrics (request latency, failures, CPU, memory) are *measured* by this process and kept separate from the
synthetic daily history used to demonstrate 12-month trends.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import subprocess
import threading
import time
from collections import deque

import psutil
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as M
from app.finance import engine as E


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {"ts": dt.datetime.fromtimestamp(record.created, dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z", "level": record.levelname,
             "logger": record.name, "msg": record.getMessage()}
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            d["trace_id"] = f"{span.trace_id:032x}"
            d["span_id"] = f"{span.span_id:016x}"
        for k in ("actor", "role", "action", "entity", "entity_id", "route", "status", "duration_ms"):
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d, default=str)


def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root.handlers = [h]
    root.setLevel(level)


class _Store:
    def __init__(self, maxlen: int = 5000):
        self.lock = threading.Lock()
        self.requests: deque = deque(maxlen=maxlen)
        self.spans: deque = deque(maxlen=500)
        self.started = time.time()

    def add_request(self, route: str, method: str, status: int, ms: float):
        with self.lock:
            self.requests.append((time.time(), route, method, status, ms))

    def add_span(self, s: dict):
        with self.lock:
            self.spans.append(s)


STORE = _Store()


class MemoryExporter(SpanExporter):
    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        for s in spans:
            STORE.add_span({"name": s.name, "trace_id": f"{s.context.trace_id:032x}", "duration_ms": round((s.end_time - s.start_time) / 1e6, 2),
                            "status": s.status.status_code.name, "attributes": {k: v for k, v in (s.attributes or {}).items()}})
        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None


_provider: TracerProvider | None = None


def setup_tracing() -> trace.Tracer:
    global _provider
    if _provider is None:
        _provider = TracerProvider(resource=Resource.create({"service.name": "flobank-sherin-api", "service.version": "3.0.0"}))
        _provider.add_span_processor(SimpleSpanProcessor(MemoryExporter()))
        trace.set_tracer_provider(_provider)
    return trace.get_tracer("sherin")


def percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def _gpu() -> dict:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=2).stdout.strip().splitlines()
            u, mu, mt = [float(x) for x in out[0].split(",")]
            return {"available": True, "utilization_pct": u, "memory_used_mb": mu, "memory_total_mb": mt}
        except Exception as e:  # noqa: BLE001
            return {"available": False, "reason": f"nvidia-smi failed: {e}"}
    return {"available": False, "reason": "No NVIDIA GPU detected on this host (nvidia-smi not found)."}


def live_metrics() -> dict:
    with STORE.lock:
        reqs = list(STORE.requests)
        spans = list(STORE.spans)[-25:]
    api = [r for r in reqs if r[1].startswith("/api") and not r[1].startswith("/api/metrics/live")]
    lat = [r[4] for r in api]
    fails = sum(1 for r in api if r[3] >= 500)
    by_route: dict[str, list[float]] = {}
    for r in api:
        by_route.setdefault(f"{r[2]} {r[1]}", []).append(r[4])
    vm = psutil.virtual_memory()
    return {"data_class": "measured", "since": dt.datetime.fromtimestamp(STORE.started, dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z",
            "requests": len(api), "failed": fails, "client_errors": sum(1 for r in api if 400 <= r[3] < 500),
            "p50_ms": percentile(lat, 50), "p95_ms": percentile(lat, 95), "p99_ms": percentile(lat, 99),
            "routes": sorted([{"route": k, "count": len(v), "p95_ms": percentile(v, 95)} for k, v in by_route.items()], key=lambda r: -r["count"])[:12],
            "host": {"cpu_pct": psutil.cpu_percent(interval=None), "memory_pct": vm.percent, "memory_used_mb": round(vm.used / 1e6), "gpu": _gpu()},
            "recent_spans": spans}


def history(db: Session, p: E.Period, dc: str) -> dict:
    from sqlalchemy import case, func
    rows = db.scalars(select(M.SystemMetricDaily).where(M.SystemMetricDaily.date.between(p.start, p.end), M.SystemMetricDaily.data_class == dc)
                      .order_by(M.SystemMetricDaily.date)).all()
    t = M.AgentTask
    tk = db.execute(select(func.date(t.created_at), func.count(), func.sum(case((t.status == "succeeded", 1), else_=0)),
                           func.sum(case((t.status == "failed", 1), else_=0)), func.sum(t.tool_calls), func.sum(t.retries),
                           func.sum(case((t.rework_min > 0, 1), else_=0)), func.sum(case((t.quality_pass.is_(True), 1), else_=0)))
                    .where(E._between(t.created_at, p), t.data_class == dc).group_by(func.date(t.created_at))).all()
    tkd = {str(r[0]): r for r in tk}
    tu = M.TokenUsage
    inf = dict((str(d), (float(a or 0), int(i or 0), int(o or 0))) for d, a, i, o in db.execute(
        select(func.date(tu.ts), func.avg(tu.latency_ms), func.sum(tu.input_tokens), func.sum(tu.output_tokens))
        .where(E._between(tu.ts, p), tu.data_class == dc).group_by(func.date(tu.ts))).all())
    x = [r.date.isoformat() for r in rows]

    def g(i, d, default=0):
        r = tkd.get(d)
        return int(r[i] or 0) if r else default
    return {"data_class": dc, "x": x,
            "series": {"requests": [r.requests for r in rows], "p50_ms": [r.p50_ms for r in rows], "p95_ms": [r.p95_ms for r in rows],
                       "p99_ms": [r.p99_ms for r in rows], "cpu_pct": [float(r.cpu_pct) for r in rows], "mem_pct": [float(r.mem_pct) for r in rows],
                       "gpu_pct": [float(r.gpu_pct) for r in rows], "tasks": [g(1, d) for d in x], "succeeded": [g(2, d) for d in x],
                       "failed": [g(3, d) for d in x], "tool_calls": [g(4, d) for d in x], "retries": [g(5, d) for d in x],
                       "human_corrections": [g(6, d) for d in x], "quality_pass": [g(7, d) for d in x],
                       "inference_ms_avg": [round(inf.get(d, (0, 0, 0))[0]) for d in x], "input_tokens": [inf.get(d, (0, 0, 0))[1] for d in x],
                       "output_tokens": [inf.get(d, (0, 0, 0))[2] for d in x]}}


def alerts(db: Session, end_month: str, fx: E.Fx, dc: str, warn_pct: float = 80.0) -> list[dict]:
    out = []
    p = E.resolve_period("month", end_month)
    k = {c["key"]: c for c in E.kpis(db, p, fx, dc)["cards"]}
    ai = k["ai_cost"]
    if ai["budget_utilization_pct"] is not None:
        u = ai["budget_utilization_pct"]
        lvl = "breach" if u >= 100 else ("warning" if u >= warn_pct else "ok")
        out.append({"id": "ai_budget", "level": lvl, "title": "Sherin AI monthly budget", "detail": f"{u}% of budget used in {p.label}.",
                    "value": ai["value"], "threshold": ai["budget"]})
    b = E.data_bounds(db, dc)
    if b["ledger_end"]:
        end = dt.date.fromisoformat(b["ledger_end"])
        cur = E.Period(end, end, "custom", end.isoformat())
        base = E.Period(end - dt.timedelta(days=7), end - dt.timedelta(days=1), "custom", "prior 7 days")
        d = E.cost_drivers(db, cur, base, fx, dc)
        delta = d["total_per_day"]["delta_pct"]
        if delta is not None:
            out.append({"id": "daily_spike", "level": "warning" if delta >= 30 else "ok", "title": "Daily AI spend vs 7-day average",
                        "detail": f"{end.isoformat()}: {delta:+.1f}% vs trailing 7-day average.", "value": d["total_per_day"]["current"],
                        "threshold": d["total_per_day"]["baseline"]})
    return out
