"""ClaimForge Copilot — FastAPI application.

Run:  uvicorn app.api.main:app --reload --port 8000
SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import claimiq, claims, sdlc
from app.claims.rulesets import RULESETS
from app.config.settings import SYNTHETIC_BANNER
from app.observability.audit import log
from app.requirements.analyzer import (
    DEMO_CLARIFICATIONS,
    DEMO_REQUIREMENT,
    DEMO_REQUIREMENT_EXPLICIT,
    RequirementNotReady,
)
from app.security.sanitizer import UploadValidationError
from app.services.platform import get_platform
from app.tools.registry import ToolError
from app.utils.serialize import to_jsonable

MAX_BODY_BYTES = 2_500_000

app = FastAPI(
    title="ClaimForge Copilot API",
    description="Agentic SDLC & Production Intelligence for Health Insurance. " + SYNTHETIC_BANNER,
    version="1.0.0",
)


@app.middleware("http")
async def guard(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Synthetic-Data"] = "true"
    return response


@app.exception_handler(RequirementNotReady)
async def _not_ready(_: Request, exc: RequirementNotReady):
    return JSONResponse(status_code=409, content={"detail": f"Requirement needs human clarification: {exc}"})


@app.exception_handler(UploadValidationError)
async def _upload(_: Request, exc: UploadValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ToolError)
async def _tool(_: Request, exc: ToolError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def _value(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)[:300]})


@app.exception_handler(KeyError)
async def _key(_: Request, exc: KeyError):
    return JSONResponse(status_code=404, content={"detail": f"not found: {str(exc)[:80]}"})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.error(f"unhandled error: {type(exc).__name__}")  # no payloads / secrets logged
    return JSONResponse(status_code=500, content={"detail": "internal error"})


@app.get("/health", tags=["system"])
def health() -> dict:
    p = get_platform()
    return {"status": "ok", "service": "claimforge-copilot", "notice": SYNTHETIC_BANNER,
            "settings": p.settings.public_dict(), "llm_mode": p.llm.mode, "paid_llm_calls": p.llm.paid_calls}


@app.get("/use-cases", tags=["system"])
def use_cases() -> dict:
    ucs = get_platform().use_cases()
    counts: dict[str, int] = {}
    for u in ucs:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    return {"use_cases": ucs, "counts": counts}


@app.get("/scenarios", tags=["system"])
def scenarios() -> dict:
    return {"scenarios": [
        {"id": "V1-PHYSIO-BR391", "company": "NorthStar Health Benefits (fictional)",
         "requirement": DEMO_REQUIREMENT, "clarifications": DEMO_CLARIFICATIONS,
         "explicit_variant": DEMO_REQUIREMENT_EXPLICIT,
         "current_policy": "Physiotherapy 80%, $750 annual max, no authorization for first 10 completed visits",
         "controlled_defect": "Release 2.4 build counts COMPLETED + CANCELLED visits toward the threshold",
         "rulesets": sorted(RULESETS)}],
        "notice": SYNTHETIC_BANNER}


@app.get("/metrics", tags=["system"])
def metrics() -> dict:
    return to_jsonable(get_platform().system_metrics())


app.include_router(sdlc.router)
app.include_router(claims.router)
app.include_router(claimiq.router)
