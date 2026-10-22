"""FLO Enterprise API."""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as SATimeoutError

from backend.api import routes_ai, routes_compliance, routes_conversation, routes_core, routes_exec, routes_invest, routes_wealth
from backend.config import get_settings
from observability.telemetry import HTTP_LATENCY

log = logging.getLogger("flo.api")
MAX_BODY = 6 * 1024 * 1024
MAX_INFLIGHT = int(os.environ.get("FLO_MAX_INFLIGHT", "32"))  # per process; keep below DB pool capacity
_inflight = 0
_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("FLO_AUTO_SEED", "1") == "1":
        from backend.db.seed import seed
        seed()
    stop = None
    if os.environ.get("FLO_INPROCESS_WORKER", "1") == "1":
        from backend.worker import start_in_process
        stop = start_in_process()
    if os.environ.get("FLO_OTEL_ENABLED") == "1":  # optional OpenTelemetry auto-instrumentation
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except ImportError:
            log.warning("OpenTelemetry requested but not installed")
    yield
    if stop:
        stop.set()


app = FastAPI(title="FLO Enterprise API", version="1.0.0", lifespan=lifespan,
              description="FLO - Financial Leadership, Operations & Wealth Intelligence. Independent architecture demonstration; synthetic data only.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")], allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def guard(request: Request, call_next):
    global _inflight
    if int(request.headers.get("content-length") or 0) > MAX_BODY:
        return JSONResponse({"detail": {"code": "PAYLOAD-TOO-LARGE"}}, status_code=413)
    with _lock:
        if _inflight >= MAX_INFLIGHT and request.url.path not in ("/healthz", "/readyz", "/metrics"):
            return JSONResponse({"detail": {"code": "LOAD-SHED", "message": "server busy"}}, status_code=503, headers={"Retry-After": "2"})
        _inflight += 1
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    status = 500
    try:
        resp = await call_next(request)
        status = resp.status_code
    finally:
        with _lock:
            _inflight -= 1
        route = request.scope.get("route")
        HTTP_LATENCY.labels(getattr(route, "path", "unmatched"), request.method, str(status)).observe(time.perf_counter() - t0)
    resp.headers.update({"X-Request-ID": rid, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                         "Cache-Control": "no-store", "X-FLO-Data": "synthetic"})
    return resp


@app.exception_handler(SATimeoutError)
async def pool_exhausted(request: Request, exc: SATimeoutError):
    # graceful degradation: database saturation is reported as retryable backpressure, never as a 500
    return JSONResponse({"detail": {"code": "BACKPRESSURE", "message": "database capacity exhausted; retry shortly"}}, status_code=503,
                        headers={"Retry-After": "2"})


for r in (routes_core, routes_exec, routes_invest, routes_wealth, routes_ai, routes_compliance, routes_conversation):
    app.include_router(r.router)
