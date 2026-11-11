"""Florome FastAPI application."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from florome import __version__
from florome.api.v1 import router
from florome.config import Settings, get_settings
from florome.context import AppContext
from florome.models import init_engine, session_factory

log = logging.getLogger("florome")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        out.update(getattr(record, "fields", {}))
        return json.dumps(out)


def _configure_logging() -> None:
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JsonFormatter())
        log.addHandler(h)
        log.setLevel(logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    ctx = AppContext(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN202
        init_engine(settings.database_url)
        if settings.default_mode == "demo":
            from florome.demo.seed import DEMO_TENANTS, seed_demo

            db = session_factory()()
            try:
                for tid in DEMO_TENANTS:  # sandbox state is in-memory, so demo tenants are re-seeded on start
                    await seed_demo(db, ctx, tid)
                db.commit()
            finally:
                db.close()
        yield

    _configure_logging()
    app = FastAPI(title="Florome API", version=__version__, lifespan=lifespan,
                  description="One Intelligence. Every Cloud. From Root Cause to Resolution. "
                              "Demo tenants are synthetic; see /api/v1/platforms for the real status of every integration.")
    app.state.ctx = ctx
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def request_log(request: Request, call_next):  # noqa: ANN001, ANN202
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["x-request-id"] = rid
        log.info("request", extra={"fields": {"request_id": rid, "method": request.method, "path": request.url.path,
                                              "status": response.status_code, "duration_ms": ms}})
        return response

    app.include_router(router)
    return app


app = create_app()
