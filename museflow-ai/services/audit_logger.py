"""Tamper-evident, session-scoped audit log (SHA-256 hash chain)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

GENESIS = "0" * 64


def _digest(prev_hash: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{prev_hash}|{body}".encode()).hexdigest()


class AuditLogger:
    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    @property
    def head(self) -> str:
        return self._entries[-1]["hash"] if self._entries else GENESIS

    def record(self, run_id: str, kind: str, detail: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "seq": len(self._entries) + 1,
            "run_id": run_id,
            "kind": kind,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        entry = {**payload, "prev_hash": self.head, "hash": _digest(self.head, payload)}
        self._entries.append(entry)
        return dict(entry)

    def entries(self, run_id: str | None = None) -> list[dict[str, Any]]:
        return [dict(e) for e in self._entries if run_id is None or e["run_id"] == run_id]

    def verify(self) -> bool:
        prev = GENESIS
        for entry in self._entries:
            payload = {k: entry[k] for k in ("seq", "run_id", "kind", "detail", "at")}
            if entry["prev_hash"] != prev or entry["hash"] != _digest(prev, payload):
                return False
            prev = entry["hash"]
        return True

    def __len__(self) -> int:
        return len(self._entries)
