"""FastAPI application entry point."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import DISCLAIMER, router
from .config import get_settings
from .connectors.base import ConnectorError
from .observability.audit import request_id_var
from .observability.redaction import redact_text
from .workflows.service import WorkflowError, recover_incomplete_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        return True


for h in logging.getLogger().handlers:
    h.addFilter(RedactingFilter())

log = logging.getLogger("telecomresolve")


def create_app(run_recovery: bool = True) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if run_recovery:
            try:
                resumed = recover_incomplete_jobs()
                if resumed:
                    log.info("resumed interrupted investigations: %s", resumed)
            except Exception:  # noqa: BLE001 - startup must not die on recovery
                log.exception("checkpoint recovery failed")
        yield

    app = FastAPI(title="TelecomResolve Copilot API", version="0.1.0", lifespan=lifespan,
                  description=f"{DISCLAIMER}. Evidence-backed investigation workflow prototype.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type",
                                                                     "Idempotency-Key", "X-Request-ID"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
        rid = rid[:64]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Data-Notice"] = "synthetic"
        return response

    @app.exception_handler(WorkflowError)
    async def workflow_error(request: Request, exc: WorkflowError):
        return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, "message": exc.message,
                                                                        **exc.extra}})

    @app.exception_handler(ConnectorError)
    async def connector_error(request: Request, exc: ConnectorError):
        return JSONResponse(status_code=503, content={"detail": {"code": exc.code, "message": str(exc)}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": {"code": "VALIDATION_ERROR",
                                                                 "errors": exc.errors()}})

    app.include_router(router)

    return app


app = create_app()
