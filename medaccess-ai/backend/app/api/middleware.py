"""Request middleware: request IDs, trace correlation, rate limiting, metrics,
security headers and consistent error envelopes."""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings
from app.telemetry import metrics as tm
from app.telemetry.tracing import current_trace_id, request_id_var, tracer


class SlidingWindowLimiter:
    """In-process sliding-window limiter (per client + route group). Use Redis for multi-replica deployments."""

    def __init__(self) -> None:
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> tuple[bool, int]:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False, int(window - (now - q[0])) + 1
            q.append(now)
            return True, 0


LIMITER = SlidingWindowLimiter()


def error_body(code: str, message: str, request_id: str | None, details=None) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id, "details": details}}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid = rid[:64]
        token = request_id_var.set(rid)
        route = request.url.path
        group = "/".join(route.split("/")[:4])
        client = request.client.host if request.client else "unknown"
        limit = get_settings().rate_limit_per_minute
        if route.startswith("/api/") and not route.endswith("/health"):
            ok, retry = LIMITER.allow(f"{client}:{group}", limit)
            if not ok:
                request_id_var.reset(token)
                return JSONResponse(error_body("RATE_LIMITED", "Too many requests", rid), status_code=429,
                                    headers={"Retry-After": str(retry), "X-Request-ID": rid})
        t0 = time.perf_counter()
        with tracer().start_as_current_span(f"HTTP {request.method} {group}") as span:
            span.set_attribute("http.request_id", rid)
            try:
                resp = await call_next(request)
            finally:
                request_id_var.reset(token)
            trace_id = current_trace_id()
        dur = time.perf_counter() - t0
        tm.HTTP_REQUESTS.labels(route=group, method=request.method, status=str(resp.status_code)).inc()
        tm.HTTP_LATENCY.labels(route=group).observe(dur)
        if route.startswith("/api/"):
            tm.STORE.add("http_latency_ms", dur * 1000, {"route": group})
            tm.STORE.add("http_error", 1 if resp.status_code >= 500 else 0, {"route": group})
        resp.headers["X-Request-ID"] = rid
        if trace_id:
            resp.headers["X-Trace-ID"] = trace_id
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exc(request: Request, exc: HTTPException):
        code = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT",
                422: "VALIDATION_ERROR", 429: "RATE_LIMITED"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(error_body(code, str(exc.detail), request.headers.get("x-request-id") or
                                       request_id_var.get()), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def val_exc(request: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()][:10]
        return JSONResponse(error_body("VALIDATION_ERROR", "Request validation failed", request_id_var.get(), details),
                            status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # pragma: no cover - safety net
        return JSONResponse(error_body("INTERNAL_ERROR", "An internal error occurred", request_id_var.get()),
                            status_code=500)
