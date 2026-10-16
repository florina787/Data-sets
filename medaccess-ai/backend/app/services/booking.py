"""Booking Assistance Agent (12) state machine.

Booking handoff != booking. In synthetic and public-discovery modes the platform
can only prepare a handoff (official link / phone instructions). A booking is
marked PROVIDER_CONFIRMED only from a verifiable confirmation delivered by an
AUTHORIZED_LIVE integration - which is never the case for synthetic data.
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.session import session_scope
from app.governance import audit
from app.harness.core import new_id
from app.models import db as m
from app.schemas.domain import BookingStatus, Facility
from app.security.crypto import encrypt

B = BookingStatus
ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    B.PENDING_APPROVAL: {B.HANDOFF_PREPARED, B.REJECTED, B.FAILED, B.CANCELLED},
    B.HANDOFF_PREPARED: {B.PATIENT_REPORTED_BOOKED, B.PROVIDER_CONFIRMED, B.CANCELLED},
    B.PATIENT_REPORTED_BOOKED: {B.PROVIDER_CONFIRMED, B.CANCELLED},
    B.PROVIDER_CONFIRMED: {B.CANCELLED},
    B.REJECTED: set(), B.FAILED: set(), B.CANCELLED: set(), B.NOT_REQUESTED: {B.PENDING_APPROVAL},
}


class BookingError(Exception):
    pass


def _row(r: m.BookingRequest) -> dict:
    return {"id": r.id, "idempotency_key": r.idempotency_key, "workflow_id": r.workflow_id, "user_id": r.user_id,
            "facility_id": r.facility_id, "slot_id": r.slot_id, "status": r.status, "approval_id": r.approval_id,
            "handoff": r.handoff, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
            "is_confirmed_booking": r.status == B.PROVIDER_CONFIRMED.value}


def get_or_create(idempotency_key: str, user_id: str | None, workflow_id: str, facility_id: str, slot_id: str,
                  notes: str | None = None) -> tuple[dict, bool]:
    with session_scope() as s:
        existing = s.scalar(select(m.BookingRequest).where(m.BookingRequest.idempotency_key == idempotency_key))
        if existing:
            if existing.slot_id != slot_id or existing.user_id != user_id:
                raise BookingError("idempotency key reused for a different booking request")
            return _row(existing), False
        r = m.BookingRequest(id=new_id("BKG"), idempotency_key=idempotency_key, user_id=user_id,
                             workflow_id=workflow_id, facility_id=facility_id, slot_id=slot_id,
                             status=B.PENDING_APPROVAL.value, handoff={}, notes_encrypted=encrypt(notes))
        s.add(r)
        s.flush()
        return _row(r), True


def get(booking_id: str) -> dict:
    with session_scope() as s:
        r = s.get(m.BookingRequest, booking_id)
        if r is None:
            raise BookingError("booking not found")
        return _row(r)


def list_for_user(user_id: str) -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(select(m.BookingRequest).where(m.BookingRequest.user_id == user_id)
                         .order_by(m.BookingRequest.created_at.desc())).all()
        return [_row(r) for r in rows]


def transition(booking_id: str, new: BookingStatus, actor: str, **fields) -> dict:
    with session_scope() as s:
        r = s.get(m.BookingRequest, booking_id)
        if r is None:
            raise BookingError("booking not found")
        cur = B(r.status)
        if cur == new:
            return _row(r)  # idempotent
        if new not in ALLOWED_TRANSITIONS[cur]:
            raise BookingError(f"invalid transition {cur.value} -> {new.value}")
        r.status = new.value
        for k, v in fields.items():
            setattr(r, k, v)
        s.flush()
        out = _row(r)
    audit.record("BOOKING_STATUS", actor, {"booking_id": booking_id, "from": cur.value, "to": new.value},
                 out["workflow_id"])
    return out


def handoff_instructions(f: Facility, slot_local: str | None) -> dict:
    steps = []
    if f.booking_capability == "online_handoff" and f.booking_url:
        steps.append(f"Open the provider's official booking page: {f.booking_url}")
    steps.append(f"Or call {f.name} at {f.phone} and reference the opening on {slot_local or 'the listed date'}.")
    steps.append("Have your requisition ready; the provider will confirm eligibility and availability.")
    return {"facility_id": f.id, "facility_name": f.name, "booking_capability": f.booking_capability,
            "booking_url": f.booking_url, "phone": f.phone, "slot_local": slot_local, "steps": steps,
            "confirmation_status": "NOT_CONFIRMED",
            "disclaimer": "This is a booking handoff, not a booking. Your appointment is confirmed only when the "
                          "provider confirms it directly." + (" SYNTHETIC DEMO FACILITY - the link and phone number "
                                                             "are fictional." if f.is_synthetic else "")}


def record_provider_confirmation(booking_id: str, provider_reference: str, integration_id: str,
                                 integration_mode: str, actor: str) -> dict:
    if integration_mode != "AUTHORIZED_LIVE":
        raise BookingError("Provider confirmations are accepted only from an authorized live integration.")
    if not provider_reference.strip():
        raise BookingError("A provider confirmation reference is required.")
    with session_scope() as s:
        s.add(m.BookingConfirmation(booking_id=booking_id, provider_reference=provider_reference,
                                    source_integration_id=integration_id, verified=True))
    return transition(booking_id, B.PROVIDER_CONFIRMED, actor)
