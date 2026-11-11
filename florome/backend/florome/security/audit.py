"""Hash-chained, append-only audit log. Each event's hash covers its content and the previous event's hash,
so editing or deleting any stored event breaks verification from that point on."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.models import AuditEvent, as_utc, utcnow
from florome.security.redaction import redact

GENESIS = "0" * 64


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256(obj: Any) -> str:
    return hashlib.sha256((obj if isinstance(obj, str) else canonical(obj)).encode()).hexdigest()


def _event_hash(prev: str, tenant_id: str, at: str, actor: str, action: str, target: str, outcome: str, detail: dict) -> str:
    return sha256({"prev": prev, "tenant": tenant_id, "at": at, "actor": actor, "action": action, "target": target,
                   "outcome": outcome, "detail": detail})


def record(db: Session, tenant_id: str, actor: str, action: str, target: str, outcome: str, detail: dict | None = None) -> AuditEvent:
    detail = redact(detail or {})
    last = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.seq.desc()).limit(1)).first()
    prev = last.hash if last else GENESIS
    at = utcnow()
    ev = AuditEvent(tenant_id=tenant_id, at=at, actor=actor, action=action, target=target, outcome=outcome, detail=detail,
                    prev_hash=prev, hash=_event_hash(prev, tenant_id, at.isoformat(), actor, action, target, outcome, detail))
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session, tenant_id: str) -> dict[str, Any]:
    prev = GENESIS
    events = db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.seq)).all()
    for ev in events:
        expected = _event_hash(prev, ev.tenant_id, as_utc(ev.at).isoformat(), ev.actor, ev.action, ev.target, ev.outcome, ev.detail)
        if ev.prev_hash != prev or ev.hash != expected:
            return {"valid": False, "events_checked": len(events), "broken_at": ev.id}
        prev = ev.hash
    return {"valid": True, "events_checked": len(events), "broken_at": None}
