"""ConvoLens AI backend entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_data, routes_flo, routes_review
from app.config import get_settings
from app.db import init_db
from app.ingestion.bootstrap import ensure_demo_datasets
from app.ingestion.jobs import get_jobs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("convolens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    n = get_jobs().recover()
    if n:
        log.info("Marked %d interrupted job(s)", n)
    ids = ensure_demo_datasets()
    log.info("Demonstration datasets ready: %s", ids)
    yield


app = FastAPI(title="ConvoLens AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["GET", "POST", "PUT", "PATCH"],
                   allow_headers=["Content-Type", "X-Flo-Session", "X-Flo-Token"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {type(exc).__name__}. See server logs."})


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(routes_data.router)
app.include_router(routes_flo.router)
app.include_router(routes_review.router)
