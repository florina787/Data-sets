"""Append-only, hash-chained audit log. Each event's hash covers its content and the previous event's hash, so any
modification or deletion is detectable by `verify_chain`. Details are privacy-redacted before they are written."""
from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy.orm import sessionmaker

from backend.config import get_settings
from backend.db import models as m
from backend.db.session import make_engine
from governance.policy import canonical_json

GENESIS = "0" * 64
_lock = threading.Lock()


@lru_cache
def _factory(url: str):
    eng = make_engine(url)
    if url.startswith("sqlite"):
        m.Base.metadata.create_all(eng, tables=[m.AuditEvent.__table__])
    return sessionmaker(bind=eng, expire_on_commit=False)


@contextmanager
def audit_session():
    s = _factory(get_settings().audit_url)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _digest(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + canonical_json(body)).encode()).hexdigest()


def _body(e: m.AuditEvent) -> dict:
    return {"id": e.id, "ts": e.ts.replace(tzinfo=None).isoformat(timespec="microseconds"), "tenant_id": e.tenant_id, "actor": e.actor,
            "action": e.action, "resource_type": e.resource_type, "resource_id": e.resource_id, "decision": e.decision,
            "reasons": e.reasons, "policy_version": e.policy_version, "details": e.details}


def record(*, tenant_id: str, actor: str, action: str, resource_type: str = "-", resource_id: str = "-",
           decision: str = "info", reasons: list | None = None, policy_version: str = "-", details: dict | None = None) -> str:
    from privacy.detect import redact_structure
    with _lock, audit_session() as s:
        if s.get_bind().dialect.name == "postgresql":
            s.execute(text("SELECT pg_advisory_xact_lock(74201)"))
        last = s.execute(select(m.AuditEvent.hash).order_by(m.AuditEvent.seq.desc()).limit(1)).scalar()
        prev = last or GENESIS
        ev = m.AuditEvent(id=f"AE-{uuid.uuid4().hex[:16]}", ts=datetime.now(timezone.utc).replace(tzinfo=None), tenant_id=tenant_id,
                          actor=actor, action=action, resource_type=resource_type, resource_id=str(resource_id), decision=decision,
                          reasons=reasons or [], policy_version=policy_version, details=redact_structure(details or {}),
                          prev_hash=prev, hash="")
        ev.hash = _digest(prev, _body(ev))
        s.add(ev)
        return ev.id


def verify_chain(s: Session | None = None) -> dict:
    if s is None:
        with audit_session() as s2:
            return verify_chain(s2)
    prev = GENESIS
    n = 0
    for e in s.scalars(select(m.AuditEvent).order_by(m.AuditEvent.seq)):
        n += 1
        if e.prev_hash != prev or _digest(prev, _body(e)) != e.hash:
            return {"valid": False, "events_checked": n, "first_invalid_seq": e.seq, "event_id": e.id}
        prev = e.hash
    return {"valid": True, "events_checked": n, "head": prev}
