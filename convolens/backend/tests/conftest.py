import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="convolens-test-"))
os.environ["DATA_DIR"] = str(_TMP / "var")
os.environ["IMPORT_ROOT"] = str(_TMP / "imports")
os.environ["MODEL_PROVIDER"] = "none"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["EMBEDDINGS_ENABLED"] = "false"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("LANGSMITH_API_KEY", None)

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db import init_db  # noqa: E402
from app.ingestion.bootstrap import ensure_demo_datasets  # noqa: E402
from app.ingestion.importer import run_import  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def demo_ids():
    init_db()
    return ensure_demo_datasets()


@pytest.fixture(scope="session")
def imported_id(demo_ids):
    """A non-synthetic dataset (small CSV in the Kaggle schema) to exercise connected-mode code paths."""
    return run_import(FIXTURES / "mini_twcs.csv", kind="kaggle_twcs", name="mini", source_label="test fixture", synthetic=False)


@pytest.fixture()
def runner(tmp_path):
    from app.graph.runner import reset_runner
    return reset_runner(tmp_path / "ckpt.db")


@pytest.fixture()
def client(demo_ids):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session(client):
    r = client.post("/api/flo/sessions").json()
    return {"X-Flo-Session": r["session_id"], "X-Flo-Token": r["session_token"]}
