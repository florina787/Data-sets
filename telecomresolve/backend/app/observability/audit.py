"""Append-only audit trail with a per-tenant hash chain (tamper-evident only)."""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models.orm import AuditEvent
from .redaction import redact

log = logging.getLogger("telecomresolve.audit")
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

GENESIS = "0" * 64


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def record(
    db: Session,
    *,
    tenant_id: str,
    actor_id: str,
    actor_role: str,
    event_type: str,
    case_id: str | None = None,
    trace_id: str | None = None,
    node: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    generation_mode: str | None = None,
    connector_mode: str | None = None,
    policy_version: str | None = None,
    latency_ms: float | None = None,
    usage: dict | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append one event. Caller owns the transaction so the event commits
    atomically with the state change it describes."""
    chain_key = case_id or f"tenant:{tenant_id}"
    q = select(AuditEvent.event_hash).order_by(AuditEvent.id.desc()).limit(1)
    q = q.where(AuditEvent.case_id == case_id) if case_id else q.where(
        AuditEvent.case_id.is_(None), AuditEvent.tenant_id == tenant_id)
    prev = db.execute(q).scalar_one_or_none() or GENESIS
    event = AuditEvent(
        event_id=f"evt-{uuid.uuid4().hex[:16]}",
        tenant_id=tenant_id,
        case_id=case_id,
        trace_id=trace_id or f"trace-{uuid.uuid4().hex[:12]}",
        request_id=request_id_var.get(),
        occurred_at=utcnow(),
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=event_type,
        node=node,
        from_status=from_status,
        to_status=to_status,
        generation_mode=generation_mode,
        connector_mode=connector_mode,
        policy_version=policy_version,
        latency_ms=latency_ms,
        usage=usage or {},
        detail=redact(detail or {}),
        prev_hash=prev,
        event_hash="",
    )
    event.event_hash = _hash(hashable(event, chain_key))
    db.add(event)
    db.flush()
    log.info("audit %s case=%s actor=%s %s->%s", event_type, case_id, actor_id, from_status, to_status)
    return event


def hashable(e: AuditEvent, chain_key: str | None = None) -> dict:
    return {
        "chain": chain_key or (e.case_id or f"tenant:{e.tenant_id}"),
        "event_id": e.event_id, "tenant_id": e.tenant_id, "case_id": e.case_id,
        "trace_id": e.trace_id, "occurred_at": e.occurred_at.isoformat(), "actor_id": e.actor_id,
        "actor_role": e.actor_role, "event_type": e.event_type, "node": e.node,
        "from_status": e.from_status, "to_status": e.to_status, "policy_version": e.policy_version,
        "detail": e.detail, "prev_hash": e.prev_hash,
    }


def verify_chain(events: list[AuditEvent]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    prev = GENESIS
    for e in events:
        if e.prev_hash != prev:
            problems.append(f"{e.event_id}: prev_hash mismatch")
        if _hash(hashable(e)) != e.event_hash:
            problems.append(f"{e.event_id}: content hash mismatch")
        prev = e.event_hash
    return not problems, problems
