"""Session memory (SQLite).

Stores what is needed to resolve follow-up questions: the resolved intent, the
applied scope and plan, and *references* to deterministic results (ranked keys,
conversation ids). It deliberately does not store model prose as a source of
truth: follow-ups re-run the referenced analysis and re-validate the references.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, created_at TEXT, updated_at TEXT, title TEXT, dataset_mode TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, request_id TEXT, created_at TEXT, question TEXT,
    intent_json TEXT, scope_json TEXT, plan_json TEXT, refs_json TEXT, summary TEXT, status TEXT
);
CREATE INDEX IF NOT EXISTS idx_turn_session ON turns(session_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_session(self, session_id: str | None, dataset_mode: str, title: str) -> str:
        sid = session_id or f"S-{uuid.uuid4().hex[:12]}"
        with self._lock, self._conn() as c:
            row = c.execute("SELECT session_id FROM sessions WHERE session_id=?", (sid,)).fetchone()
            if row is None:
                c.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, _now(), _now(), title[:80], dataset_mode))
            else:
                c.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (_now(), sid))
        return sid

    def add_turn(self, session_id: str, request_id: str, question: str, intent: dict, scope: dict, plan: dict, refs: dict,
                 summary: str, status: str) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO turns (session_id,request_id,created_at,question,intent_json,scope_json,plan_json,refs_json,summary,status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (session_id, request_id, _now(), question, json.dumps(intent), json.dumps(scope), json.dumps(plan), json.dumps(refs), summary[:1000], status),
            )

    def history(self, session_id: str, limit: int = 6) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM turns WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
        out = []
        for r in reversed(rows):
            d = dict(r)
            for k in ("intent_json", "scope_json", "plan_json", "refs_json"):
                d[k.removesuffix("_json")] = json.loads(d.pop(k) or "{}")
            out.append(d)
        return out

    def last_successful(self, session_id: str) -> dict | None:
        """Latest completed analytical turn. If it produced no ranking, the most recent earlier ranking is
        attached (with its request id) so references like "the first one" still resolve."""
        hist = [h for h in self.history(session_id, 20) if h["status"] == "completed" and h["plan"].get("steps")]
        if not hist:
            return None
        last = hist[-1]
        if not last["refs"].get("ranking"):
            earlier = next((h for h in reversed(hist[:-1]) if h["refs"].get("ranking")), None)
            if earlier:
                last["refs"] = {**last["refs"], "ranking": earlier["refs"]["ranking"], "dimension": earlier["refs"].get("dimension", "topic"),
                                "ranking_from": earlier["request_id"]}
        return last

    def sessions(self, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT s.*, (SELECT COUNT(*) FROM turns t WHERE t.session_id=s.session_id) AS turns FROM sessions s ORDER BY updated_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return None
        return {**dict(row), "turns": self.history(session_id, 50)}

    def clear_session(self, session_id: str) -> bool:
        with self._lock, self._conn() as c:
            n = c.execute("DELETE FROM turns WHERE session_id=?", (session_id,)).rowcount
            m = c.execute("DELETE FROM sessions WHERE session_id=?", (session_id,)).rowcount
        return bool(n or m)

    def purge_older_than(self, days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        with self._lock, self._conn() as c:
            old = [r[0] for r in c.execute("SELECT session_id FROM sessions WHERE updated_at < ?", (cutoff,)).fetchall()]
            for sid in old:
                c.execute("DELETE FROM turns WHERE session_id=?", (sid,))
                c.execute("DELETE FROM sessions WHERE session_id=?", (sid,))
        return len(old)


@lru_cache
def get_memory() -> MemoryStore:
    return MemoryStore(get_settings().memory_database_path)
