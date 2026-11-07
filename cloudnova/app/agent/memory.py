"""Conversation memory + trace store (SQLite). Pattern from ConvoLens/FloPilot conversation context:
per-session turns; we additionally keep the last QueryPlan so follow-ups can patch it."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from ..config import get_settings

_lock = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (session_id TEXT, turn INTEGER, at REAL, question TEXT, intent TEXT,
  plan_json TEXT, answer TEXT, sql TEXT, PRIMARY KEY (session_id, turn));
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, session_id TEXT, at REAL, question TEXT, intent TEXT,
  planner TEXT, status TEXT, total_ms REAL, llm_ms REAL, sql_ms REAL, trace_json TEXT);
"""


@contextmanager
def _db():
    s = get_settings()
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(s.runtime_dir / "copilot.db")
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def history(session_id: str, n: int = 6) -> list[dict]:
    with _lock, _db() as con:
        rows = con.execute("SELECT turn, question, intent, plan_json, answer, sql FROM turns WHERE session_id=? "
                           "ORDER BY turn DESC LIMIT ?", (session_id, n)).fetchall()
    return [{"turn": r[0], "question": r[1], "intent": r[2], "plan": json.loads(r[3]) if r[3] else None,
             "answer": r[4], "sql": r[5]} for r in reversed(rows)]


def last_plan(session_id: str) -> tuple[dict | None, str | None]:
    for t in reversed(history(session_id, 10)):
        if t["plan"]:
            return t["plan"], t["sql"]
    return None, None


def append(session_id: str, question: str, intent: str, plan: dict | None, answer: str, sql: str | None) -> None:
    with _lock, _db() as con:
        n = con.execute("SELECT COALESCE(MAX(turn), 0) + 1 FROM turns WHERE session_id=?", (session_id,)).fetchone()[0]
        con.execute("INSERT INTO turns VALUES (?,?,?,?,?,?,?,?)", (session_id, n, time.time(), question, intent,
                                                                  json.dumps(plan) if plan else None, answer, sql))


def clear(session_id: str) -> int:
    with _lock, _db() as con:
        return con.execute("DELETE FROM turns WHERE session_id=?", (session_id,)).rowcount


def record_run(run: dict) -> None:
    with _lock, _db() as con:
        con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            run["run_id"], run["session_id"], time.time(), run["question"][:300], run["intent"], run["planner"],
            run["status"], run["total_ms"], run.get("llm_ms", 0.0), run.get("sql_ms", 0.0), json.dumps(run["trace"])))


def recent_runs(limit: int = 50) -> list[dict]:
    with _lock, _db() as con:
        rows = con.execute("SELECT run_id, session_id, at, question, intent, planner, status, total_ms, llm_ms, sql_ms, trace_json "
                           "FROM runs ORDER BY at DESC LIMIT ?", (limit,)).fetchall()
    keys = ["run_id", "session_id", "at", "question", "intent", "planner", "status", "total_ms", "llm_ms", "sql_ms", "trace"]
    return [dict(zip(keys, r[:-1] + (json.loads(r[-1]),))) for r in rows]
