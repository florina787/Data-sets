"""Rate limiting, retry with backoff + jitter, Retry-After parsing and a circuit breaker."""

from __future__ import annotations

import random
import re
import threading
import time
from collections import deque


class RateLimiter:
    """Sliding-window requests-per-minute limiter plus a concurrency cap (thread-safe)."""

    def __init__(self, rpm: int, max_concurrency: int, clock=time.monotonic, sleep=time.sleep):
        self.rpm = max(1, rpm)
        self._times: deque[float] = deque()
        self._lock = threading.Lock()
        self._sem = threading.BoundedSemaphore(max(1, max_concurrency))
        self._clock = clock
        self._sleep = sleep
        self.waits = 0

    def acquire(self, timeout: float = 60.0) -> None:
        deadline = self._clock() + timeout
        if not self._sem.acquire(timeout=timeout):
            raise TimeoutError("Timed out waiting for an LLM concurrency slot")
        while True:
            with self._lock:
                now = self._clock()
                while self._times and now - self._times[0] >= 60.0:
                    self._times.popleft()
                if len(self._times) < self.rpm:
                    self._times.append(now)
                    return
                wait = 60.0 - (now - self._times[0])
            if self._clock() + wait > deadline:
                self._sem.release()
                raise TimeoutError("Rate limit window would exceed the request budget")
            self.waits += 1
            self._sleep(min(wait, 1.0))

    def release(self) -> None:
        self._sem.release()


def backoff_delay(attempt: int, base: float = 1.0, cap: float = 20.0, rng: random.Random | None = None) -> float:
    """Full-jitter exponential backoff: uniform(0, min(cap, base * 2**attempt))."""
    r = rng or random
    return r.uniform(0, min(cap, base * (2 ** attempt)))


_RETRY_DELAY = re.compile(r"retry(?:Delay|-after|_after)?\W+(\d+(?:\.\d+)?)s?", re.I)


def retry_after_seconds(error: Exception) -> float | None:
    """Extract a server-suggested delay from a Gemini 429 (RetryInfo.retryDelay) or a Retry-After header."""
    resp = getattr(error, "response", None)
    headers = getattr(resp, "headers", None) or {}
    try:
        if "retry-after" in headers:
            return float(headers["retry-after"])
    except (TypeError, ValueError):
        pass
    details = getattr(error, "details", None) or {}
    text = str(details) + " " + str(error)
    m = _RETRY_DELAY.search(text)
    return float(m.group(1)) if m else None


RETRYABLE_CODES = {408, 429, 500, 502, 503, 504}


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; half-opens after `cooldown` seconds."""

    def __init__(self, threshold: int, cooldown: float, clock=time.monotonic):
        self.threshold = threshold
        self.cooldown = cooldown
        self._clock = clock
        self.failures = 0
        self.opened_at: float | None = None
        self.last_error: str | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self._clock() - self.opened_at >= self.cooldown:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        return self.state != "open"

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None
            self.last_error = None

    def failure(self, error: str, permanent: bool = False) -> None:
        with self._lock:
            self.failures += 1
            self.last_error = error
            if permanent or self.failures >= self.threshold:
                self.opened_at = self._clock()
