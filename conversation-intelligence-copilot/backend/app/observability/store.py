"""SQLite telemetry store: requests, node events (traces), LLM calls, audit events.

Only sanitised summaries are stored: no API keys, and message text only in its
PII-masked form.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY, session_id TEXT, created_at TEXT, question TEXT, intent TEXT, operations TEXT,
    status TEXT, latency_ms REAL, error_category TEXT, llm_mode TEXT, quality_status TEXT, response_json TEXT
);
CREATE TABLE IF NOT EXISTS node_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, node TEXT, status TEXT, started_at TEXT, finished_at TEXT,
    duration_ms REAL, retries INTEGER, input_summary TEXT, output_summary TEXT, error TEXT, meta_json TEXT
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, created_at TEXT, purpose TEXT, prompt_id TEXT, prompt_version TEXT,
    model TEXT, input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, latency_ms REAL, retries INTEGER,
    cache_hit INTEGER, status TEXT, error TEXT, estimated_cost_usd REAL, rate_limited INTEGER
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, request_id TEXT, session_id TEXT, category TEXT, action TEXT, detail_json TEXT
);
CREATE TABLE IF NOT EXISTS ui_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, session_id TEXT, event TEXT, detail_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_node_req ON node_events(request_id);
CREATE INDEX IF NOT EXISTS idx_llm_req ON llm_calls(request_id);
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


class TelemetryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")  # persistent: readers never block the writer
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        # With WAL, NORMAL syncs at checkpoints instead of on every commit: the store stays consistent, and a
        # power cut can lose at most the last few rows. Full syncs cost tens of ms per request on many small writes.
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _exec(self, sql: str, params: tuple) -> None:
        with self._lock, self._conn() as c:
            c.execute(sql, params)

    def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    # writes ---------------------------------------------------------------
    def record_request(self, **r) -> None:
        self._exec(
            "INSERT OR REPLACE INTO requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["request_id"], r.get("session_id"), r.get("created_at", now()), r.get("question"), json.dumps(r.get("intent")),
             json.dumps(r.get("operations")), r.get("status"), r.get("latency_ms"), r.get("error_category"), r.get("llm_mode"),
             r.get("quality_status"), json.dumps(r.get("response"), default=str) if r.get("response") is not None else None),
        )

    def record_node(self, request_id: str, ev: dict) -> None:
        self._exec(
            "INSERT INTO node_events (request_id,node,status,started_at,finished_at,duration_ms,retries,input_summary,output_summary,error,meta_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (request_id, ev["node"], ev["status"], ev.get("started_at"), ev.get("finished_at"), ev.get("duration_ms"), ev.get("retries", 0),
             json.dumps(ev.get("input_summary"), default=str), json.dumps(ev.get("output_summary"), default=str), ev.get("error"),
             json.dumps(ev.get("meta", {}), default=str)),
        )

    def record_llm_call(self, **c) -> None:
        self._exec(
            "INSERT INTO llm_calls (request_id,created_at,purpose,prompt_id,prompt_version,model,input_tokens,output_tokens,total_tokens,"
            "latency_ms,retries,cache_hit,status,error,estimated_cost_usd,rate_limited) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c.get("request_id"), now(), c.get("purpose"), c.get("prompt_id"), c.get("prompt_version"), c.get("model"), c.get("input_tokens"),
             c.get("output_tokens"), c.get("total_tokens"), c.get("latency_ms"), c.get("retries", 0), int(bool(c.get("cache_hit"))),
             c.get("status"), c.get("error"), c.get("estimated_cost_usd"), int(bool(c.get("rate_limited")))),
        )

    def audit(self, category: str, action: str, detail: dict | None = None, request_id: str | None = None, session_id: str | None = None) -> None:
        self._exec("INSERT INTO audit_events (created_at,request_id,session_id,category,action,detail_json) VALUES (?,?,?,?,?,?)",
                   (now(), request_id, session_id, category, action, json.dumps(detail or {}, default=str)))

    def ui_event(self, session_id: str | None, event: str, detail: dict | None = None) -> None:
        self._exec("INSERT INTO ui_events (created_at,session_id,event,detail_json) VALUES (?,?,?,?)", (now(), session_id, event, json.dumps(detail or {})))

    # reads ------------------------------------------------------------------
    def trace(self, request_id: str) -> dict | None:
        req = self._all("SELECT * FROM requests WHERE request_id=?", (request_id,))
        if not req:
            return None
        nodes = self._all("SELECT * FROM node_events WHERE request_id=? ORDER BY id", (request_id,))
        for n in nodes:
            for k in ("input_summary", "output_summary", "meta_json"):
                n[k] = json.loads(n[k]) if n[k] else None
        calls = self._all("SELECT * FROM llm_calls WHERE request_id=? ORDER BY id", (request_id,))
        r = req[0]
        r["intent"] = json.loads(r["intent"]) if r["intent"] else None
        r["operations"] = json.loads(r["operations"]) if r["operations"] else None
        r.pop("response_json", None)
        return {"request": r, "nodes": nodes, "llm_calls": calls}

    def request_usage(self, request_id: str) -> dict:
        """Per-request LLM accounting. Tokens are null when calls were made but no provider reported usage;
        0 only when no model call was made (or every call was a cache hit)."""
        rows = self._all("SELECT purpose,model,input_tokens,output_tokens,total_tokens,cache_hit,status,latency_ms,estimated_cost_usd "
                         "FROM llm_calls WHERE request_id=? ORDER BY id", (request_id,))
        return usage_summary(rows)

    def token_accounting(self) -> dict:
        """Dataset-preprocessing tokens (LLM labelling) kept apart from per-query tokens, plus routing outcomes.
        Calls whose provider reported no usage are counted as unreported, never as zero."""
        def agg(where: str) -> dict:
            r = self._all(f"""SELECT COUNT(*) calls, SUM(cache_hit) cache_hits, SUM(cache_hit=0 AND total_tokens IS NULL) unreported,
                                     SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(total_tokens) total_tokens,
                                     SUM(estimated_cost_usd) estimated_cost_usd FROM llm_calls WHERE {where}""")[0]
            r["cache_hits"] = r["cache_hits"] or 0
            live = r["calls"] - r["cache_hits"]
            if live == 0:
                r["estimated_cost_usd"] = 0.0
            for k in ("input_tokens", "output_tokens", "total_tokens"):
                r[k] = r[k] if r[k] is not None else (0 if live == 0 else None)
            r["unreported"] = r["unreported"] or 0
            r["complete"] = r["unreported"] == 0
            return r
        routes = self._all("""SELECT json_extract(response_json,'$.routing.route') route, COUNT(*) n,
                                     SUM(json_extract(response_json,'$.token_usage.model_calls')) model_calls
                              FROM requests WHERE response_json IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
        by_purpose = self._all("SELECT purpose, COUNT(*) calls, SUM(total_tokens) total_tokens, SUM(total_tokens IS NULL AND cache_hit=0) unreported "
                               "FROM llm_calls GROUP BY 1 ORDER BY 2 DESC")
        return {"preprocessing": agg("purpose='labelling'"), "per_query": agg("purpose<>'labelling'"), "by_purpose": by_purpose, "routes": routes}

    def response(self, request_id: str) -> dict | None:
        rows = self._all("SELECT response_json FROM requests WHERE request_id=?", (request_id,))
        return json.loads(rows[0]["response_json"]) if rows and rows[0]["response_json"] else None

    def recent_requests(self, limit: int = 50) -> list[dict]:
        rows = self._all("SELECT request_id,session_id,created_at,question,intent,status,latency_ms,error_category,llm_mode,quality_status "
                         "FROM requests ORDER BY created_at DESC LIMIT ?", (limit,))
        for r in rows:
            r["intent"] = json.loads(r["intent"]) if r["intent"] else None
        return rows

    def summary(self) -> dict:
        req = self._all("""SELECT COUNT(*) n, SUM(status='completed') ok, SUM(status<>'completed') failed, AVG(latency_ms) avg_ms,
                                  COUNT(DISTINCT session_id) sessions FROM requests""")[0]
        lat = [r["latency_ms"] for r in self._all("SELECT latency_ms FROM requests WHERE latency_ms IS NOT NULL ORDER BY latency_ms")]
        pct = (lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] if lat else None)
        llm = self._all("""SELECT COUNT(*) calls, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, SUM(total_tokens) total_tokens,
                                  SUM(cache_hit) cache_hits, SUM(status<>'ok') failures, SUM(rate_limited) rate_limited, SUM(retries) retries,
                                  SUM(estimated_cost_usd) cost, AVG(latency_ms) avg_ms FROM llm_calls""")[0]
        by_intent = self._all("""SELECT json_extract(intent,'$.category') intent, COUNT(*) n, AVG(latency_ms) avg_ms FROM requests GROUP BY 1 ORDER BY 2 DESC""")
        nodes = self._all("""SELECT node, COUNT(*) runs, AVG(duration_ms) avg_ms, MAX(duration_ms) max_ms, SUM(status='failed') failed, SUM(status='skipped') skipped
                             FROM node_events GROUP BY node ORDER BY avg_ms DESC""")
        errors = self._all("SELECT error_category, COUNT(*) n FROM requests WHERE error_category IS NOT NULL GROUP BY 1")
        llm_errors = self._all("SELECT error, COUNT(*) n FROM llm_calls WHERE status<>'ok' GROUP BY 1 ORDER BY 2 DESC LIMIT 5")
        modes = self._all("SELECT llm_mode, COUNT(*) n FROM requests GROUP BY 1")
        daily = self._all("SELECT substr(created_at,1,10) day, COUNT(*) n FROM requests GROUP BY 1 ORDER BY 1")
        ui = self._all("SELECT event, COUNT(*) n FROM ui_events GROUP BY 1 ORDER BY 2 DESC")
        followups = self._all("SELECT COUNT(*) n FROM requests WHERE json_extract(intent,'$.is_follow_up')=1")[0]["n"]
        return {
            "requests": {**req, "p50_ms": pct(0.5), "p95_ms": pct(0.95), "follow_ups": followups},
            "llm": llm, "by_intent": by_intent, "nodes": nodes, "errors": errors, "llm_errors": llm_errors,
            "llm_modes": modes, "daily": daily, "ui_events": ui,
        }

    def audit_log(self, limit: int = 100) -> list[dict]:
        rows = self._all("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["detail"] = json.loads(r.pop("detail_json") or "{}")
        return rows


def usage_summary(rows: list[dict]) -> dict:
    live = [r for r in rows if not r["cache_hit"]]
    reported = [r for r in live if r["total_tokens"] is not None]
    unreported = len(live) - len(reported)

    def total(k: str):
        if not live:
            return 0
        return sum(r[k] or 0 for r in reported) if reported else None

    costs = [r["estimated_cost_usd"] for r in reported if r["estimated_cost_usd"] is not None]
    return {"calls": len(rows), "model_calls": len(live), "cache_hits": len(rows) - len(live), "reported_calls": len(reported),
            "unreported_calls": unreported, "complete": unreported == 0,
            "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"), "total_tokens": total("total_tokens"),
            "estimated_cost_usd": round(sum(costs), 6) if costs else (0.0 if not live else None),
            "by_purpose": [{k: r[k] for k in ("purpose", "model", "total_tokens", "cache_hit", "status", "latency_ms")} for r in rows]}


@lru_cache
def get_telemetry() -> TelemetryStore:
    return TelemetryStore(get_settings().memory_database_path.parent / "telemetry.sqlite")
