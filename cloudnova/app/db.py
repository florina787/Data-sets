"""Read-only DuckDB execution with timeout, row cap, PII masking (specs/query_interface.md §3)."""
from __future__ import annotations

import threading
import time
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache

import duckdb

from .config import get_settings
from .errors import AppError
from .governance.sql_guard import check_sql

PII_COLUMNS = {"contact_email"}


def _connect() -> duckdb.DuckDBPyConnection:
    s = get_settings()
    if not s.db_path.exists():
        raise AppError("data_not_built", "The cleaned dataset has not been built yet. Run `python -m app build`.", 503)
    con = duckdb.connect(str(s.db_path), read_only=True, config={
        "enable_external_access": False, "autoload_known_extensions": False, "autoinstall_known_extensions": False,
        "memory_limit": s.duckdb_memory_limit, "threads": 2})
    try:
        con.execute("SET lock_configuration = true")
    except duckdb.InvalidInputException:
        pass  # DuckDB shares one instance per file per process: already locked by an earlier connection
    return con


_local = threading.local()


def connection() -> duckdb.DuckDBPyConnection:
    con = getattr(_local, "con", None)
    if con is None:
        con = _local.con = _connect()
    return con


def reset_connections() -> None:
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
        _local.con = None
    schema.cache_clear()


@lru_cache
def schema() -> dict[str, set[str]]:
    rows = connection().execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'main'").fetchall()
    out: dict[str, set[str]] = {}
    for t, c in rows:
        out.setdefault(t.lower(), set()).add(c.lower())
    return out


def schema_with_types() -> dict[str, list[tuple[str, str]]]:
    rows = connection().execute("SELECT table_name, column_name, data_type FROM information_schema.columns "
                                "WHERE table_schema='main' ORDER BY table_name, ordinal_position").fetchall()
    out: dict[str, list] = {}
    for t, c, ty in rows:
        out.setdefault(t, []).append((c, ty))
    return out


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def run_query(sql: str, max_rows: int | None = None) -> dict:
    """Guard → execute (read-only, timeout) → bounded, JSON-safe result."""
    s = get_settings()
    guarded = check_sql(sql, schema())
    con = connection()
    limit = max_rows or s.max_result_rows
    timer = threading.Timer(s.query_timeout_s, con.interrupt)
    t0 = time.perf_counter()
    timer.start()
    try:
        cur = con.execute(guarded.sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(limit + 1)
    except duckdb.InterruptException as exc:
        raise AppError("query_timeout", f"The query took longer than {s.query_timeout_s:.0f}s and was stopped.", 504, retryable=True) from exc
    except duckdb.Error as exc:
        raise AppError("sql_error", f"The database could not run this query: {str(exc).splitlines()[0][:200]}", 422) from exc
    finally:
        timer.cancel()
    truncated = len(rows) > limit
    rows = rows[:limit]
    mask = [i for i, c in enumerate(cols) if c.lower() in PII_COLUMNS and not s.allow_pii]
    out_rows = []
    for r in rows:
        r = [_jsonable(v) for v in r]
        for i in mask:
            if isinstance(r[i], str) and "@" in r[i]:
                user, dom = r[i].split("@", 1)
                r[i] = user[:1] + "***@" + dom
        out_rows.append(r)
    return {"columns": cols, "rows": out_rows, "row_count": len(out_rows), "truncated": truncated,
            "sql": guarded.sql, "tables": sorted(guarded.tables), "ms": round((time.perf_counter() - t0) * 1000, 1)}


def internal_scalar(sql: str):
    """Trusted, read-only scalar query for evals/tests/admin views — bypasses the chat allow-list (e.g. to count
    `rejected_rows`, which holds raw PII and is never exposed to conversational SQL). Never call with user input."""
    return connection().execute(sql).fetchone()[0]
