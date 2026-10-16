"""Availability verification (Agent 8) - deterministic status mapping.

The mapping from a source's raw slot status to an ``AvailabilityStatus`` lives in
``STATUS_MAPPINGS`` and is selected by the *active build* (see
``app.governance.builds``). Build ``1.5.0`` carries the controlled demonstration
defect used by the AI-SDLC "90-Day MRI Wait-Time Challenge": it maps advertised,
unverified slots to VERIFIED_AVAILABLE. The defect exists only so the platform
can demonstrate detection, root-cause analysis, fix and regression testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config.settings import get_settings
from app.schemas.domain import (
    AvailabilityStatus,
    Facility,
    ProviderIntegration,
    RawSlot,
    SourceSlotStatus,
    VerifiedSlot,
)

A = AvailabilityStatus
CORRECT_STATUS_MAP: dict[SourceSlotStatus, AvailabilityStatus] = {
    SourceSlotStatus.CONFIRMED_BY_FEED: A.VERIFIED_AVAILABLE,
    SourceSlotStatus.ADVERTISED: A.ADVERTISED_UNVERIFIED,
    SourceSlotStatus.CALL_TO_CONFIRM: A.CONTACT_REQUIRED,
    SourceSlotStatus.BOOKED: A.UNAVAILABLE,
    SourceSlotStatus.CANCELLED: A.UNAVAILABLE,
}

# DEMONSTRATION DEFECT (build 1.5.0 only): advertised slots incorrectly treated as confirmed.
DEFECTIVE_STATUS_MAP: dict[SourceSlotStatus, AvailabilityStatus] = {
    **CORRECT_STATUS_MAP,
    SourceSlotStatus.ADVERTISED: A.VERIFIED_AVAILABLE,
}

STATUS_MAPPINGS = {"correct": CORRECT_STATUS_MAP, "defect_unverified_as_confirmed": DEFECTIVE_STATUS_MAP}


def to_local_iso(dt: datetime | None, tz: str) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo(tz)).isoformat(timespec="minutes")


def verify_slot(slot: RawSlot, facility: Facility | None, integration: ProviderIntegration | None,
                now: datetime | None = None, mapping: str = "correct",
                max_age_hours: float | None = None, min_reliability: float | None = None) -> VerifiedSlot:
    s = get_settings()
    now = now or datetime.now(UTC)
    max_age = s.max_verified_age_hours if max_age_hours is None else max_age_hours
    min_rel = s.min_source_reliability if min_reliability is None else min_reliability
    status_map = STATUS_MAPPINGS[mapping]
    reasons: list[str] = []
    age_h = None
    if slot.last_verified_at is not None:
        age_h = round((now - slot.last_verified_at).total_seconds() / 3600, 2)

    status: AvailabilityStatus
    if facility is None:
        status, reasons = A.UNKNOWN, ["Facility identity could not be confirmed in the directory."]
    elif slot.service not in facility.services:
        status, reasons = A.UNAVAILABLE, [f"Facility does not list {slot.service.value} as an offered service."]
    elif slot.start_utc is None:
        status, reasons = A.UNKNOWN, ["Slot has no valid appointment timestamp."]
    elif slot.start_utc <= now:
        status, reasons = A.UNAVAILABLE, ["Appointment time has already passed (expired)."]
    elif integration is None or not integration.authorized:
        status, reasons = A.UNKNOWN, ["Availability source is not an authorized integration."]
    elif slot.last_verified_at is None or age_h is None or age_h < 0:
        status, reasons = A.UNKNOWN, ["Missing or invalid verification timestamp."]
    else:
        status = status_map[slot.source_status]
        reasons.append(f"Source reported '{slot.source_status.value}'.")
        if status == A.VERIFIED_AVAILABLE:
            if age_h > max_age:
                status = A.ADVERTISED_UNVERIFIED
                reasons.append(f"Data is {age_h:.1f}h old (limit {max_age:.0f}h) - stale, needs re-verification.")
            elif integration.reliability < min_rel:
                status = A.ADVERTISED_UNVERIFIED
                reasons.append(f"Source reliability {integration.reliability:.2f} is below {min_rel:.2f}.")
            else:
                reasons.append(f"Confirmed by source {age_h:.1f}h ago; reliability {integration.reliability:.2f}.")
        elif status == A.CONTACT_REQUIRED:
            reasons.append("Provider must be contacted to confirm this opening.")
        elif status == A.ADVERTISED_UNVERIFIED:
            reasons.append("Opening is advertised but has not been confirmed by the provider.")

    is_synth = slot.is_synthetic or (facility.is_synthetic if facility else True)
    tz = facility.timezone if facility else "America/Toronto"
    return VerifiedSlot(
        slot_id=slot.slot_id, facility_id=slot.facility_id, service=slot.service, start_utc=slot.start_utc,
        start_local=to_local_iso(slot.start_utc, tz), source_id=slot.source_id, source_status=slot.source_status,
        verification_status=status, display_status=A.DEMO_SIMULATED if is_synth else status,
        verification_reasons=reasons, last_verified_at=slot.last_verified_at, data_age_hours=age_h,
        is_synthetic=is_synth,
    )


def dedupe_slots(slots: list[RawSlot]) -> tuple[list[RawSlot], list[str]]:
    """Drop duplicate slots (same facility, service and start time) keeping the most recently verified."""
    best: dict[tuple, RawSlot] = {}
    dropped: list[str] = []
    for sl in slots:
        key = (sl.facility_id, sl.service, sl.start_utc)
        cur = best.get(key)
        if cur is None:
            best[key] = sl
            continue
        keep, drop = (sl, cur) if (sl.last_verified_at or datetime.min.replace(tzinfo=UTC)) > (
            cur.last_verified_at or datetime.min.replace(tzinfo=UTC)) else (cur, sl)
        best[key] = keep
        dropped.append(drop.slot_id)
    return list(best.values()), dropped
