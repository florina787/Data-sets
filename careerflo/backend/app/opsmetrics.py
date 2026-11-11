"""In-process request metrics for the operations dashboard.

Measured values only: request counts, status classes, latency percentiles and active sessions since the
process started. They reset on restart (a Space restart, a deploy) — the dashboard says so. For multi-replica
deployments export these to Prometheus/OpenTelemetry instead.
"""
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from typing import Any


class RequestMetrics:
    def __init__(self, window: int = 5000) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self.total = 0
        self.by_class: Counter[str] = Counter()
        self.by_route_errors: Counter[str] = Counter()
        self.latency_ms: deque[float] = deque(maxlen=window)
        self.last_seen: dict[str, float] = {}

    def record(self, path: str, status: int, ms: float, user_id: str | None) -> None:
        cls = f"{status // 100}xx"
        with self._lock:
            self.total += 1
            self.by_class[cls] += 1
            self.latency_ms.append(ms)
            if status >= 500:
                self.by_route_errors[path] += 1
            if user_id:
                self.last_seen[user_id] = time.time()

    @staticmethod
    def _pct(values: list[float], p: float) -> float | None:
        if not values:
            return None
        s = sorted(values)
        return round(s[min(len(s) - 1, int(p * (len(s) - 1)))], 1)

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            lat = list(self.latency_ms)
            active15 = sum(1 for t in self.last_seen.values() if now - t <= 900)
            active24 = sum(1 for t in self.last_seen.values() if now - t <= 86400)
            total = self.total
            classes = dict(self.by_class)
            errs = self.by_route_errors.most_common(8)
        server_errors = classes.get("5xx", 0)
        return {"since_seconds": int(now - self.started), "requests": total, "by_status_class": classes,
                "success_rate": round(1 - server_errors / total, 4) if total else None,
                "client_error_rate": round(classes.get("4xx", 0) / total, 4) if total else None,
                "latency_ms": {"p50": self._pct(lat, .5), "p95": self._pct(lat, .95), "p99": self._pct(lat, .99)},
                "active_users_15m": active15, "active_users_24h": active24, "top_5xx_routes": errs}

    def reset(self) -> None:
        self.__init__(self.latency_ms.maxlen or 5000)


metrics = RequestMetrics()


def route_key(path: str) -> str:
    """Collapse ids so metrics group by route, never by user-specific values."""
    import re

    return re.sub(r"/[0-9a-f]{8}-[0-9a-f-]{27,}", "/{id}", path)
