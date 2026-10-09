import os
import sys
import tempfile
from pathlib import Path

# Configure a clean, isolated demo environment BEFORE the app is imported.
_TMP = tempfile.mkdtemp(prefix="lexguard-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DEMO_MODE"] = "true"
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.data_store import get_store  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def store():
    return get_store()


def hdr(user_id: str) -> dict:
    return {"X-LexGuard-User": user_id}


@pytest.fixture
def as_user():
    return hdr
