"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..agents.engine import Engine, ModelCatalog
from ..agents.interview import InterviewCoach
from ..agents.question_detection import QuestionDetector
from ..analytics.metrics import Metrics
from ..config import Settings
from ..llm.ollama import OllamaClient
from ..memory.db import make_engine
from ..memory.store import Store
from ..rag.embed import Embedder
from ..rag.index import VectorIndex
from ..rag.service import KnowledgeBase
from ..security.auth import TokenAuthMiddleware
from ..security.redact import install_log_redaction
from . import routes_chat, routes_knowledge, routes_practice, routes_system, ws_audio
from .state import AppState

log = logging.getLogger("veena")


class _LazyDimIndex(VectorIndex):
    """Defers loading the embedding model until the first document or search."""

    def __init__(self, root, embedder: Embedder):
        self.embedder = embedder
        super().__init__(root, dim=0)

    def _get(self, collection_id):
        if not self.dim:
            self.dim = self.embedder.dim
        return super()._get(collection_id)


def create_app(settings: Settings | None = None, *, llm=None, embedder=None, transcriber_factory=None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()
    install_log_redaction()

    db = make_engine(settings.db_path)
    store = Store(db)
    llm = llm or OllamaClient(settings.ollama_url)
    metrics = Metrics(store)
    catalog = ModelCatalog(llm)
    embedder = embedder or Embedder()
    kb = KnowledgeBase(db, embedder, _LazyDimIndex(settings.index_dir, embedder), settings.max_upload_mb * 2**20)
    state = AppState(
        settings=settings,
        store=store,
        llm=llm,
        metrics=metrics,
        catalog=catalog,
        kb=kb,
        engine=Engine(store, llm, kb, metrics, catalog),
        coach=InterviewCoach(db, llm),
        detector=QuestionDetector(llm=llm),
    )
    if transcriber_factory is not None:
        state.transcriber_factory = transcriber_factory

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s = store.get_settings()
        purged = store.purge_expired(int(s.get("retention_days") or 0))
        if purged:
            log.info("retention: removed %d expired sessions", purged)
        task = asyncio.create_task(_retention_loop(store))
        yield
        task.cancel()
        await llm.aclose()

    app = FastAPI(title="VEENA.AI local backend", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.veena = state
    # Order matters: CORS must wrap auth so preflight responses carry headers.
    app.add_middleware(TokenAuthMiddleware, token=settings.token, allowed_origins=settings.allowed_origins)
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o for o in settings.allowed_origins if o != "null"],
            allow_origin_regex="null" if "null" in settings.allowed_origins else None,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["authorization", "content-type"],
        )

    @app.get("/api/health")
    async def health():
        return {"ok": True, "service": "veena-ai", "version": __version__}

    app.include_router(routes_system.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_knowledge.router)
    app.include_router(routes_practice.router)
    app.include_router(ws_audio.router)
    return app


async def _retention_loop(store: Store) -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            store.purge_expired(int(store.get_settings().get("retention_days") or 0))
        except Exception:  # noqa: BLE001
            log.exception("retention purge failed")
