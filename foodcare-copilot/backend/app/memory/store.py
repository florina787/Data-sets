"""Persistent memory: conversations, messages, search and execution history.

``MemoryStore`` is the persistence interface the rest of the application uses.
``SqliteMemoryStore`` is the local implementation (one file, WAL mode). A
multi-replica deployment would implement the same interface over an external
transactional database (e.g. PostgreSQL); a SQLite file must not be shared
between Kubernetes replicas through a network filesystem.

Every query is parameterised. Question text is untrusted: full-text search terms
are reduced to quoted word tokens before they reach FTS5, so query syntax in a
question cannot change the search.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from app.config import get_settings
from app.db import now_iso
from app.memory.schema import migrate

CONVERSATION_ID = re.compile(r"CNV-[0-9A-F]{10}")


class MemoryStore(Protocol):
    def init(self) -> None: ...
    def save_turn(self, conversation_id: str, username: str, question: str, answer: str,
                  meta: dict, context: dict) -> None: ...
    def conversation(self, conversation_id: str, username: str) -> dict | None: ...
    def messages(self, conversation_id: str, username: str) -> list[dict]: ...
    def list_conversations(self, username: str, limit: int = 50) -> list[dict]: ...
    def search(self, username: str, query: str, limit: int = 20) -> list[dict]: ...
    def delete_conversation(self, conversation_id: str, username: str) -> bool: ...
    def context_window(self, conversation_id: str, username: str, turns: int) -> dict: ...


def new_conversation_id() -> str:
    return f"CNV-{uuid.uuid4().hex[:10].upper()}"


def fts_query(text: str) -> str | None:
    """Turn untrusted text into an FTS5 query of quoted terms (implicit AND)."""
    words = [w for w in re.findall(r"[\w'-]+", text.lower()) if len(w) > 1][:8]
    return " ".join('"' + w.replace('"', "") + '"' for w in words) or None


class SqliteMemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._init_lock = threading.Lock()
        self._ready = False

    @property
    def path(self) -> Path:
        return self._path or get_settings().memory_db_path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> list[int]:
        with self._init_lock:
            conn = self.connect()
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                applied = migrate(conn)
            finally:
                conn.close()
            self._ready = True
            return applied

    def _conn(self) -> sqlite3.Connection:
        if not self._ready or not self.path.exists():
            self.init()
        return self.connect()

    def _q(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def _x(self, statements: list[tuple[str, tuple]]) -> int:
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                changed = sum(conn.execute(sql, params).rowcount for sql, params in statements)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
            return changed
        finally:
            conn.close()

    # --- conversations ---------------------------------------------------------------

    def save_turn(self, conversation_id: str, username: str, question: str, answer: str,
                  meta: dict, context: dict) -> None:
        ts = now_iso()
        title = question if len(question) <= 80 else question[:77] + "..."
        self._x([
            ("INSERT INTO conversations (id, username, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
             " ON CONFLICT(id) DO NOTHING", (conversation_id, username, title, ts, ts)),
            ("INSERT INTO messages (conversation_id, role, content, meta_json, created_at) VALUES (?, 'user', ?, ?, ?)",
             (conversation_id, question, "{}", ts)),
            ("INSERT INTO messages (conversation_id, role, content, meta_json, created_at)"
             " VALUES (?, 'assistant', ?, ?, ?)", (conversation_id, answer, json.dumps(meta, default=str), ts)),
            ("UPDATE conversations SET updated_at = ?, message_count = message_count + 2, context_json = ?"
             " WHERE id = ? AND username = ?", (ts, json.dumps(context, default=str), conversation_id, username)),
        ])
        self._maybe_summarise(conversation_id)

    def owner(self, conversation_id: str) -> str | None:
        found = self._q("SELECT username FROM conversations WHERE id = ?", (conversation_id,))
        return found[0]["username"] if found else None

    def conversation(self, conversation_id: str, username: str) -> dict | None:
        found = self._q("SELECT * FROM conversations WHERE id = ? AND username = ?", (conversation_id, username))
        if not found:
            return None
        item = found[0]
        item["context"] = json.loads(item.pop("context_json") or "{}")
        return item

    def messages(self, conversation_id: str, username: str) -> list[dict]:
        items = self._q("SELECT m.id, m.role, m.content, m.meta_json, m.created_at FROM messages m"
                        " JOIN conversations c ON c.id = m.conversation_id"
                        " WHERE m.conversation_id = ? AND c.username = ? ORDER BY m.id", (conversation_id, username))
        for item in items:
            item["meta"] = json.loads(item.pop("meta_json") or "{}")
        return items

    def list_conversations(self, username: str, limit: int = 50) -> list[dict]:
        return self._q("SELECT id, title, created_at, updated_at, message_count FROM conversations"
                       " WHERE username = ? ORDER BY updated_at DESC LIMIT ?", (username, max(1, min(limit, 200))))

    def search(self, username: str, query: str, limit: int = 20) -> list[dict]:
        """Historical question search over the user's own conversations (FTS5, best match first)."""
        match = fts_query(query)
        if not match:
            return []
        return self._q(
            "SELECT m.id AS message_id, m.conversation_id, c.title, m.role, m.created_at,"
            " snippet(messages_fts, 0, '[', ']', '…', 12) AS snippet"
            " FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid"
            " JOIN conversations c ON c.id = m.conversation_id"
            " WHERE messages_fts MATCH ? AND c.username = ? AND m.role = 'user'"
            " ORDER BY bm25(messages_fts) LIMIT ?", (match, username, max(1, min(limit, 50))))

    def delete_conversation(self, conversation_id: str, username: str) -> bool:
        return self._x([("DELETE FROM conversations WHERE id = ? AND username = ?", (conversation_id, username))]) > 0

    def delete_all(self, username: str) -> int:
        return self._x([("DELETE FROM conversations WHERE username = ?", (username,))])

    def context_window(self, conversation_id: str, username: str, turns: int) -> dict:
        """Bounded context for follow-ups: the last ``turns`` exchanges, the rolling
        summary of older ones and the structured context of the last answer. Never the
        whole history."""
        conv = self.conversation(conversation_id, username)
        if not conv:
            return {"recent": [], "summary": None, "context": {}}
        recent = self._q("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
                         (conversation_id, max(0, turns) * 2))
        recent.reverse()
        return {"recent": recent, "summary": conv["summary"], "context": conv["context"]}

    def _maybe_summarise(self, conversation_id: str) -> None:
        """Rolling summary, only once a conversation is long. It is extractive (the earlier
        questions, no inference), so it costs a single indexed query."""
        settings = get_settings()
        conv = self._q("SELECT message_count, summary_upto FROM conversations WHERE id = ?", (conversation_id,))
        if not conv or conv[0]["message_count"] <= settings.memory_summary_after:
            return
        keep_from = self._q("SELECT id FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 1 OFFSET ?",
                            (conversation_id, settings.memory_context_turns * 2 - 1))
        if not keep_from or keep_from[0]["id"] <= conv[0]["summary_upto"]:
            return
        older = self._q("SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' AND id < ?"
                        " ORDER BY id", (conversation_id, keep_from[0]["id"]))
        summary = "Earlier questions in this conversation: " + "; ".join(
            m["content"][:120] for m in older[-12:])
        self._x([("UPDATE conversations SET summary = ?, summary_upto = ? WHERE id = ?",
                  (summary[:1500], keep_from[0]["id"], conversation_id))])

    # --- execution history -----------------------------------------------------------

    def record_agent_run(self, run: dict, tool_calls: list[dict]) -> None:
        statements = [(
            "INSERT INTO agent_runs (id, agent, parent_id, conversation_id, run_id, status, started_at, finished_at,"
            " duration_ms, input_summary, output_summary, error, detail_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run["id"], run["agent"], run.get("parent_id"), run.get("conversation_id"), run.get("run_id"),
             run["status"], run["started_at"], run.get("finished_at"), run.get("duration_ms"),
             (run.get("input_summary") or "")[:500], (run.get("output_summary") or "")[:500], run.get("error"),
             json.dumps(run.get("detail", {}), default=str)))]
        for t in tool_calls:
            statements.append((
                "INSERT INTO tool_calls (agent_run_id, tool, args_json, status, started_at, duration_ms,"
                " result_summary, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run["id"], t["tool"], json.dumps(t.get("args", {}), default=str), t["status"], t["started_at"],
                 t.get("duration_ms"), (t.get("result_summary") or "")[:300], t.get("error"))))
        self._x(statements)

    def agent_runs(self, limit: int = 50, conversation_id: str | None = None) -> list[dict]:
        if conversation_id:
            return self._q("SELECT * FROM agent_runs WHERE conversation_id = ? ORDER BY started_at DESC LIMIT ?",
                           (conversation_id, limit))
        return self._q("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?", (limit,))

    def tool_calls_for(self, agent_run_id: str) -> list[dict]:
        return self._q("SELECT * FROM tool_calls WHERE agent_run_id = ? ORDER BY id", (agent_run_id,))

    # --- maintenance -----------------------------------------------------------------

    def apply_retention(self, days: int | None = None) -> int:
        """Delete conversations not updated within the retention period (0 = keep forever)."""
        days = get_settings().memory_retention_days if days is None else days
        if days <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="milliseconds")
        return self._x([("DELETE FROM conversations WHERE updated_at < ?", (cutoff,)),
                        ("DELETE FROM agent_runs WHERE started_at < ?", (cutoff,))])

    def stats(self) -> dict[str, Any]:
        counts = self._q("SELECT (SELECT COUNT(*) FROM conversations) AS conversations,"
                         " (SELECT COUNT(*) FROM messages) AS messages,"
                         " (SELECT COUNT(*) FROM agent_runs) AS agent_runs,"
                         " (SELECT COUNT(*) FROM tool_calls) AS tool_calls,"
                         " (SELECT MAX(version) FROM schema_migrations) AS schema_version")[0]
        counts["bytes"] = sum(p.stat().st_size for p in self.path.parent.glob(self.path.name + "*") if p.is_file())
        return counts


_store: SqliteMemoryStore | None = None
_store_lock = threading.Lock()


def get_store() -> SqliteMemoryStore:
    global _store
    with _store_lock:
        backend = get_settings().memory_backend
        if backend != "sqlite":
            raise RuntimeError(f"Memory backend '{backend}' is not implemented; only 'sqlite' is available locally")
        if _store is None or _store.path != get_settings().memory_db_path:
            _store = SqliteMemoryStore()
        return _store
