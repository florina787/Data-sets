"""Tamper-evident audit log.

Regulators and internal audit need to answer: who asked what, which client
data and documents were accessed, which model answered, and what the system
did. Each record carries the hash of the previous record, so any edit or
deletion breaks the chain and ``verify()`` detects it. Production writes the
same records to WORM storage (e.g. S3 Object Lock).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    ts: float
    actor: str
    event: str
    details: dict[str, Any]
    trace_id: str | None
    prev_hash: str
    hash: str


class AuditLog:
    GENESIS = "0" * 64

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._lock = threading.Lock()

    @staticmethod
    def _digest(seq: int, ts: float, actor: str, event: str, details: dict[str, Any], trace_id: str | None, prev: str) -> str:
        payload = json.dumps(
            {"seq": seq, "ts": ts, "actor": actor, "event": event, "details": details, "trace_id": trace_id, "prev": prev},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def record(self, actor: str, event: str, details: dict[str, Any] | None = None, trace_id: str | None = None) -> AuditRecord:
        details = details or {}
        with self._lock:
            seq = len(self._records)
            prev = self._records[-1].hash if self._records else self.GENESIS
            ts = time.time()
            rec = AuditRecord(seq, ts, actor, event, details, trace_id, prev, self._digest(seq, ts, actor, event, details, trace_id, prev))
            self._records.append(rec)
            return rec

    def records(self, actor: str | None = None, event: str | None = None) -> list[AuditRecord]:
        return [r for r in self._records if (actor is None or r.actor == actor) and (event is None or r.event == event)]

    def verify(self) -> tuple[bool, int | None]:
        """Return (ok, first_bad_seq)."""
        prev = self.GENESIS
        for r in self._records:
            expected = self._digest(r.seq, r.ts, r.actor, r.event, r.details, r.trace_id, prev)
            if r.prev_hash != prev or r.hash != expected:
                return False, r.seq
            prev = r.hash
        return True, None


audit_log = AuditLog()
