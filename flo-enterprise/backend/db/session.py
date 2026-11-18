from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import ROOT, get_settings


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        (ROOT / "var").mkdir(exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # enforce referential integrity on SQLite too
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    import os
    # pool sized together with FLO_MAX_INFLIGHT; a short pool timeout makes saturation fail fast (503) instead of queueing
    return create_engine(url, pool_size=int(os.environ.get("FLO_DB_POOL_SIZE", "20")), max_overflow=int(os.environ.get("FLO_DB_MAX_OVERFLOW", "20")),
                         pool_timeout=float(os.environ.get("FLO_DB_POOL_TIMEOUT", "5")), pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_settings().database_url)


@lru_cache
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = _factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as s:
        yield s
