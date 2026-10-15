"""FloPilot API entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .auth import seed_demo_identities
from .common import AppError, new_id
from .config import get_settings
from .db import init_db
from .harness.state import recover_interrupted_runs
from .services.workbooks import apply_retention
from .storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("flopilot")


def startup() -> None:
    init_db()
    seed_demo_identities()
    removed = get_storage().cleanup_temp_files()
    recovered = recover_interrupted_runs()
    purged = apply_retention()
    log.info("startup: temp files removed=%s, interrupted runs failed=%s, retention purged=%s", removed, recovered, purged)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FloPilot API", version="1.0.0", lifespan=lifespan,
                  description="FloPilot — Florina’s Excel Copilot. Independent product; not affiliated with Microsoft.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-Id"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        correlation = request.headers.get("x-correlation-id") or new_id("req")
        request.state.correlation_id = correlation[:64]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        response.headers["X-Correlation-Id"] = request.state.correlation_id
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        body = exc.to_dict() | {"correlation_id": getattr(request.state, "correlation_id", None)}
        return JSONResponse(body, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = [".".join(str(x) for x in e["loc"][1:]) for e in exc.errors()[:5]]
        return JSONResponse({"schema_version": "1.0", "code": "invalid_request", "message": "The request was not valid.",
                             "details": {"fields": fields}, "retryable": False,
                             "correlation_id": getattr(request.state, "correlation_id", None)}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error correlation=%s", getattr(request.state, "correlation_id", None))
        return JSONResponse({"schema_version": "1.0", "code": "internal_error", "message": "Something went wrong. Please try again.",
                             "details": {}, "retryable": True, "correlation_id": getattr(request.state, "correlation_id", None)},
                            status_code=500)

    app.include_router(router)
    return app


app = create_app()
