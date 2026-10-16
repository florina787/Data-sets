"""Audit Agent (18): append-only, hash-chained, redacted audit trail."""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from sqlalchemy import select

from app.database.session import session_scope
from app.models import db as m
from app.security.guards import redact

_lock = threading.Lock()
GENESIS = "0" * 64


def _digest(prev: str, event_type: str, actor: str, workflow_id: str | None, payload: dict) -> str:
    body = json.dumps({"p": prev, "t": event_type, "a": actor, "w": workflow_id, "d": payload},
                      sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def record(event_type: str, actor: str, payload: dict[str, Any] | None = None, workflow_id: str | None = None,
           severity: str = "INFO") -> str:
    safe = redact(payload or {})
    with _lock, session_scope() as s:
        last = s.scalar(select(m.AuditEvent).order_by(m.AuditEvent.id.desc()).limit(1))
        prev = last.hash if last else GENESIS
        h = _digest(prev, event_type, actor, workflow_id, safe)
        s.add(m.AuditEvent(event_type=event_type, actor=actor, workflow_id=workflow_id, severity=severity,
                           payload=safe, prev_hash=prev, hash=h))
    return h


def verify_chain() -> dict:
    with session_scope() as s:
        rows = s.scalars(select(m.AuditEvent).order_by(m.AuditEvent.id)).all()
        prev = GENESIS
        for r in rows:
            if r.prev_hash != prev or _digest(prev, r.event_type, r.actor, r.workflow_id, r.payload) != r.hash:
                return {"valid": False, "broken_at": r.id, "events": len(rows)}
            prev = r.hash
        return {"valid": True, "events": len(rows), "head": prev}


def list_events(workflow_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    with session_scope() as s:
        q = select(m.AuditEvent).order_by(m.AuditEvent.id.desc())
        if workflow_id:
            q = q.where(m.AuditEvent.workflow_id == workflow_id)
        rows = s.scalars(q.offset(offset).limit(limit)).all()
        return [{"id": r.id, "event_type": r.event_type, "actor": r.actor, "workflow_id": r.workflow_id,
                 "severity": r.severity, "payload": r.payload, "hash": r.hash[:16],
                 "created_at": r.created_at.isoformat()} for r in rows]
