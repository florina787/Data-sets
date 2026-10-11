import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.db import Base

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True,
                   capture_output=True)
    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        cols = {c["name"] for c in insp.get_columns(name)}
        assert cols == {c.name for c in table.columns}, name
