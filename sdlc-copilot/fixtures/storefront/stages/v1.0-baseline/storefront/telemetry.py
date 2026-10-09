"""Append-only JSONL telemetry read by the SDLC Copilot control room."""

from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator


class Telemetry:
    def __init__(self, path: str | None, revision: str, release_id: str) -> None:
        self.path = path
        self.revision = revision
        self.release_id = release_id
        self._lock = threading.Lock()

    def emit(self, kind: str, **fields: Any) -> None:
        if not self.path:
            return
        event = {
            "event_id": uuid.uuid4().hex,
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "revision": self.revision,
            "release_id": self.release_id,
            **fields,
        }
        line = json.dumps(event, sort_keys=True)
        with self._lock, open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    @contextmanager
    def timed(self, dependency: str, operation: str) -> Iterator[None]:
        started = time.perf_counter()
        outcome, error = "ok", None
        try:
            yield
        except BaseException as exc:
            outcome, error = "error", type(exc).__name__
            raise
        finally:
            self.emit(
                "dependency",
                dependency=dependency,
                operation=operation,
                outcome=outcome,
                error=error,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
            )


_current = Telemetry(None, "unknown", "unreleased")


def configure(path: str | None, revision: str, release_id: str) -> Telemetry:
    global _current
    _current = Telemetry(path, revision, release_id)
    return _current


def get() -> Telemetry:
    return _current
