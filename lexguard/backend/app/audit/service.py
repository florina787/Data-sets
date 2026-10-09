"""Tamper-evident audit trail (hash chain) with forward and reverse traceability."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid

from sqlalchemy import select

from app.models.db import AuditEventRow, session
from app.security.redaction import redact

_lock = threading.Lock()
GENESIS = "0" * 64

TRACE_ORDER = ["REQUEST_RECEIVED", "MATTER_CONTEXT", "ACCESS_DECISION", "ETHICAL_WALL_DECISION", "POLICY_DECISION",
               "SUITABILITY_ASSESSED", "ROUTING_DECISION", "PROVIDER_INVOKED", "RETRIEVAL", "AGENT_INVOKED",
               "WORK_PRODUCT_CREATED", "ASSURANCE_RESULT", "HUMAN_REVIEW_PENDING", "HUMAN_REVIEW_APPROVED",
               "HUMAN_REVIEW_REJECTED", "FINAL_STATUS"]


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, default=str)).encode()).hexdigest()


def record(event_type: str, *, request_id: str | None, user_id: str | None, client_id: str | None,
           matter_id: str | None, payload: dict | None = None, severity: str = "INFO") -> str:
    payload = redact(payload or {})
    event_id = "EVT-" + uuid.uuid4().hex[:16]
    with _lock, session() as s:
        last = s.execute(select(AuditEventRow).order_by(AuditEventRow.id.desc()).limit(1)).scalar_one_or_none()
        prev = last.hash if last else GENESIS
        body = {"event_id": event_id, "request_id": request_id, "event_type": event_type, "user_id": user_id,
                "client_id": client_id, "matter_id": matter_id, "payload": payload, "severity": severity}
        s.add(AuditEventRow(event_id=event_id, request_id=request_id, event_type=event_type, severity=severity,
                            user_id=user_id, client_id=client_id, matter_id=matter_id, payload=payload,
                            prev_hash=prev, hash=_hash(prev, body)))
        s.commit()
    return event_id


def _row(r: AuditEventRow) -> dict:
    return {"event_id": r.event_id, "request_id": r.request_id, "ts": r.ts.isoformat() if r.ts else None,
            "event_type": r.event_type, "severity": r.severity, "user_id": r.user_id, "client_id": r.client_id,
            "matter_id": r.matter_id, "payload": r.payload, "hash": r.hash, "prev_hash": r.prev_hash}


def events_for_matter(matter_id: str, limit: int = 300) -> list[dict]:
    with session() as s:
        rows = s.execute(select(AuditEventRow).where(AuditEventRow.matter_id == matter_id)
                         .order_by(AuditEventRow.id.desc()).limit(limit)).scalars().all()
        return [_row(r) for r in rows]


def events_for_request(request_id: str) -> list[dict]:
    with session() as s:
        rows = s.execute(select(AuditEventRow).where(AuditEventRow.request_id == request_id)
                         .order_by(AuditEventRow.id)).scalars().all()
        return [_row(r) for r in rows]


def recent_events(limit: int = 200, severity: str | None = None) -> list[dict]:
    with session() as s:
        q = select(AuditEventRow).order_by(AuditEventRow.id.desc()).limit(limit)
        if severity:
            q = select(AuditEventRow).where(AuditEventRow.severity == severity).order_by(AuditEventRow.id.desc()).limit(limit)
        return [_row(r) for r in s.execute(q).scalars().all()]


def verify_chain() -> dict:
    with session() as s:
        rows = s.execute(select(AuditEventRow).order_by(AuditEventRow.id)).scalars().all()
    prev = GENESIS
    for r in rows:
        body = {"event_id": r.event_id, "request_id": r.request_id, "event_type": r.event_type, "user_id": r.user_id,
                "client_id": r.client_id, "matter_id": r.matter_id, "payload": r.payload, "severity": r.severity}
        if r.prev_hash != prev or _hash(prev, body) != r.hash:
            return {"valid": False, "broken_at": r.event_id, "events": len(rows)}
        prev = r.hash
    return {"valid": True, "events": len(rows)}


def trace_chain(request_id: str) -> list[dict]:
    """USER -> CLIENT -> MATTER -> TASK -> POLICY -> ACCESS -> ROUTING -> PROVIDER -> SOURCES -> AGENTS
    -> WORK PRODUCT -> ASSURANCE -> HUMAN REVIEW -> FINAL STATUS."""
    events = events_for_request(request_id)
    order = {k: i for i, k in enumerate(TRACE_ORDER)}
    return sorted(events, key=lambda e: (order.get(e["event_type"], 50), e["ts"] or ""))
