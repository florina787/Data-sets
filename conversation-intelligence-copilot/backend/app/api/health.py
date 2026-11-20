"""Health and startup validation."""

from __future__ import annotations

from fastapi import APIRouter

from app.startup import startup_report

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return startup_report(refresh=True)
