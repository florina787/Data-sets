import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="ff-test-"))
os.environ["FF_DATA_DIR"] = str(_TMP)
os.environ["FF_GENERATED_DIR"] = str(_TMP / "generated")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("OFFLINE_MODE", "true")
os.environ["FF_SESSION_SECRET"] = "test-secret"  # noqa: S105 - test-only value

from app.core.config import reset_settings  # noqa: E402

reset_settings()

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import load_actor  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.generator import reset_database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    reset_database()
    yield


@pytest.fixture(scope="session")
def client(seeded):
    with TestClient(app) as c:
        yield c


def login(client, user_id):
    r = client.post("/api/auth/login", json={"user_id": user_id})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["data"]["token"]}


@pytest.fixture
def planner(client):
    return login(client, "planner.marco")


@pytest.fixture
def actor():
    return load_actor
