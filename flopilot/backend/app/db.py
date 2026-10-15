"""Metadata store.

SQLite (stdlib) for local development. The SQL deliberately sticks to a portable subset
(TEXT/INTEGER/REAL columns, no SQLite-only functions) so the schema can be migrated to
PostgreSQL; see docs/DEPLOYMENT.md. Workbook *contents* never live here, only metadata.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id), role TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workbooks (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, owner_id TEXT NOT NULL, name TEXT NOT NULL,
  source_format TEXT NOT NULL, current_version INTEGER NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, deleted_at TEXT);
CREATE TABLE IF NOT EXISTS versions (
  id TEXT PRIMARY KEY, workbook_id TEXT NOT NULL REFERENCES workbooks(id), version_no INTEGER NOT NULL,
  storage_key TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, kind TEXT NOT NULL,
  operation_id TEXT, note TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE (workbook_id, version_no));
CREATE TABLE IF NOT EXISTS operations (
  id TEXT PRIMARY KEY, workbook_id TEXT NOT NULL, base_version INTEGER NOT NULL, run_id TEXT,
  action_type TEXT NOT NULL, mutating INTEGER NOT NULL, status TEXT NOT NULL, title TEXT NOT NULL,
  payload TEXT NOT NULL, change_set_hash TEXT NOT NULL, result_version INTEGER, result TEXT,
  idempotency_key TEXT UNIQUE, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES operations(id), workbook_version INTEGER NOT NULL,
  change_set_hash TEXT NOT NULL, decision TEXT NOT NULL, acknowledged_risks TEXT NOT NULL,
  user_id TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, workbook_id TEXT NOT NULL, workbook_version INTEGER NOT NULL,
  conversation_id TEXT NOT NULL, user_id TEXT NOT NULL, workspace_id TEXT NOT NULL, state TEXT NOT NULL,
  intent TEXT, plan TEXT, steps TEXT NOT NULL, result TEXT, error TEXT, model TEXT, prompt_version TEXT,
  tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0, cost_estimate_usd REAL NOT NULL DEFAULT 0,
  cancel_requested INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, workbook_id TEXT NOT NULL, user_id TEXT NOT NULL, title TEXT NOT NULL,
  context TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
  run_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY, ts TEXT NOT NULL, event_type TEXT NOT NULL, run_id TEXT, correlation_id TEXT,
  user_id TEXT, workspace_id TEXT, workbook_id TEXT, workbook_version INTEGER, detail TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_versions_wb ON versions(workbook_id);
CREATE INDEX IF NOT EXISTS ix_ops_wb ON operations(workbook_id);
CREATE INDEX IF NOT EXISTS ix_runs_wb ON runs(workbook_id);
CREATE INDEX IF NOT EXISTS ix_audit_wb ON audit_events(workbook_id);
CREATE INDEX IF NOT EXISTS ix_msgs_conv ON messages(conversation_id);
"""

_lock = threading.RLock()
_initialized_path: str | None = None


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    global _initialized_path
    path = str(get_settings().sqlite_path)
    with _lock:
        conn = _connect()
        try:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?) ON CONFLICT(key) DO NOTHING",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()
        finally:
            conn.close()
        _initialized_path = path


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """A serialized transaction. Writes are small and infrequent, so one lock is enough locally."""
    if _initialized_path != str(get_settings().sqlite_path):
        init_db()
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def fetchone(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with tx() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def fetchall(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with tx() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def execute(sql: str, params: tuple = ()) -> int:
    with tx() as conn:
        return conn.execute(sql, params).rowcount


def dumps(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


def loads(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    return json.loads(value)
