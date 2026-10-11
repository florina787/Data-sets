"""Typed connector contracts shared by synthetic and enterprise adapters."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")


class ConnectorError(Exception):
    code = "CONNECTOR_ERROR"
    retryable = False


class ConnectorUnavailable(ConnectorError):
    code = "CONNECTOR_UNAVAILABLE"


class ConnectorTimeout(ConnectorError):
    code = "CONNECTOR_TIMEOUT"
    retryable = True


class ConnectorNotFound(ConnectorError):
    code = "CONNECTOR_NOT_FOUND"


class OutcomeUnknown(ConnectorError):
    """A write may or may not have been applied (e.g. response lost).
    Callers must reconcile before retrying."""

    code = "OUTCOME_UNKNOWN"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    classification: str  # read | write
    required_permission: str
    input_schema: dict
    timeout_seconds: float
    idempotency: str  # none | required
    errors: tuple[str, ...]
    audit_fields: tuple[str, ...]
    requires_approval: bool = False
    connector_mode: str = "SIMULATED"
    available: bool = True
    unavailable_reason: str = ""
    extra: dict = field(default_factory=dict)


def retry_read(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 0.05,
               sleep: Callable[[float], None] = time.sleep) -> T:
    """Exponential backoff with full jitter, for retryable READ failures only."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except ConnectorError as exc:
            if not exc.retryable:
                raise
            last = exc
            if i < attempts - 1:
                sleep(random.uniform(0, base_delay * (2 ** i)))
    assert last is not None
    raise last
