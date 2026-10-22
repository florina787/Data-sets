"""Small, dependency-free resilience primitives used by the live LLM client."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a call is short-circuited because the breaker is open."""


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0

    def delays(self) -> list[float]:
        """Exponential backoff schedule between attempts (deterministic, no jitter)."""
        return [min(self.base_delay_seconds * 2**i, self.max_delay_seconds) for i in range(self.max_attempts - 1)]

    def run(self, fn: Callable[[], T], *, sleep: Callable[[float], None] = time.sleep) -> T:
        last: Exception | None = None
        delays = self.delays()
        for attempt in range(self.max_attempts):
            try:
                return fn()
            except CircuitOpenError:
                raise
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last = exc
                if attempt < len(delays):
                    sleep(delays[attempt])
        assert last is not None
        raise last


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_timeout_seconds: float = 60.0
    failures: int = 0
    opened_at: float | None = None
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self.clock() - self.opened_at >= self.reset_timeout_seconds:
            return "half_open"
        return "open"

    def call(self, fn: Callable[[], T]) -> T:
        if self.state == "open":
            raise CircuitOpenError("Circuit open: dependency unavailable, using fallback.")
        try:
            result = fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = self.clock()
            raise
        self.failures = 0
        self.opened_at = None
        return result
