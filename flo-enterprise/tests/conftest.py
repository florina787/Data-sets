import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLO_DATABASE_URL", f"sqlite:///{ROOT / 'var' / 'test.db'}")
os.environ.setdefault("FLO_CHECKPOINT_DB", str(ROOT / "var" / "test_checkpoints.sqlite"))
os.environ.setdefault("FLO_EXPORT_DIR", str(ROOT / "var" / "test_exports"))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def st():
    from backend.db.seed import seed
    from backend.db.session import session_scope
    from backend import runtime as R
    seed()
    with session_scope() as s:
        return R.store(s)


@pytest.fixture(scope="session")
def engine():
    from governance.policy import get_policy_engine
    return get_policy_engine()


@pytest.fixture(scope="session")
def P(st):
    from backend import runtime as R
    return {u: R.principal_for(st, u) for u in st.idx["user"]}


@pytest.fixture
def ctx_for(st):
    from backend import runtime as R

    def make(user, model=None, purpose=None):
        return R.run_context(st, R.principal_for(st, user), model=model, purpose=purpose)
    return make


def _unique(st):
    from collections import Counter
    n = Counter(c["full_name"] for c in st.tables["clients"])
    return {c["id"] for c in st.tables["clients"] if n[c["full_name"]] == 1}


@pytest.fixture(scope="session")
def a001_client(st):
    """An active, uniquely named client of advisor A-001 with a managed portfolio."""
    ports, uniq = {p["client_id"] for p in st.tables["portfolios"]}, _unique(st)
    return next(c["id"] for c in st.tables["clients"]
                if c["advisor_id"] == "A-001" and c["id"] in ports and c["status"] == "active" and c["id"] in uniq)


@pytest.fixture(scope="session")
def other_client(st):
    """A uniquely named t-flo client NOT assigned to A-001."""
    ports, uniq = {p["client_id"] for p in st.tables["portfolios"]}, _unique(st)
    return next(c["id"] for c in st.tables["clients"] if c["advisor_id"] == "A-002" and c["id"] in ports and c["id"] in uniq)


@pytest.fixture(scope="session")
def nw_client(st):
    return next(c["id"] for c in st.tables["clients"] if c["tenant_id"] == "t-nw")
