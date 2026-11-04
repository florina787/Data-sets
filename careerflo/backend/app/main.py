"""Career_flo AI — FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .billing.metering import MeteringError, release_stale
from .careers.context import NotFound
from .config import get_settings
from .db import Base, SessionLocal, get_engine
from .llm.qwen import assert_qwen
from .mcp_gateway import ToolDenied, ToolFailed
from .routers import account, admin, auth, billing, careers, chat, crm, jobs, ops, resumes
from .seed import seed_reference

log = logging.getLogger("careerflo")


def init_db() -> None:
    engine = get_engine()
    # SQLite (dev/tests) creates tables directly; PostgreSQL/Supabase uses Alembic migrations.
    if engine.dialect.name == "sqlite":
        from . import models  # noqa: F401

        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        release_stale(db, get_settings().reservation_stale_minutes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.llm_provider in ("ollama", "llamacpp"):
        assert_qwen(s.llm_model)
    if s.environment == "production" and s.auth_mode == "local" and "dev-only" in s.local_jwt_secret:
        raise RuntimeError("Set LOCAL_JWT_SECRET (or use AUTH_MODE=supabase) in production")
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Career_flo AI API", version="0.1.0", lifespan=lifespan,
                  description="Your Intelligent AI Career Partner — Qwen-powered, MCP-enabled, LangGraph-orchestrated.")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        from .security.ratelimit import client_ip, limiter

        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/webhooks"):
            try:
                limiter.check(f"ip:{client_ip(request)}", s.rate_limit_per_minute * 5)
            except Exception:
                return JSONResponse({"detail": "Too many requests"}, status_code=429, headers={"Retry-After": "30"})
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if s.environment == "production":
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    @app.exception_handler(MeteringError)
    async def _metering(_: Request, exc: MeteringError):
        return JSONResponse({"detail": {"code": exc.code, "message": exc.message, **exc.detail}}, status_code=exc.status_code)

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(ToolDenied)
    async def _denied(_: Request, exc: ToolDenied):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(ToolFailed)
    async def _failed(_: Request, exc: ToolFailed):
        msg = str(exc)
        code = 404 if "not found" in msg.lower() or "no resume" in msg.lower() else 502
        return JSONResponse({"detail": msg}, status_code=code)

    for r in (auth.router, account.router, jobs.router, resumes.router, careers.router, crm.router, chat.router, ops.router,
              billing.router, billing.webhook_router, admin.router):
        app.include_router(r)
    return app


app = create_app()
