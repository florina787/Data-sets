"""Circuit breakers, retry with exponential backoff, token-bucket rate limiting and a TTL idempotency cache."""
from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from harness.errors import CircuitOpen, HarnessError

T = TypeVar("T")


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    reset_after_s: float = 30.0
    state: str = "closed"
    failures: int = 0
    opened_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def before(self) -> None:
        with self.lock:
            if self.state == "open":
                if time.monotonic() - self.opened_at >= self.reset_after_s:
                    self.state = "half_open"
                else:
                    raise CircuitOpen(f"circuit '{self.name}' is open; failing fast")

    def success(self) -> None:
        with self.lock:
            self.state, self.failures = "closed", 0

    def failure(self) -> None:
        with self.lock:
            self.failures += 1
            if self.state == "half_open" or self.failures >= self.failure_threshold:
                self.state, self.opened_at = "open", time.monotonic()

    def snapshot(self) -> dict:
        return {"name": self.name, "state": self.state, "failures": self.failures}


_breakers: dict[str, CircuitBreaker] = {}
_blk = threading.Lock()


def breaker(name: str) -> CircuitBreaker:
    with _blk:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name)
        return _breakers[name]


def all_breakers() -> list[dict]:
    return [b.snapshot() for b in _breakers.values()]


def reset_breakers() -> None:
    with _blk:
        _breakers.clear()


def retry(fn: Callable[[], T], max_retries: int, base_delay: float = 0.05, max_delay: float = 1.0,
          on_retry: Callable[[int, BaseException], None] | None = None) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except HarnessError as e:
            if not e.retryable or attempt >= max_retries:
                raise
            attempt += 1
            if on_retry:
                on_retry(attempt, e)
            time.sleep(min(max_delay, base_delay * 2 ** (attempt - 1)) * (0.5 + random.random() / 2))


class RateLimiter:
    """Token bucket per key."""

    def __init__(self, rate_per_min: int):
        self.rate = rate_per_min / 60.0
        self.cap = float(rate_per_min)
        self.buckets: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self.lock:
            tokens, ts = self.buckets.get(key, (self.cap, time.monotonic()))
            now = time.monotonic()
            tokens = min(self.cap, tokens + (now - ts) * self.rate)
            if tokens < 1:
                self.buckets[key] = (tokens, now)
                return False
            self.buckets[key] = (tokens - 1, now)
            return True


class TTLCache:
    def __init__(self, ttl_s: float = 300, max_items: int = 2000):
        self.ttl, self.max = ttl_s, max_items
        self.d: dict[str, tuple[float, Any]] = {}
        self.lock = threading.Lock()
        self.hits = self.misses = 0

    def get(self, key: str) -> Any | None:
        with self.lock:
            v = self.d.get(key)
            if v and time.monotonic() - v[0] < self.ttl:
                self.hits += 1
                return v[1]
            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        with self.lock:
            if len(self.d) >= self.max:
                self.d.pop(next(iter(self.d)))
            self.d[key] = (time.monotonic(), value)

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses, "hit_rate": round(self.hits / total, 4) if total else 0.0, "size": len(self.d)}
