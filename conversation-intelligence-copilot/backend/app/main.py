"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, chat, conversations, governance, health, prompts, retrieval, sessions, telemetry
from app.config import get_settings
from app.startup import startup_report

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("cic")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    if s.enable_langsmith:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
    report = startup_report(refresh=True)
    for c in report["checks"]:
        log.info("startup %s: %s (%s)", c["check"], c["status"], c["detail"])
    # Warm everything a first question would otherwise pay for, in the background: the retrieval and intent
    # indexes (embedding model, FAISS, LSA) and, when the local model is the provider, the model weights.
    def _warm() -> None:
        try:
            from app.agents.semantic_intent import get_semantic_index
            from app.retrieval.index import get_retriever
            from app.schemas.analysis import Scope

            get_semantic_index()
            get_retriever().search("customer was charged twice", Scope(), k=1)
            log.info("retrieval and intent indexes warm")
        except Exception as e:  # noqa: BLE001 - retrieval reports its own unavailability per request
            log.warning("index preload failed: %s", e)
        if s.local_preload and s.resolved_llm_provider == "local":
            try:
                from app.llm.gemini_client import get_llm

                _ = get_llm().llama  # type: ignore[attr-defined]
                log.info("local model warm")
            except Exception as e:  # noqa: BLE001 - the app works without a model
                log.warning("local model preload failed: %s", e)

    threading.Thread(target=_warm, name="preload", daemon=True).start()
    yield


app = FastAPI(title="Conversation Intelligence Copilot API", version="1.0.0", lifespan=lifespan,
              description="Agentic contact-centre analytics: LangGraph orchestration over deterministic DuckDB analytics, FAISS retrieval and Gemini.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(FileNotFoundError)
async def missing_data(_: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


for r in (health, chat, analytics, conversations, retrieval, sessions, prompts, telemetry, governance):
    app.include_router(r.router)
