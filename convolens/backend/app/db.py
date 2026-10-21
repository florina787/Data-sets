from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker | None = None


def _configure(url: str):
    global _engine, _SessionLocal
    _engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def engine():
    if _engine is None:
        _configure(get_settings().db_url)
    return _engine


def reset_engine(url: str) -> None:
    """Used by tests to point the app at an isolated database."""
    _configure(url)


def init_db() -> None:
    from app.models import orm  # noqa: F401  (register tables)
    Base.metadata.create_all(engine())
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Additive migration for SQLite: add columns introduced after a database was created (no drops or renames)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine())
    with engine().begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                    ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine().dialect)}'
                    if isinstance(default, str):
                        ddl += f" DEFAULT '{default}'"
                    elif isinstance(default, list):
                        ddl += " DEFAULT '[]'"
                    conn.execute(text(ddl))


@contextmanager
def session_scope() -> Iterator[Session]:
    engine()
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    engine()
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.close()
