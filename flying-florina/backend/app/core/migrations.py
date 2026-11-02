"""Versioned, forward-only SQLite schema migrations (Flying Florina 3.0).

The 1.0/2.0 base schema stays in `db.SCHEMA` (idempotent CREATE IF NOT EXISTS). Everything added from 3.0 on is a numbered migration
recorded in `schema_migrations`, so an existing database is upgraded in place on startup and nothing the user saved is lost.
"""

from __future__ import annotations

import sqlite3

from app.core.util import now_iso

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "forecast runs", """
CREATE TABLE IF NOT EXISTS forecast_runs (id TEXT PRIMARY KEY, ts TEXT, model_version TEXT, dataset TEXT, data_hash TEXT,
  build_ms REAL, metrics_json TEXT);
"""),
    (2, "conversation memory", """
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, user_id TEXT NOT NULL,
  role TEXT NOT NULL, content TEXT NOT NULL, run_id TEXT, intent TEXT, slots_json TEXT, ts TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_msg_session ON messages(session_id, id);
CREATE INDEX IF NOT EXISTS ix_msg_user ON messages(user_id, id);
CREATE TABLE IF NOT EXISTS conversation_summaries (session_id TEXT PRIMARY KEY, user_id TEXT, summary TEXT, slots_json TEXT,
  turns INTEGER, updated TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(session_id UNINDEXED, user_id UNINDEXED, content);
CREATE TABLE IF NOT EXISTS user_preferences (user_id TEXT, key TEXT, value TEXT, updated TEXT, PRIMARY KEY (user_id, key));
"""),
    (3, "scenarios, evidence references, visual analyses", """
CREATE TABLE IF NOT EXISTS saved_scenarios (id TEXT PRIMARY KEY, user_id TEXT, kind TEXT, name TEXT, params_json TEXT,
  result_json TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS evidence_refs (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, kind TEXT, ref TEXT, detail_json TEXT, ts TEXT);
CREATE INDEX IF NOT EXISTS ix_ev_run ON evidence_refs(run_id);
CREATE TABLE IF NOT EXISTS visual_analyses (id TEXT PRIMARY KEY, user_id TEXT, ts TEXT, source TEXT, filename TEXT, sha256 TEXT,
  frames INTEGER, method TEXT, result_json TEXT);
"""),
    (4, "agent harness plans", """
CREATE TABLE IF NOT EXISTS harness_plans (run_id TEXT PRIMARY KEY, ts TEXT, user_id TEXT, intent TEXT, agents_json TEXT,
  tools_json TEXT, budget_json TEXT, usage_json TEXT, outcome TEXT);
"""),
]


def apply(conn: sqlite3.Connection) -> list[int]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied TEXT)")
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    applied = []
    for version, name, sql in MIGRATIONS:
        if version in done:
            continue
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations VALUES (?,?,?)", (version, name, now_iso()))
        applied.append(version)
    return applied


def status(conn: sqlite3.Connection) -> list[dict[str, object]]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied TEXT)")
    return [{"version": r[0], "name": r[1], "applied": r[2]} for r in conn.execute("SELECT * FROM schema_migrations ORDER BY version")]
