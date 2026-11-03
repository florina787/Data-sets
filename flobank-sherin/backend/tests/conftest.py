"""Test setup: PostgreSQL when TEST_DATABASE_URL is set (CI and local), otherwise a temporary SQLite file.

The synthetic environment is seeded once per session at reduced volume. No network and no LLM are used.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="sherin-test-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["LLM_ENABLED"] = "false"
os.environ["APP_MODE"] = "test"
os.environ["CHECKPOINT_PATH"] = ":memory:"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import drop_all, init_engine, session_scope  # noqa: E402

SCALE = float(os.environ.get("TEST_SEED_SCALE", "0.3"))


@pytest.fixture(scope="session", autouse=True)
def seeded():
    init_engine()
    drop_all()
    from app.data.seed import seed
    counts = seed(scale=SCALE)
    from app.agents import harness as H
    H.set_harness(H.Harness(":memory:", sync_mode=True))
    yield counts


@pytest.fixture()
def db():
    with session_scope() as s:
        yield s


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app
    with TestClient(app) as c:
        yield c


def hdr(role="SHERIN_MANAGER", user="exec.demo"):
    return {"X-Role": role, "X-User": user}
