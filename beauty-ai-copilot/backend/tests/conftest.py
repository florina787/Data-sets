"""Test isolation: every test gets its own SQLite database (copied from a seeded template) and its
own copy of the data directory, so tampering tests cannot affect each other."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE: dict = {}


def _reset_caches():
    from app.agents import llm
    from app.config import reset_settings
    from app.db import reset_engine
    from app.retrieval import knowledge
    from app.services import fixtures
    from app.workflows import graph
    reset_settings()
    reset_engine()
    fixtures.clear_caches()
    knowledge._kb.cache_clear()
    llm.reset_provider()
    graph.FAULTS.clear()


def _configure(monkeypatch, db_path: Path, data_dir: Path, storage: Path, **extra):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("EVAL_EXECUTION", "inline")
    monkeypatch.setenv("APP_ENV", "demo")
    monkeypatch.setenv("LLM_MODE", "deterministic")
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    _reset_caches()


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("template")
    mp = pytest.MonkeyPatch()
    _configure(mp, d / "t.db", ROOT / "data", d / "storage")
    from app.seed import init_db, seed
    init_db()
    seed()
    from app.db import reset_engine
    reset_engine()
    mp.undo()
    return d / "t.db"


@pytest.fixture
def env(tmp_path, monkeypatch, template_db):
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    db = tmp_path / "test.db"
    shutil.copy(template_db, db)
    _configure(monkeypatch, db, data, tmp_path / "storage")
    yield {"data": data, "db": db, "tmp": tmp_path, "monkeypatch": monkeypatch}
    _reset_caches()


@pytest.fixture
def client(env):
    from fastapi.testclient import TestClient
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def H(user: str, **extra) -> dict:
    return {"X-Demo-User": user, **extra}


class Journey:
    """Drives the seeded BR-101 journey through the HTTP API."""

    def __init__(self, c):
        self.c = c

    def ok(self, r, code=None):
        assert r.status_code < 300 if code is None else r.status_code == code, r.text
        return r.json()

    def get(self, user="u-po"):
        return self.ok(self.c.get("/api/changes/BR-101", headers=H(user)))

    def clarify_all(self):
        for cl in self.get()["clarifications"]:
            self.ok(self.c.post("/api/changes/BR-101/clarifications", headers=H("u-po"), json={"key": cl["key"], "use_suggested": True}))

    def approve_requirements(self):
        self.clarify_all()
        self.ok(self.c.post("/api/changes/BR-101/requirements/approve", headers=H("u-po")))

    def to_development(self):
        self.approve_requirements()
        self.ok(self.c.post("/api/changes/BR-101/investigate", headers=H("u-ml-eng")))
        self.ok(self.c.post("/api/changes/BR-101/impact/accept", headers=H("u-po")))

    def candidate(self, model):
        return self.ok(self.c.post("/api/changes/BR-101/candidates", headers=H("u-cv-eng"), json={"model_id": model}))

    def evaluate(self):
        run = self.ok(self.c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")), 202)
        return self.ok(self.c.get(f"/api/evaluations/{run['id']}", headers=H("u-qa")))

    def to_review_required(self):
        self.to_development()
        self.candidate("shade-matcher-v2.4.0-rc2")
        self.ok(self.c.post("/api/changes/BR-101/reviews", headers=H("u-qa"), json={"kind": "code", "decision": "APPROVE"}))
        return self.evaluate()

    def reviews(self):
        for u, k in (("u-domain", "domain"), ("u-privacy", "privacy")):
            self.ok(self.c.post("/api/changes/BR-101/reviews", headers=H(u), json={"kind": k, "decision": "APPROVE"}))

    def to_release_approved(self):
        self.to_review_required()
        self.reviews()
        return self.ok(self.c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"), json={"decision": "APPROVED"}), 201)

    def release(self, key="k-1"):
        return self.c.post("/api/changes/BR-101/releases", headers=H("u-release", **{"Idempotency-Key": key}), json={})


@pytest.fixture
def journey(client):
    return Journey(client)
