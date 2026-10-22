"""Governance status, audit log, model controls and blind human review."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.analytics.db import get_db
from app.config import get_settings
from app.governance.human_review import LABELS, get_review_store, metrics, sample
from app.governance.pii import PII_PATTERNS
from app.llm.gemini_client import get_llm
from app.observability.store import get_telemetry

router = APIRouter(tags=["governance"])


@router.get("/api/governance/status")
def status() -> dict:
    s = get_settings()
    db = get_db()
    pii = db.query("SELECT SUM(pii_hits) AS hits, SUM((pii_hits>0)::INT) AS messages FROM messages").iloc[0]
    audit = get_telemetry()._all("SELECT category, action, COUNT(*) n FROM audit_events GROUP BY 1, 2")
    return {
        "controls": [
            {"id": "GOV-001", "name": "Secrets in environment only", "status": "implemented",
             "detail": "GEMINI_API_KEY read from env/.env; never sent to the browser; .env is git-ignored."},
            {"id": "GOV-002", "name": "PII masking before model, index, logs and UI", "status": "implemented",
             "detail": f"Patterns: {', '.join(PII_PATTERNS)}. Hits in this dataset: {int(pii['hits'] or 0)} in {int(pii['messages'] or 0)} messages."},
            {"id": "GOV-003", "name": "Customer pseudonymisation", "status": "implemented", "detail": "Customer handles replaced with salted hashes; not used in analysis."},
            {"id": "GOV-004", "name": "Prompt-injection controls", "status": "implemented",
             "detail": "Transcripts passed as delimited data; typed outputs only; no model-generated SQL/code; heuristic flagging in the audit log."},
            {"id": "GOV-005", "name": "Approved operations only", "status": "implemented", "detail": "Registered read-only DuckDB operations with validated arguments and row limits."},
            {"id": "GOV-006", "name": "Numeric grounding of model text", "status": "implemented",
             "detail": "Model explanations containing numbers not in the verified results are rejected."},
            {"id": "GOV-007", "name": "Coaching safeguards and human review", "status": "implemented",
             "detail": f"Minimum {s.min_agent_conversations} conversations per agent; decision-support notice; human review flag on coaching and leadership output."},
            {"id": "GOV-008", "name": "Synthetic data isolation", "status": "implemented",
             "detail": f"Original dataset by default; synthetic modes {'enabled' if s.enable_synthetic_demo else 'disabled'}."},
            {"id": "GOV-009", "name": "Session retention", "status": "implemented", "detail": f"Sessions older than {s.session_retention_days} days are purged at startup; sessions can be cleared."},
            {"id": "GOV-010", "name": "Authentication / RBAC", "status": "not_implemented",
             "detail": "Local prototype: no login. Production would add SSO, RBAC and tenant isolation (see SECURITY.md)."},
        ],
        "model": get_llm().status(),
        "audit_summary": audit,
    }


@router.get("/api/governance/audit")
def audit(limit: int = 100) -> list[dict]:
    return get_telemetry().audit_log(min(limit, 500))


@router.get("/api/model/status")
def model_status() -> dict:
    return get_llm().status()


@router.post("/api/model/retry")
def model_retry() -> dict:
    llm = get_llm()
    if hasattr(llm, "breaker"):
        llm.breaker.success()
    get_telemetry().audit("model", "circuit_reset", llm.status())
    return llm.status()


class ReviewLabel(BaseModel):
    message_id: str = Field(pattern=r"^C\d{7}-T\d{2}$")
    reviewer: str = Field(min_length=1, max_length=40)
    sentiment: str
    empathy: bool | None = None
    note: str | None = Field(None, max_length=300)


@router.get("/api/review/sample")
def review_sample(reviewer: str, n: int = 10) -> dict:
    return {"labels": LABELS, "items": sample(get_db(), get_review_store(), reviewer, min(n, 50))}


@router.post("/api/review/labels")
def review_label(label: ReviewLabel) -> dict:
    try:
        get_review_store().add(label.message_id, label.reviewer, label.sentiment, label.empathy, label.note)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    get_telemetry().audit("human_review", "label_submitted", {"message_id": label.message_id, "reviewer": label.reviewer})
    return {"ok": True}


@router.get("/api/review/metrics")
def review_metrics() -> dict:
    return metrics(get_db(), get_review_store())
