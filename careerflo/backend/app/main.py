"""Career_flo AI — FastAPI application."""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .billing.metering import MeteringError, release_stale
from .careers.context import NotFound
from .config import get_settings
from .db import Base, SessionLocal, get_engine
from .llm.qwen import assert_qwen
from .mcp_gateway import ToolDenied, ToolFailed
from .opsmetrics import metrics, route_key
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
    if s.llm_provider in ("ollama", "llamacpp", "hf"):
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
        t0 = time.perf_counter()
        try:
            resp = await call_next(request)
        except Exception:
            if request.url.path.startswith("/api/"):
                metrics.record(route_key(request.url.path), 500, (time.perf_counter() - t0) * 1000, None)
            raise
        if request.url.path.startswith("/api/"):
            uid = getattr(request.state, "user_id", None)
            metrics.record(route_key(request.url.path), resp.status_code, (time.perf_counter() - t0) * 1000, str(uid) if uid else None)
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
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app from the same origin (single-container deployments such as a HF Docker Space).

    Set FRONTEND_DIST to the Vite `dist` folder. /api/* is never shadowed; unknown non-API paths fall back to
    index.html so client-side routes (/app/jobs, /pricing, ...) work on reload.
    """
    dist = os.environ.get("FRONTEND_DIST")
    if not dist or not (Path(dist) / "index.html").is_file():
        return
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    root = Path(dist).resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


app = create_app()
