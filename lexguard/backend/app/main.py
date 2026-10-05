"""LexGuard Copilot API - FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api
from app.config import get_settings
from app.models.db import init_db
from app.observability.logging import configure_logging, log_event
from app.rag.retriever import get_index
from app.services.data_store import get_store

MAX_BODY_BYTES = 10 * 1024 * 1024


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    init_db(settings.database_url)
    get_store()
    get_index()
    app = FastAPI(title="LexGuard Copilot API", version="1.0.0",
                  description="Govern AI. Protect matters. Prove value. Synthetic demo data only.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-LexGuard-User"])

    @app.middleware("http")
    async def observability(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        log_event("http_request", http_id=rid, method=request.method, path=request.url.path, status=response.status_code,
                  user=request.headers.get("X-LexGuard-User"), latency_ms=round((time.perf_counter() - t0) * 1000, 1))
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "Invalid request.",
                                                      "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("lexguard").exception("unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal error. The incident has been logged."})

    app.include_router(api)
    return app


app = create_app()
