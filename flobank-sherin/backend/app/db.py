from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def init_engine(url: str | None = None):
    global _engine, _Session
    url = url or get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def _fk(dbapi_conn, _):  # pragma: no cover - sqlite only
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    else:
        _engine = create_engine(url, pool_pre_ping=True)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def engine():
    if _engine is None:
        init_engine()
    return _engine


def create_all():
    from app import models  # noqa: F401
    Base.metadata.create_all(engine())


def drop_all():
    from app import models  # noqa: F401
    Base.metadata.drop_all(engine())


@contextmanager
def session_scope():
    if _Session is None:
        init_engine()
    s: Session = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session():
    """FastAPI dependency."""
    with session_scope() as s:
        yield s
