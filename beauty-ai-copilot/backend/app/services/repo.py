"""Tenant-scoped data access. Every read of a tenant-owned record goes through these helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.models.orm import ChangeRequest, EvaluationRun, Release


def get_change(db: Session, tenant_id: str, change_id: str, *, for_update: bool = False) -> ChangeRequest:
    q = select(ChangeRequest).where(ChangeRequest.id == change_id, ChangeRequest.tenant_id == tenant_id)
    if for_update:
        q = q.with_for_update()
    ch = db.execute(q).scalar_one_or_none()
    if ch is None:  # same response whether it does not exist or belongs to another tenant
        raise NotFound("change_not_found", f"Change {change_id} not found")
    return ch


def get_run(db: Session, tenant_id: str, run_id: str) -> EvaluationRun:
    run = db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id, EvaluationRun.tenant_id == tenant_id)).scalar_one_or_none()
    if run is None:
        raise NotFound("evaluation_not_found", f"Evaluation run {run_id} not found")
    return run


def get_release(db: Session, tenant_id: str, release_id: str) -> Release:
    rel = db.execute(select(Release).where(Release.id == release_id, Release.tenant_id == tenant_id)).scalar_one_or_none()
    if rel is None:
        raise NotFound("release_not_found", f"Release {release_id} not found")
    return rel
