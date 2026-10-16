"""Notification Agent (13). In-app delivery is implemented; email/SMS adapters
are disabled until an approved provider is configured. Message bodies are
deliberately generic and never include service type, symptoms or requisition data."""

from __future__ import annotations

from sqlalchemy import select

from app.database.session import session_scope
from app.governance import audit
from app.harness.core import new_id
from app.models import db as m

CHANNELS = {"in_app": "implemented", "email": "disabled (no approved provider configured)",
            "sms": "disabled (no approved provider configured)"}

TEMPLATES = {
    "booking_handoff_ready": ("Your booking handoff is ready",
                              "Open MedAccess AI to view the provider's booking instructions."),
    "search_saved": ("Search saved", "Your saved search is available in MedAccess AI."),
    "approval_needed": ("Action needed", "A request is waiting for your review in MedAccess AI."),
}


class NotificationError(Exception):
    pass


def has_consent(user_id: str, consent_type: str = "notifications") -> bool:
    with session_scope() as s:
        row = s.scalar(select(m.PatientConsent).where(m.PatientConsent.user_id == user_id,
                                                      m.PatientConsent.consent_type == consent_type)
                       .order_by(m.PatientConsent.created_at.desc()).limit(1))
        return bool(row and row.granted and row.revoked_at is None)


def send(user_id: str, template: str, channel: str = "in_app", workflow_id: str | None = None) -> dict:
    if channel != "in_app":
        raise NotificationError(f"channel {channel} is {CHANNELS.get(channel, 'unknown')}")
    if template not in TEMPLATES:
        raise NotificationError("unknown template")
    if not has_consent(user_id, "notifications"):
        audit.record("NOTIFICATION_SKIPPED", "notification_agent", {"reason": "no consent"}, workflow_id)
        return {"sent": False, "reason": "Notification consent not granted."}
    title, body = TEMPLATES[template]
    nid = new_id("NTF")
    with session_scope() as s:
        s.add(m.Notification(id=nid, user_id=user_id, channel=channel, title=title, body=body, status="DELIVERED"))
    audit.record("NOTIFICATION_SENT", "notification_agent", {"id": nid, "template": template, "channel": channel},
                 workflow_id)
    return {"sent": True, "id": nid, "channel": channel}


def list_for(user_id: str) -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(select(m.Notification).where(m.Notification.user_id == user_id)
                         .order_by(m.Notification.created_at.desc()).limit(100)).all()
        return [{"id": r.id, "title": r.title, "body": r.body, "channel": r.channel, "read": r.read,
                 "created_at": r.created_at.isoformat()} for r in rows]


def set_consent(user_id: str, consent_type: str, granted: bool, scope: str = "") -> dict:
    cid = new_id("CNS")
    with session_scope() as s:
        s.add(m.PatientConsent(id=cid, user_id=user_id, consent_type=consent_type, granted=granted, scope=scope))
    audit.record("CONSENT_RECORDED", user_id, {"consent_type": consent_type, "granted": granted})
    return {"id": cid, "consent_type": consent_type, "granted": granted}
