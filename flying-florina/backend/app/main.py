"""Flying_Florina FastAPI application."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_core, routes_trust
from app.core import egress
from app.core.config import APP_VERSION, get_settings
from app.core.util import redact
from app.seed.generator import ensure_seeded

log = logging.getLogger("flying_florina")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.offline_mode:
        egress.install()
    ensure_seeded()
    from app.services.tools import registry

    registry()  # fail fast if a tool does not match its pin
    log.info("Flying_Florina %s ready (demo=%s offline=%s)", APP_VERSION, settings.demo_mode, settings.offline_mode)
    yield


app = FastAPI(
    title="Flying_Florina API",
    version=APP_VERSION,
    description="Independent concept demo | Not affiliated with or endorsed by IFS. Synthetic data only.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
    request.state.request_id = rid
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    for k, v in SECURITY_HEADERS.items():
        if k == "Content-Security-Policy" and request.url.path in ("/docs", "/redoc"):
            continue
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    log.info("rid=%s %s %s -> %s %.1fms", rid, request.method, redact(request.url.path), response.status_code, (time.perf_counter() - started) * 1000)
    return response


def _error(request: Request, status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message, "details": details,
                                                     "request_id": getattr(request.state, "request_id", None)})


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
    return _error(request, exc.status_code, d.get("code", "http_error"), d.get("message", ""), d.get("details"))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return _error(request, 422, "validation_error", "Request failed validation.",
                  [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error rid=%s", getattr(request.state, "request_id", None))
    return _error(request, 500, "internal_error", "Unexpected error. See server log with this request_id.")


app.include_router(routes_core.router)
app.include_router(routes_trust.router)
