"""MedAccess AI - FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from app.agents.registry import register_all
from app.api.middleware import RequestContextMiddleware, install_error_handlers
from app.api.routes import engineering, patient
from app.config.settings import get_settings, validate_settings
from app.copilot import llm
from app.database.session import DEMO_USERS, get_engine, init_db
from app.schemas.domain import SERVICE_LABELS
from app.security.auth import issue_token
from app.services.gazetteer import CITY_CENTROIDS, SUPPORTED_RADII_KM
from app.telemetry.tracing import setup_tracing
from app.telemetry.tracing import status as tracing_status
from app.tools.patient_tools import register as register_tools

log = logging.getLogger("medaccess")
STARTUP_WARNINGS: list[str] = []
VERSION = "0.9.0-prototype"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    STARTUP_WARNINGS[:] = validate_settings(s)
    for w in STARTUP_WARNINGS:
        log.warning(w)
    setup_tracing()
    register_all()
    register_tools()
    init_db(seed=True)
    yield


app = FastAPI(
    title="MedAccess AI API",
    version=VERSION,
    description="Healthcare access intelligence + AI-SDLC command center. DEMO MODE uses synthetic, fictional "
                "data only. Christina is a virtual AI assistant, not a licensed physician.",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type",
                                                                                  "X-Request-ID"])
install_error_handlers(app)
app.include_router(patient.router)
app.include_router(engineering.router)


@app.get("/api/v1/health", tags=["health"])
def health():
    db_ok = True
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    s = get_settings()
    return {"status": "ok" if db_ok else "degraded", "version": VERSION, "environment": s.environment,
            "data_mode": s.data_mode, "database": "ok" if db_ok else "unavailable",
            "llm_configured": llm.available(), "tracing": tracing_status(), "warnings": STARTUP_WARNINGS,
            "time": datetime.now(UTC).isoformat()}


class LoginIn(BaseModel):
    user_id: str


@app.post("/api/v1/auth/demo-login", tags=["auth"])
def demo_login(body: LoginIn):
    return issue_token(body.user_id)


@app.get("/api/v1/auth/demo-users", tags=["auth"])
def demo_users():
    if get_settings().is_production_like:
        return {"items": []}
    return {"items": [{"id": u, "name": n, "role": r} for u, _, n, r in DEMO_USERS]}


@app.get("/api/v1/config/public", tags=["config"])
def public_config():
    """Non-secret configuration for the frontend. Never contains keys or credentials."""
    s = get_settings()
    return {"app_name": s.app_name, "environment": s.environment, "data_mode": s.data_mode,
            "demo_banner": "DEMONSTRATION DATA - NOT LIVE APPOINTMENT AVAILABILITY" if s.data_mode == "SYNTHETIC"
            else None,
            "services": [{"code": k.value, "label": v} for k, v in SERVICE_LABELS.items()],
            "radii_km": list(SUPPORTED_RADII_KM), "cities": sorted(c.title() for c in CITY_CENTROIDS),
            "christina_disclaimer": "Christina is a virtual AI assistant, not a licensed physician.",
            "voice_disclosure": "Voice uses your browser's speech features. Some browsers send audio to their "
                                "vendor's cloud speech service. Voice is off by default and needs your permission.",
            "scenarios": ["provider_outage", "provider_flaky"]}
