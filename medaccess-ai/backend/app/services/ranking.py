"""Wait-time comparison (Agent 10) and recommendation ranking (Agent 11).

Fully deterministic. Verified slots and unverified possibilities are ranked in
separate tiers; an unverified slot can never be ranked as a confirmed alternative.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.schemas.domain import (
    AvailabilityStatus,
    EligibilityResult,
    EligibilityStatus,
    Facility,
    GeoResult,
    Recommendation,
    VerifiedSlot,
)

A = AvailabilityStatus
CONFIRMED_TIER = "CONFIRMED_ALTERNATIVE"
UNVERIFIED_TIER = "UNVERIFIED_POSSIBILITY"
POSSIBILITY_STATUSES = {A.ADVERTISED_UNVERIFIED, A.CONTACT_REQUIRED}
ELIGIBLE_STATUSES = {EligibilityStatus.ELIGIBLE, EligibilityStatus.ELIGIBLE_WITH_CONDITIONS}


class Preferences(BaseModel):
    prefer_transit: bool = False
    max_travel_minutes: int | None = None
    earliest_date: date | None = None  # do not offer slots before this local date


def days_until(start_utc: datetime | None, now: datetime, tz: str = "America/Toronto") -> int | None:
    if start_utc is None:
        return None
    z = ZoneInfo(tz)
    return (start_utc.astimezone(z).date() - now.astimezone(z).date()).days


def days_saved(existing_days: int | None, alternative_days: int | None) -> int | None:
    if existing_days is None or alternative_days is None:
        return None
    return max(0, existing_days - alternative_days)


def score(days: int, km: float, minutes: int, prefs: Preferences, transit_ok: bool) -> float:
    """Lower is better. Earliest date dominates; distance and travel time break ties."""
    s = days * 10.0 + km * 0.8 + minutes * 0.2
    if prefs.prefer_transit and not transit_ok:
        s += 25.0
    return round(s, 2)


def rank(verified: list[VerifiedSlot], eligibility: dict[str, EligibilityResult], geo: dict[str, GeoResult],
         facilities: dict[str, Facility], now: datetime | None = None, existing_appointment_days: int | None = None,
         prefs: Preferences | None = None, limit: int = 10) -> list[Recommendation]:
    now = now or datetime.now(UTC)
    prefs = prefs or Preferences()
    candidates: list[tuple[str, float, Recommendation]] = []
    for v in verified:
        el = eligibility.get(v.facility_id)
        g = geo.get(v.facility_id)
        f = facilities.get(v.facility_id)
        if el is None or g is None or f is None or el.status not in ELIGIBLE_STATUSES:
            continue
        if v.verification_status == A.VERIFIED_AVAILABLE:
            tier = CONFIRMED_TIER
        elif v.verification_status in POSSIBILITY_STATUSES:
            tier = UNVERIFIED_TIER
        else:
            continue
        d = days_until(v.start_utc, now, f.timezone)
        if d is None or d < 0:
            continue
        if prefs.earliest_date and v.start_utc and v.start_utc.astimezone(ZoneInfo(f.timezone)).date() < prefs.earliest_date:
            continue
        if prefs.max_travel_minutes is not None and g.est_driving_minutes > prefs.max_travel_minutes:
            continue
        sc = score(d, g.straight_km, g.est_driving_minutes, prefs, g.transit_accessible)
        reasons = [f"{d} day(s) away", f"{g.straight_km:.1f} km (straight-line)",
                   f"~{g.est_driving_minutes} min drive (estimate)"]
        saved = days_saved(existing_appointment_days, d)
        if saved:
            reasons.append(f"{saved} day(s) sooner than your current appointment")
        if el.status == EligibilityStatus.ELIGIBLE_WITH_CONDITIONS:
            reasons.append("Eligibility conditions apply - see checklist")
        if tier == UNVERIFIED_TIER:
            reasons.append("NOT CONFIRMED - provider contact required to verify")
        candidates.append((tier, sc, Recommendation(
            rank=0, tier=tier, facility_id=f.id, facility_name=f.name, slot_id=v.slot_id, service=v.service,
            start_local=v.start_local, start_utc=v.start_utc, days_until=d, days_saved=saved,
            straight_km=g.straight_km, est_driving_minutes=g.est_driving_minutes,
            verification_status=v.verification_status, display_status=v.display_status,
            eligibility_status=el.status, score=sc, reasons=reasons, source_id=v.source_id,
            last_verified_at=v.last_verified_at, is_synthetic=v.is_synthetic, booking_capability=f.booking_capability,
        )))
    # Confirmed tier always precedes unverified; then by score, then stable ids.
    candidates.sort(key=lambda t: (0 if t[0] == CONFIRMED_TIER else 1, t[1], t[2].facility_id, t[2].slot_id))
    out: list[Recommendation] = []
    seen_facility_tier: set[tuple[str, str]] = set()
    for tier, _, rec in candidates:
        key = (rec.facility_id, tier)
        if key in seen_facility_tier:  # best slot per facility per tier
            continue
        seen_facility_tier.add(key)
        rec.rank = len(out) + 1
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def summarize_wait(recs: list[Recommendation], existing_days: int | None) -> dict:
    confirmed = [r for r in recs if r.tier == CONFIRMED_TIER]
    best = confirmed[0] if confirmed else None
    return {
        "existing_wait_days": existing_days,
        "best_confirmed_days": best.days_until if best else None,
        "potential_days_saved": days_saved(existing_days, best.days_until) if best else None,
        "confirmed_count": len(confirmed),
        "unverified_count": len(recs) - len(confirmed),
        "basis": "Verified alternatives only. Unverified possibilities are excluded from days-saved.",
    }
