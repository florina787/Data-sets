"""Read-only DuckDB access and scope -> parameterised SQL filters.

All analytical SQL is written by developers in registered operations. User or
model input only ever reaches the database as bound parameters.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from app.config import get_settings
from app.schemas.analysis import Scope

MAX_ROWS = 5000
_lock = threading.Lock()


class AnalyticsDB:
    def __init__(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Analytics database not found at {path}. Run `make prepare` first.")
        self.path = path
        self._con = duckdb.connect(str(path), read_only=True)

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        with _lock:  # a DuckDB connection is not safe for concurrent use
            df = self._con.execute(sql, params or []).df()
        if len(df) > MAX_ROWS:
            raise ValueError(f"Query returned {len(df)} rows, above the {MAX_ROWS} row limit")
        return df

    def frame(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """Unbounded read for internal batch jobs (index build, labelling). Never exposed to user input."""
        with _lock:
            return self._con.execute(sql, params or []).df()

    def scalar(self, sql: str, params: list | None = None):
        with _lock:
            row = self._con.execute(sql, params or []).fetchone()
        return row[0] if row else None

    def metadata(self) -> dict:
        return json.loads(self.scalar("SELECT meta_json FROM build_metadata"))

    def close(self) -> None:
        self._con.close()


@lru_cache
def get_db() -> AnalyticsDB:
    return AnalyticsDB(get_settings().database_path)


def reset_db() -> None:
    if get_db.cache_info().currsize:
        get_db().close()
    get_db.cache_clear()


DATASET_SOURCES = {"original": ["original"], "synthetic": ["synthetic_demo"], "combined": ["original", "synthetic_demo"]}


def where(scope: Scope, alias: str = "c", skip: set[str] | None = None) -> tuple[str, list]:
    """Build a WHERE clause for the conversations table from a validated scope."""
    skip = skip or set()
    clauses: list[str] = []
    params: list = []

    def in_list(col: str, values: list[str]) -> None:
        clauses.append(f"{alias}.{col} IN ({','.join('?' * len(values))})")
        params.extend(values)

    in_list("dataset_source", DATASET_SOURCES[scope.dataset_mode])
    if scope.window.start and "window" not in skip:
        clauses.append(f"{alias}.start_timestamp >= CAST(? AS TIMESTAMP)")
        params.append(scope.window.start)
    if scope.window.end and "window" not in skip:
        clauses.append(f"{alias}.start_timestamp < CAST(? AS TIMESTAMP)")
        params.append(scope.window.end)
    for col, values in (("topic", scope.topics), ("product", scope.products), ("domain", scope.domains),
                        ("agent_id", scope.agents), ("sentiment", scope.sentiments), ("conversation_id", scope.conversation_ids)):
        if values and col not in skip:
            in_list(col, values)
    return " AND ".join(clauses), params
