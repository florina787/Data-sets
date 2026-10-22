"""Test configuration: an isolated fixture dataset, database, index and stores in a temp dir.

No test touches the real data/ directory or the network. Model calls use scripted fakes.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.fixtures.build_fixture import write_fixture


def _clear_caches() -> None:
    from app.agents import graph
    from app.analytics import db
    from app.config import get_settings
    from app.governance import human_review
    from app.llm import gemini_client
    from app.memory import store as memory
    from app.observability import store as telemetry
    from app.retrieval import index

    db.reset_db()
    for fn in (get_settings, memory.get_memory, telemetry.get_telemetry, index.get_retriever, graph.get_graph, human_review.get_review_store):
        fn.cache_clear()
    gemini_client.set_llm(None)


@pytest.fixture(scope="session")
def env(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("cic")
    raw = write_fixture(root / "raw" / "fixture.csv")
    os.environ.update({
        "RAW_DATASET_PATH": str(raw),
        "SYNTHETIC_DATASET_PATH": str(root / "synthetic" / "none.csv"),
        "DATABASE_PATH": str(root / "processed" / "analytics.duckdb"),
        "MEMORY_DATABASE_PATH": str(root / "processed" / "memory.sqlite"),
        "CHECKPOINT_DATABASE_PATH": str(root / "processed" / "checkpoints.sqlite"),
        "FAISS_INDEX_PATH": str(root / "indexes" / "conversations.faiss"),
        "MANIFESTS_DIR": str(root / "manifests"),
        "LLM_CACHE_PATH": str(root / "processed" / "llm_cache.sqlite"),
        "LABELS_DATABASE_PATH": str(root / "processed" / "labels.sqlite"),
        "LLM_ENABLED": "false",
        "GEMINI_API_KEY": "",
        "EMBEDDING_BACKEND": "lsa",
        "MIN_AGENT_CONVERSATIONS": "3",
        "ENABLE_LANGSMITH": "false",
    })
    _clear_caches()
    from app.data.pipeline import run
    from app.retrieval.index import build_index

    run()
    _clear_caches()
    build_index()
    _clear_caches()
    return root


@pytest.fixture()
def db(env):
    from app.analytics.db import get_db

    return get_db()


@pytest.fixture(autouse=True)
def _reset_llm():
    yield
    from app.llm import gemini_client

    gemini_client.set_llm(None)
