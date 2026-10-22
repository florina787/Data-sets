"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
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
    yield


app = FastAPI(title="Conversation Intelligence Copilot API", version="1.0.0", lifespan=lifespan,
              description="Agentic contact-centre analytics: LangGraph orchestration over deterministic DuckDB analytics, FAISS retrieval and Gemini.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(FileNotFoundError)
async def missing_data(_: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


for r in (health, chat, analytics, conversations, retrieval, sessions, prompts, telemetry, governance):
    app.include_router(r.router)
