from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from app.api.routes import router
from app.config import get_settings
from app.errors import DomainError
from app.security.redaction import redact

log = logging.getLogger("beauty_ai")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.seed import init_db, seed
    init_db()
    seed()
    from app.evaluation import jobs
    recovered = jobs.recover()
    if recovered:
        log.info(json.dumps({"event": "evaluation_jobs_recovered", "runs": recovered}))
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Beauty AI Change Copilot API", version="0.1.0",
                  description="Independent beauty AI prototype — synthetic evaluation data", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Trace-Id"])

    @app.middleware("http")
    async def trace(request: Request, call_next):
        tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = tid
        t0 = time.perf_counter()
        resp = await call_next(request)
        resp.headers["X-Trace-Id"] = tid
        log.info(redact(json.dumps({"trace_id": tid, "method": request.method, "path": request.url.path, "status": resp.status_code,
                                    "ms": round((time.perf_counter() - t0) * 1000, 1)})))
        return resp

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(exc.to_dict(getattr(request.state, "trace_id", None)), status_code=exc.http_status)

    @app.exception_handler(StaleDataError)
    async def stale(request: Request, exc: StaleDataError):
        return JSONResponse({"error": {"category": "conflict", "code": "concurrent_modification",
                                       "message": "Record changed concurrently; reload and retry.",
                                       "trace_id": getattr(request.state, "trace_id", None)}}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": {"category": "validation", "code": "invalid_request", "message": "Request validation failed",
                                       "details": {"errors": json.loads(json.dumps(exc.errors(), default=str))},
                                       "trace_id": getattr(request.state, "trace_id", None)}}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled")
        return JSONResponse({"error": {"category": "computation", "code": "internal_error", "message": redact(str(exc))[:300],
                                       "trace_id": getattr(request.state, "trace_id", None)}}, status_code=500)

    app.include_router(router)
    return app


app = create_app()
