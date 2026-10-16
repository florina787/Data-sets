"""Metrics: Prometheus exposition + an in-process rolling store for dashboards.

Every recorded sample carries a ``synthetic`` flag so dashboards can separate
real measurements of this process from simulation-generated telemetry.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from statistics import mean

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter("medaccess_http_requests_total", "HTTP requests", ["route", "method", "status"],
                        registry=REGISTRY)
HTTP_LATENCY = Histogram("medaccess_http_request_seconds", "HTTP latency", ["route"], registry=REGISTRY)
AGENT_RUNS = Counter("medaccess_agent_executions_total", "Agent executions", ["agent", "status"], registry=REGISTRY)
AGENT_LATENCY = Histogram("medaccess_agent_seconds", "Agent latency", ["agent"], registry=REGISTRY)
TOOL_CALLS = Counter("medaccess_tool_calls_total", "Tool calls", ["tool", "status"], registry=REGISTRY)
RETRIES = Counter("medaccess_retries_total", "Retries", ["component"], registry=REGISTRY)
WORKFLOWS = Counter("medaccess_workflows_total", "Workflows by terminal status", ["type", "status"],
                    registry=REGISTRY)
LLM_TOKENS = Counter("medaccess_llm_tokens_total", "LLM tokens", ["model", "kind"], registry=REGISTRY)
BUSINESS = Counter("medaccess_business_events_total", "Business events", ["event"], registry=REGISTRY)
ACTIVE_SEARCHES = Gauge("medaccess_active_searches", "Searches in progress", registry=REGISTRY)
DATA_AGE = Gauge("medaccess_availability_data_age_hours", "Median age of availability records", registry=REGISTRY)


class RollingStore:
    """Bounded time-series store: name -> deque[(ts, value, labels, synthetic)]."""

    def __init__(self, maxlen: int = 5000) -> None:
        self._data: dict[str, deque] = defaultdict(lambda: deque(maxlen=maxlen))
        self._lock = threading.Lock()

    def add(self, name: str, value: float, labels: dict | None = None, synthetic: bool = False,
            ts: float | None = None) -> None:
        with self._lock:
            self._data[name].append((ts or time.time(), float(value), labels or {}, synthetic))

    def series(self, name: str, since: float | None = None, synthetic: bool | None = None) -> list[tuple]:
        with self._lock:
            rows = list(self._data.get(name, ()))
        return [r for r in rows if (since is None or r[0] >= since) and (synthetic is None or r[3] == synthetic)]

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._data)

    def summary(self, name: str, since: float | None = None, synthetic: bool | None = None) -> dict:
        vals = [r[1] for r in self.series(name, since, synthetic)]
        if not vals:
            return {"count": 0}
        vs = sorted(vals)
        return {"count": len(vs), "mean": round(mean(vs), 4), "min": vs[0], "max": vs[-1],
                "p95": vs[min(len(vs) - 1, int(0.95 * (len(vs) - 1) + 0.5))], "sum": round(sum(vs), 4)}

    def clear(self, synthetic_only: bool = False) -> None:
        with self._lock:
            if not synthetic_only:
                self._data.clear()
                return
            for k in list(self._data):
                self._data[k] = deque((r for r in self._data[k] if not r[3]), maxlen=self._data[k].maxlen)


STORE = RollingStore()


def prometheus_text() -> bytes:
    return generate_latest(REGISTRY)


def infrastructure_snapshot() -> dict:
    """Real process/host measurements using only the standard library (Linux /proc when available)."""
    snap: dict = {"measured": True, "pid": os.getpid()}
    try:
        load1, load5, _ = os.getloadavg()
        snap["load_avg_1m"], snap["load_avg_5m"], snap["cpu_count"] = round(load1, 2), round(load5, 2), os.cpu_count()
    except OSError:
        pass
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    snap["process_rss_mb"] = round(int(line.split()[1]) / 1024, 1)
        with open("/proc/meminfo") as fh:
            info = {ln.split(":")[0]: int(ln.split()[1]) for ln in fh if ln.split()}
            snap["host_mem_total_mb"] = round(info["MemTotal"] / 1024)
            snap["host_mem_available_mb"] = round(info["MemAvailable"] / 1024)
    except (OSError, KeyError, ValueError, IndexError):
        pass
    try:
        st = os.statvfs("/")
        snap["disk_free_gb"] = round(st.f_bavail * st.f_frsize / 1e9, 2)
        snap["disk_total_gb"] = round(st.f_blocks * st.f_frsize / 1e9, 2)
    except OSError:
        pass
    return snap
