from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import tables  # noqa: F401 - registers the tables on the metadata


def make_engine(db_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA secure_delete=ON")  # deleted history is overwritten on disk
        cur.close()

    SQLModel.metadata.create_all(engine)
    return engine


def session(engine: Engine) -> Session:
    return Session(engine, expire_on_commit=False)
