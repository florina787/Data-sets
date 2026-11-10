"""Response cache for deterministic (temperature-bounded) structured model calls.

The key covers everything that changes the answer: model, prompt id + version,
system and user content, output schema and generation config. Change any of them
and the old entry is simply never hit again.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


def cache_key(model: str, prompt_id: str, prompt_version: str, system: str, user: str, schema_name: str | None, config: dict) -> str:
    payload = json.dumps(
        {"model": model, "prompt": f"{prompt_id}@{prompt_version}", "system": system, "user": user, "schema": schema_name, "config": config},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with sqlite3.connect(path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, created_at TEXT, model TEXT, prompt TEXT, text TEXT)")

    def get(self, key: str) -> str | None:
        with sqlite3.connect(self.path) as c:
            row = c.execute("SELECT text FROM responses WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, model: str, prompt: str, text: str) -> None:
        with self._lock, sqlite3.connect(self.path) as c:
            c.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?)", (key, datetime.now(UTC).isoformat(), model, prompt, text))

    def size(self) -> int:
        with sqlite3.connect(self.path) as c:
            return c.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
