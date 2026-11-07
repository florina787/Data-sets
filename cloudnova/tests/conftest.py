import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session", autouse=True)
def built_data():
    from app.pipeline.build import build
    return build(quiet=True)


@pytest.fixture(autouse=True)
def no_llm():
    """Unit tests never depend on the local model: default to an offline provider."""
    from app.llm.provider import set_provider_override

    class Offline:
        name, model = "qwen", "offline"

        def complete(self, *a, **k):
            from app.errors import AppError
            raise AppError("llm_unavailable", "offline in tests", 503)

        def ping(self):
            return {"reachable": False, "models": []}

    set_provider_override(Offline())
    yield
    set_provider_override(None)
