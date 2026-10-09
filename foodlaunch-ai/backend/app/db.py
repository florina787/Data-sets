"""Platform persistence (SQLite) and shared helpers.

Audit and evidence tables are append-oriented through application APIs only.
SQLite offers no tamper-proofing; this is documented as a production gap.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
    role TEXT NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, ts TEXT NOT NULL,
    actor TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT, entity_id TEXT,
    outcome TEXT NOT NULL, detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, title TEXT NOT NULL, mode TEXT NOT NULL,
    status TEXT NOT NULL, stage TEXT NOT NULL, requirement_set_version INTEGER,
    step_mode INTEGER NOT NULL DEFAULT 0, pause_requested INTEGER NOT NULL DEFAULT 0,
    active_flow TEXT, active_job TEXT, waiting_for TEXT, llm_calls INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS status_history (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, from_status TEXT,
    to_status TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS briefs (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, version INTEGER NOT NULL, title TEXT NOT NULL,
    text TEXT NOT NULL, submitted_by TEXT NOT NULL, created_at TEXT NOT NULL,
    analysis_json TEXT, analysis_source TEXT, UNIQUE (run_id, version)
);
CREATE TABLE IF NOT EXISTS clarifications (
    run_id TEXT NOT NULL, id TEXT NOT NULL, brief_version INTEGER NOT NULL, topic TEXT NOT NULL,
    question TEXT NOT NULL, required INTEGER NOT NULL, blocks TEXT NOT NULL,
    options_json TEXT NOT NULL, evidence_json TEXT NOT NULL, status TEXT NOT NULL,
    decision TEXT, rationale TEXT, decision_source TEXT, decided_by TEXT, decided_at TEXT,
    detected_by TEXT NOT NULL, PRIMARY KEY (run_id, id)
);
CREATE TABLE IF NOT EXISTS requirement_sets (
    run_id TEXT NOT NULL, version INTEGER NOT NULL, brief_version INTEGER NOT NULL,
    source TEXT NOT NULL, status TEXT NOT NULL, origin TEXT NOT NULL,
    test_plan_json TEXT NOT NULL, approved_by TEXT, approved_at TEXT, created_at TEXT NOT NULL,
    incident_id TEXT, PRIMARY KEY (run_id, version)
);
CREATE TABLE IF NOT EXISTS requirements (
    run_id TEXT NOT NULL, set_version INTEGER NOT NULL, req_id TEXT NOT NULL, title TEXT NOT NULL,
    decisions_json TEXT NOT NULL, PRIMARY KEY (run_id, set_version, req_id)
);
CREATE TABLE IF NOT EXISTS acceptance_criteria (
    run_id TEXT NOT NULL, set_version INTEGER NOT NULL, ac_id TEXT NOT NULL, req_id TEXT NOT NULL,
    text TEXT NOT NULL, critical INTEGER NOT NULL, PRIMARY KEY (run_id, set_version, ac_id)
);
CREATE TABLE IF NOT EXISTS designs (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, content_json TEXT NOT NULL, source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_sets (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, patch_name TEXT NOT NULL,
    patch_hash TEXT NOT NULL, base_revision TEXT NOT NULL, revision TEXT NOT NULL,
    files_json TEXT NOT NULL, diff_text TEXT NOT NULL, label TEXT NOT NULL, agent TEXT NOT NULL,
    title TEXT NOT NULL, addresses_json TEXT NOT NULL, incident_id TEXT, created_at TEXT NOT NULL,
    UNIQUE (run_id, patch_name, base_revision)
);
CREATE TABLE IF NOT EXISTS test_runs (
    id TEXT PRIMARY KEY, run_id TEXT, revision TEXT NOT NULL, suite_version INTEGER NOT NULL,
    tests_hash TEXT NOT NULL, purpose TEXT NOT NULL, command TEXT NOT NULL, exit_code INTEGER,
    status TEXT NOT NULL, duration_s REAL, output TEXT, report_json TEXT,
    started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS test_results (
    test_run_id TEXT NOT NULL, nodeid TEXT NOT NULL, outcome TEXT NOT NULL,
    ac_ids_json TEXT NOT NULL, regression_ids_json TEXT NOT NULL, critical INTEGER NOT NULL,
    duration_s REAL NOT NULL, message TEXT, PRIMARY KEY (test_run_id, nodeid)
);
CREATE TABLE IF NOT EXISTS static_checks (
    id TEXT PRIMARY KEY, run_id TEXT, revision TEXT NOT NULL, tool TEXT NOT NULL,
    command TEXT NOT NULL, exit_code INTEGER, status TEXT NOT NULL, output TEXT,
    findings_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, revision TEXT NOT NULL, severity TEXT NOT NULL,
    blocking INTEGER NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL, source TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS releases (
    id TEXT PRIMARY KEY, run_id TEXT, revision TEXT NOT NULL, kind TEXT NOT NULL,
    status TEXT NOT NULL, manifest_json TEXT NOT NULL, manifest_hash TEXT NOT NULL,
    incident_id TEXT, created_at TEXT NOT NULL, deployed_at TEXT, label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, release_id TEXT NOT NULL UNIQUE, approver TEXT NOT NULL,
    revision TEXT NOT NULL, manifest_hash TEXT NOT NULL, created_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY, release_id TEXT NOT NULL, revision TEXT NOT NULL, action TEXT NOT NULL,
    pid INTEGER, port INTEGER NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
    finished_at TEXT, health_json TEXT, log_path TEXT, lifecycle_json TEXT NOT NULL DEFAULT '[]',
    requested_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY, run_id TEXT, release_id TEXT, revision TEXT, status TEXT NOT NULL,
    title TEXT NOT NULL, opened_at TEXT NOT NULL, resolved_at TEXT, analysis_json TEXT,
    fault_scripted INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS evidence (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, type TEXT NOT NULL,
    source TEXT NOT NULL, ts TEXT NOT NULL, revision TEXT, run_id TEXT, ref_table TEXT,
    ref_id TEXT, summary TEXT NOT NULL, provenance TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, ts TEXT NOT NULL,
    agent TEXT NOT NULL, kind TEXT NOT NULL, provenance TEXT NOT NULL, summary TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT, status TEXT NOT NULL,
    created_at TEXT NOT NULL, finished_at TEXT, result_json TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id TEXT PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, revision TEXT,
    release_id TEXT, route TEXT, method TEXT, status INTEGER, error TEXT, dependency TEXT,
    operation TEXT, outcome TEXT, latency_ms REAL
);
CREATE INDEX IF NOT EXISTS telemetry_ts ON telemetry_events (ts);
CREATE TABLE IF NOT EXISTS sim_stock (sku TEXT PRIMARY KEY, stock INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sim_reservations (
    id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, units_json TEXT NOT NULL, state TEXT NOT NULL,
    campaign_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sim_restocks (key TEXT PRIMARY KEY, created_at TEXT NOT NULL);
"""

_init_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def connect() -> sqlite3.Connection:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db() -> None:
    with _init_lock:
        conn = connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()


def rows(sql: str, params: tuple = ()) -> list[dict]:
    with session() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(sql: str, params: tuple = ()) -> dict | None:
    with session() as conn:
        found = conn.execute(sql, params).fetchone()
        return dict(found) if found else None


def execute(sql: str, params: tuple = ()) -> None:
    with session() as conn:
        conn.execute(sql, params)


def kv_get(key: str, default: Any = None) -> Any:
    found = row("SELECT value FROM kv WHERE key = ?", (key,))
    return json.loads(found["value"]) if found else default


def kv_set(key: str, value: Any) -> None:
    execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )


def loads(value: str | None, default: Any = None) -> Any:
    return json.loads(value) if value else default
