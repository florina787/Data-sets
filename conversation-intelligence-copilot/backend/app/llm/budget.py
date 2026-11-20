"""Per-request model budget and token streaming, passed to the provider without changing every call signature.

`model_budget(seconds, on_text)` sets a deadline and a callback for the calls made inside it. Providers that
stream (the local llama.cpp client) check the deadline between tokens and stop with `DeadlineExceeded`, and report
the text generated so far to `on_text`. Callers then fall back to the deterministic answer.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_deadline: ContextVar[float | None] = ContextVar("llm_deadline", default=None)
_on_text: ContextVar[Callable[[str], None] | None] = ContextVar("llm_on_text", default=None)


class DeadlineExceeded(TimeoutError):
    """The model did not finish inside the caller's time budget. Not retried; does not open the circuit breaker."""


@contextmanager
def model_budget(seconds: float | None, on_text: Callable[[str], None] | None = None) -> Iterator[None]:
    t1 = _deadline.set(time.perf_counter() + seconds if seconds and seconds > 0 else None)
    t2 = _on_text.set(on_text)
    try:
        yield
    finally:
        _deadline.reset(t1)
        _on_text.reset(t2)


def remaining() -> float | None:
    d = _deadline.get()
    return None if d is None else d - time.perf_counter()


def report_text(text: str) -> None:
    cb = _on_text.get()
    if cb:
        try:
            cb(text)
        except Exception:  # noqa: BLE001 - progress reporting must never break generation
            pass
