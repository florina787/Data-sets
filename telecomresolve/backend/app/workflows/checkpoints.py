"""Persistent LangGraph checkpointer (SQLite by default, Postgres when the
database URL is Postgres)."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from ..config import get_settings

_lock = threading.Lock()
_saver = None
_conn = None


def get_checkpointer():
    global _saver, _conn
    with _lock:
        if _saver is not None:
            return _saver
        url = get_settings().checkpoint_url
        if url.startswith("sqlite"):
            from langgraph.checkpoint.sqlite import SqliteSaver

            path = url.split("sqlite:///", 1)[1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(path, check_same_thread=False)
            _saver = SqliteSaver(_conn)
            _saver.setup()
        else:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg import Connection
            from psycopg.rows import dict_row

            pg_url = url.replace("postgresql+psycopg://", "postgresql://")
            _conn = Connection.connect(pg_url, autocommit=True, prepare_threshold=0, row_factory=dict_row)
            _saver = PostgresSaver(_conn)
            _saver.setup()
        return _saver


def reset_checkpoints() -> None:
    """Drop all checkpoints (demo reset / tests)."""
    global _saver, _conn
    with _lock:
        url = get_settings().checkpoint_url
        if _conn is not None:
            if url.startswith("sqlite"):
                _conn.close()
            else:
                with _conn.cursor() as cur:
                    for t in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                        cur.execute(f"DELETE FROM {t}")  # noqa: S608 - fixed table names
                _conn.close()
        _saver = None
        _conn = None
        if url.startswith("sqlite"):
            path = Path(url.split("sqlite:///", 1)[1])
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(path) + suffix)
                if p.exists():
                    p.unlink()
