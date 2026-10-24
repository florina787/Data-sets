"""SQLite storage. Every query in the application is parameterized.

One short-lived connection per unit of work keeps the engine thread-safe for
the parallel workflow steps. WAL mode lets readers proceed during writes.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.config import get_settings

_write_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS aircraft (
  id TEXT PRIMARY KEY, type TEXT, fleet TEXT, base TEXT, status TEXT,
  in_service_date TEXT, flight_hours INTEGER, cycles INTEGER, synthetic INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS sensor_readings (
  aircraft_id TEXT, day TEXT, vibration_index REAL, egt_delta_c REAL, oil_pressure_index REAL,
  PRIMARY KEY (aircraft_id, day));

CREATE TABLE IF NOT EXISTS maintenance_events (
  id TEXT PRIMARY KEY, aircraft_id TEXT, date TEXT, type TEXT, description TEXT,
  downtime_hours REAL, cause_category TEXT, cost_usd REAL, work_order_id TEXT);
CREATE INDEX IF NOT EXISTS ix_me_ac ON maintenance_events(aircraft_id);
CREATE INDEX IF NOT EXISTS ix_me_date ON maintenance_events(date);

CREATE TABLE IF NOT EXISTS work_orders (
  id TEXT PRIMARY KEY, aircraft_id TEXT, status TEXT, priority TEXT, opened TEXT, closed TEXT,
  description TEXT, part_number TEXT, assigned_tech TEXT, duplicate_of TEXT, source_system TEXT,
  classification TEXT);
CREATE INDEX IF NOT EXISTS ix_wo_ac ON work_orders(aircraft_id);

CREATE TABLE IF NOT EXISTS technicians (
  id TEXT PRIMARY KEY, name TEXT, base TEXT, shift TEXT, qualifications TEXT);

CREATE TABLE IF NOT EXISTS hangar_slots (
  id TEXT PRIMARY KEY, base TEXT, bay TEXT, start TEXT, hours REAL, status TEXT);

CREATE TABLE IF NOT EXISTS suppliers (
  id TEXT PRIMARY KEY, name TEXT, region TEXT, portal TEXT);

CREATE TABLE IF NOT EXISTS supplier_deliveries (
  id TEXT PRIMARY KEY, supplier_id TEXT, part_number TEXT, ordered TEXT, promised_days INTEGER,
  actual_days INTEGER, lot TEXT);

CREATE TABLE IF NOT EXISTS parts (
  part_number TEXT PRIMARY KEY, name TEXT, ata_chapter TEXT, unit_cost_usd REAL, criticality TEXT,
  compatible_types TEXT, supplier_id TEXT, lead_time_days INTEGER, substitutes TEXT);

CREATE TABLE IF NOT EXISTS inventory (
  id TEXT PRIMARY KEY, part_number TEXT, location TEXT, qty INTEGER, lot TEXT,
  last_verified TEXT, source_system TEXT);
CREATE INDEX IF NOT EXISTS ix_inv_pn ON inventory(part_number);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, title TEXT, revision TEXT, effective_date TEXT, review_due TEXT,
  classification TEXT, permitted_roles TEXT, source TEXT, status TEXT, provenance_sha256 TEXT,
  superseded_by TEXT, body TEXT, tags TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(doc_id UNINDEXED, title, body, tags);

CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY, name TEXT, kind TEXT, technology TEXT, owner TEXT, criticality TEXT,
  interfaces TEXT, batch_window TEXT, auth_method TEXT, last_doc_update TEXT, notes TEXT);

CREATE TABLE IF NOT EXISTS app_dependencies (
  source TEXT, target TEXT, kind TEXT, protocol TEXT, frequency TEXT);

CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, title TEXT, kind TEXT, severity TEXT, opened TEXT, status TEXT,
  related TEXT, description TEXT);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, display_name TEXT, role TEXT, org TEXT, clearances TEXT, persona TEXT);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT, title TEXT, created TEXT, updated TEXT);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, persona TEXT, query TEXT, workflow TEXT,
  status TEXT, created TEXT, updated TEXT, state_json TEXT, options_json TEXT, replay_of TEXT);

CREATE TABLE IF NOT EXISTS workflow_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, step TEXT, agent TEXT, status TEXT,
  ts TEXT, attempt INTEGER, duration_ms REAL, summary TEXT, detail_json TEXT);
CREATE INDEX IF NOT EXISTS ix_we_run ON workflow_events(run_id);

CREATE TABLE IF NOT EXISTS policy_decisions (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, role TEXT, action TEXT, resource TEXT, label TEXT,
  destination TEXT, tool TEXT, decision TEXT, policy_id TEXT, reason TEXT, checks_json TEXT,
  run_id TEXT, tool_invocations_after INTEGER);

CREATE TABLE IF NOT EXISTS tool_invocations (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, tool TEXT, version TEXT, args_redacted TEXT,
  status TEXT, duration_ms REAL, run_id TEXT, decision_id TEXT, idempotency_key TEXT);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY, kind TEXT, title TEXT, requested_by TEXT, requested_at TEXT, expires_at TEXT,
  status TEXT, decided_by TEXT, decided_at TEXT, payload_json TEXT, payload_sha256 TEXT,
  evidence_sha256 TEXT, run_id TEXT, risk TEXT, idempotency_key TEXT, executed INTEGER DEFAULT 0,
  note TEXT);

CREATE TABLE IF NOT EXISTS audit_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, ts TEXT, actor TEXT, kind TEXT,
  summary TEXT, data_json TEXT, prev_hash TEXT, hash TEXT);

CREATE TABLE IF NOT EXISTS legacy_imports (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, filename TEXT, kind TEXT, size INTEGER, sha256 TEXT,
  result_json TEXT);

CREATE TABLE IF NOT EXISTS bridge_bundles (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, capability TEXT, path TEXT, files_json TEXT,
  test_result_json TEXT);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, kind TEXT, fmt TEXT, path TEXT, sha256 TEXT,
  classification TEXT, title TEXT);

CREATE TABLE IF NOT EXISTS simulations (
  id TEXT PRIMARY KEY, ts TEXT, actor TEXT, inputs_json TEXT, result_json TEXT, version TEXT);

CREATE TABLE IF NOT EXISTS write_log (
  idempotency_key TEXT PRIMARY KEY, ts TEXT, actor TEXT, approval_id TEXT, target TEXT, result_json TEXT);

CREATE TABLE IF NOT EXISTS governance_state (key TEXT PRIMARY KEY, value TEXT);
"""


def connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def session(write: bool = False) -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        if write:
            with _write_lock:
                yield conn
                conn.commit()
        else:
            yield conn
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def rows(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    with session() as conn:
        return rows(conn, sql, params)


def query_one(sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
    with session() as conn:
        return row(conn, sql, params)


def execute(sql: str, params: tuple | list = ()) -> None:
    with session(write=True) as conn:
        conn.execute(sql, params)


def jdump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def jload(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)
