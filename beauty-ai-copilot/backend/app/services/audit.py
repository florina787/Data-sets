"""Append-only audit trail with a hash chain.

Application behaviour is append-only (no update/delete API). The hash chain makes tampering
detectable at the application level; stronger tamper resistance needs infrastructure controls
(WORM storage, restricted DB roles, external anchoring) — documented in docs/LIMITATIONS.md.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import AuditEvent, utcnow

GENESIS = "0" * 64


def _digest(prev: str, payload: dict) -> str:
    return hashlib.sha256((prev + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()


def record(db: Session, *, tenant_id: str, actor_id: str, action: str, status: str, change_id: str | None = None,
           reason: str = "", version_refs: dict | None = None, input_refs: dict | None = None,
           trace_id: str | None = None) -> AuditEvent:
    last = db.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
                      .order_by(AuditEvent.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    created = utcnow()
    payload = {"tenant_id": tenant_id, "change_id": change_id, "actor_id": actor_id, "action": action, "status": status,
               "reason": reason, "version_refs": version_refs or {}, "input_refs": input_refs or {},
               "trace_id": trace_id, "created_at": created.isoformat()}
    ev = AuditEvent(tenant_id=tenant_id, change_id=change_id, actor_id=actor_id, action=action, status=status,
                    reason=reason, version_refs=version_refs or {}, input_refs=input_refs or {}, trace_id=trace_id,
                    prev_hash=prev, hash=_digest(prev, payload), created_at=created)
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session, tenant_id: str) -> dict:
    events = db.execute(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.id)).scalars().all()
    prev = GENESIS
    for ev in events:
        created = ev.created_at
        payload = {"tenant_id": ev.tenant_id, "change_id": ev.change_id, "actor_id": ev.actor_id, "action": ev.action,
                   "status": ev.status, "reason": ev.reason, "version_refs": ev.version_refs, "input_refs": ev.input_refs,
                   "trace_id": ev.trace_id, "created_at": _iso(created)}
        if ev.prev_hash != prev or ev.hash != _digest(prev, payload):
            return {"valid": False, "broken_at": ev.id, "events": len(events)}
        prev = ev.hash
    return {"valid": True, "events": len(events)}


def _iso(dt) -> str:
    # SQLite drops tzinfo on read; normalise to the UTC form written at creation.
    from datetime import timezone
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
