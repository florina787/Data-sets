"""Patient-workflow agent node implementations.

Each function receives the typed state and the run context and returns a partial
state update. Deterministic Python performs every safety-relevant decision
(distance, dates, eligibility, verification, ranking, booking transitions).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from langgraph.types import interrupt

from app.governance import approvals
from app.graphs.state import PatientWorkflowState as S
from app.harness.core import (
    CircuitOpen,
    RunContext,
    TransientToolError,
    call_tool,
    new_id,
)
from app.schemas.domain import (
    SERVICE_LABELS,
    AvailabilityStatus,
    EligibilityResult,
    GeoResult,
    RawSlot,
    ServiceType,
    VerifiedSlot,
)
from app.security.guards import detect_injection, excess_fields
from app.security.safety import screen
from app.services import booking as booking_svc
from app.services import notifications
from app.services import ranking as rk
from app.services.copilot_nlu import classify_service
from app.services.gazetteer import SUPPORTED_RADII_KM
from app.services.synthetic import generate_dataset

A = AvailabilityStatus
MAX_EXPANSIONS = 2


def _now(ctx: RunContext) -> datetime:
    return ctx.now or datetime.now(UTC)


def _ds(ctx: RunContext):
    if ctx.dataset is None:
        ctx.dataset = generate_dataset(_now(ctx).replace(minute=0, second=0, microsecond=0))
    return ctx.dataset


# ------------------------------------------------------------------------------------- intake
def intake(state: S, ctx: RunContext) -> dict:
    missing = []
    upd: dict = {}
    if not state.requested_service:
        missing.append("service")
    if state.latitude is None or state.longitude is None:
        if state.search_location:
            loc = call_tool(ctx, "intake", "geo.resolve_location", {"query": state.search_location})
            if loc.found:
                upd.update(latitude=loc.location.latitude, longitude=loc.location.longitude,
                           search_location=loc.location.label)
            else:
                missing.append("location")
        else:
            missing.append("location")
    radius = state.radius_km or 25
    if radius not in SUPPORTED_RADII_KM:
        radius = min(SUPPORTED_RADII_KM, key=lambda r: abs(r - radius))
    upd["radius_km"] = radius
    ex = state.existing_appointment
    if ex and ex.get("date") and ex.get("days_until") is None:
        try:
            d = date.fromisoformat(ex["date"])
            local_today = _now(ctx).astimezone(ZoneInfo("America/Toronto")).date()
            upd["existing_appointment"] = {"date": ex["date"], "days_until": (d - local_today).days}
        except ValueError:
            upd["errors"] = ["intake: existing appointment date is not a valid YYYY-MM-DD date"]
    upd["missing_fields"] = missing
    if missing:
        upd["workflow_status"] = "NEEDS_INPUT"
        upd["_explanation"] = f"Need: {', '.join(missing)}"
    else:
        upd["_explanation"] = f"Collected service, location ({upd.get('search_location', state.search_location)}), " \
                              f"radius {radius} km"
    return upd


def privacy_check(ctx: RunContext, raw_payload: dict, free_text: str | None) -> list[dict]:
    events = []
    extra = excess_fields(raw_payload)
    if extra:
        events.append({"type": "EXCESS_DATA_COLLECTION", "fields": extra, "action": "ignored"})
    if free_text and detect_injection(free_text).suspicious:
        events.append({"type": "PROMPT_INJECTION_ATTEMPT", "action": "treated as data; no tool authority granted"})
    return events


# ------------------------------------------------------------------------------------- safety
def clinical_safety(state: S, ctx: RunContext) -> dict:
    text = ctx.free_text or ""
    r = screen(text)
    out: dict = {"safety": r.model_dump()}
    if r.interrupt:
        out["workflow_status"] = "SAFETY_INTERRUPTED"
        out["_explanation"] = "Potentially urgent symptoms mentioned - routine search paused"
    else:
        out["_explanation"] = "No urgent-symptom language detected" + (" (negated mention noted)" if r.negated_flags else "")
    return out


def safety_interruption(state: S, ctx: RunContext) -> dict:
    return {"explanation": state.safety.get("message"), "workflow_status": "SAFETY_INTERRUPTED",
            "source_references": [{"source_id": "SAFETY-POLICY-v1", "kind": "policy",
                                   "title": "MedAccess clinical safety escalation policy"}],
            "_explanation": "Emergency guidance shown (911 / Health811 / 988)"}


# ------------------------------------------------------------------------------------- classification
def service_classification(state: S, ctx: RunContext) -> dict:
    raw = state.requested_service or ""
    svc: ServiceType | None
    try:
        svc = ServiceType(raw.upper())
    except ValueError:
        svc = classify_service(raw)
    if svc is None:
        return {"workflow_status": "NEEDS_INPUT", "missing_fields": ["service"],
                "_explanation": f"Could not map '{raw[:30]}' to a supported service"}
    return {"requested_service": svc.value, "_explanation": f"Classified as {SERVICE_LABELS[svc]}"}


# ------------------------------------------------------------------------------------- discovery
def facility_discovery(state: S, ctx: RunContext) -> dict:
    out = call_tool(ctx, "facility_discovery", "directory.search_facilities",
                    {"service": state.requested_service,
                     "needs_wheelchair_access": bool(state.criteria.get("needs_wheelchair_access"))})
    ids = [f.id for f in out.facilities]
    return {"facility_candidates": ids,
            "source_references": [{"source_id": "DIRECTORY-SYNTHETIC", "kind": "facility_directory",
                                   "title": "Synthetic facility directory (fictional)"}],
            "_explanation": f"{len(ids)} directory facilities offer this service"}


def geospatial(state: S, ctx: RunContext) -> dict:
    out = call_tool(ctx, "geospatial", "geo.filter_by_radius",
                    {"facility_ids": state.facility_candidates, "latitude": state.latitude,
                     "longitude": state.longitude, "radius_km": state.radius_km})
    return {"geo_results": [g.model_dump() for g in out.results],
            "_explanation": f"{len(out.results)} within {state.radius_km:g} km (straight-line)"}


# ------------------------------------------------------------------------------------- availability
def _integrations_for(state: S, ctx: RunContext) -> dict[str, list[str]]:
    ds = _ds(ctx)
    by: dict[str, list[str]] = {}
    in_radius = {g["facility_id"] for g in state.geo_results}
    for f in ds.facilities:
        if f.id in in_radius:
            by.setdefault(f.integration_id, []).append(f.id)
    # The public advertised feed also lists openings for facilities that have their own integration.
    if in_radius:
        by.setdefault("INT-SYN-PUBLIC", [])
        by["INT-SYN-PUBLIC"] = sorted(set(by["INT-SYN-PUBLIC"]) | in_radius)
    return by


def availability_search(state: S, ctx: RunContext) -> dict:
    slots: list[dict] = []
    failed: list[str] = []
    for integ, fids in sorted(_integrations_for(state, ctx).items()):
        try:
            out = call_tool(ctx, "availability_search", "availability.fetch_slots",
                            {"integration_id": integ, "facility_ids": fids, "service": state.requested_service},
                            retry_key=f"availability:{integ}:{ctx.scenario or 'default'}")
            slots.extend(s.model_dump(mode="json") for s in out.slots)
        except (TransientToolError, CircuitOpen):
            failed.append(integ)
    retries = sum(1 for t in ctx.tool_log if t["tool"] == "availability.fetch_slots" and t["attempt"] > 1)
    return {"raw_slots": slots, "failed_sources": failed, "unavailable_sources": [], "retry_count": state.retry_count + retries,
            "source_references": [{"source_id": i, "kind": "availability_source", "title": f"{i} (synthetic)"}
                                  for i in sorted(_integrations_for(state, ctx)) if i not in failed],
            "_explanation": f"{len(slots)} raw slots from sources" + (f"; {len(failed)} source(s) failed"
                                                                      if failed else "")}


def recovery(state: S, ctx: RunContext) -> dict:
    by = _integrations_for(state, ctx)
    recovered, still_failed, slots = [], [], list(state.raw_slots)
    for integ in state.failed_sources:
        try:
            out = call_tool(ctx, "recovery", "availability.fetch_slots",
                            {"integration_id": integ, "facility_ids": by.get(integ, []),
                             "service": state.requested_service}, retry_key=f"availability:{integ}:{ctx.scenario or 'default'}")
            slots.extend(s.model_dump(mode="json") for s in out.slots)
            recovered.append(integ)
        except (TransientToolError, CircuitOpen) as e:
            still_failed.append(integ)
            ctx.security_events.append({"type": "SOURCE_UNAVAILABLE", "integration": integ, "error": str(e)[:120]})
    msg = (f"Recovered {recovered}" if recovered else "") + (
        f" Marked unavailable: {still_failed} (fallback: provider contact details)" if still_failed else "")
    return {"raw_slots": slots, "failed_sources": [], "unavailable_sources": still_failed,
            "errors": [f"availability source {i} unavailable after bounded retries" for i in still_failed],
            "_explanation": msg.strip() or "Nothing to recover"}


# ------------------------------------------------------------------------------------- data quality / verification
def data_quality(state: S, ctx: RunContext) -> dict:
    ds = _ds(ctx)
    slots = [RawSlot.model_validate(s) for s in state.raw_slots]
    keys = Counter((s.facility_id, s.service, s.start_utc) for s in slots)
    dupes = sum(c - 1 for c in keys.values() if c > 1)
    no_time = [s.slot_id for s in slots if s.start_utc is None]
    unattributed = [s.slot_id for s in slots if ds.integration(s.source_id) is None]
    stale = [s.slot_id for s in slots if s.last_verified_at and
             (_now(ctx) - s.last_verified_at).total_seconds() > 6 * 3600]
    bad_coords = [g["facility_id"] for g in state.geo_results
                  if not (41 < (ds.facility(g["facility_id"]).latitude) < 57)]
    report = {"duplicates": dupes, "invalid_timestamps": no_time, "missing_source_attribution": unattributed,
              "stale_records": len(stale), "invalid_coordinates": bad_coords}
    issues = dupes + len(no_time) + len(unattributed) + len(stale) + len(bad_coords)
    return {"data_quality": report, "_explanation": f"{issues} data-quality issue(s) flagged" if issues
            else "No data-quality issues"}


def availability_verification(state: S, ctx: RunContext) -> dict:
    out = call_tool(ctx, "availability_verification", "availability.verify_slots", {"slots": state.raw_slots})
    counts = Counter(v.verification_status.value for v in out.verified)
    return {"availability_results": [v.model_dump(mode="json") for v in out.verified],
            "verification_status": {"counts": dict(counts), "duplicates_removed": out.duplicates_removed,
                                    "status_mapping": out.status_mapping, "build_version": ctx.build_version},
            "_explanation": ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "No slots to verify"}


def eligibility(state: S, ctx: RunContext) -> dict:
    fids = sorted({g["facility_id"] for g in state.geo_results})
    out = call_tool(ctx, "eligibility", "requisition.evaluate",
                    {"facility_ids": fids, "service": state.requested_service, "criteria": state.criteria})
    counts = Counter(r.status.value for r in out.results)
    return {"eligibility_results": [r.model_dump(mode="json") for r in out.results],
            "_explanation": ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "No facilities"}


def wait_time(state: S, ctx: RunContext) -> dict:
    ex = (state.existing_appointment or {}).get("days_until")
    return {"timestamps": {"wait_evaluated_at": _now(ctx).isoformat()},
            "_explanation": f"Existing wait: {ex} day(s)" if ex is not None else "No existing appointment provided"}


def recommendation(state: S, ctx: RunContext) -> dict:
    ds = _ds(ctx)
    verified = [VerifiedSlot.model_validate(v) for v in state.availability_results]
    elig = {r["facility_id"]: EligibilityResult.model_validate(r) for r in state.eligibility_results}
    geo = {g["facility_id"]: GeoResult.model_validate(g) for g in state.geo_results}
    facs = {f.id: f for f in ds.facilities}
    prefs = rk.Preferences.model_validate(state.preferences or {})
    ex = (state.existing_appointment or {}).get("days_until")
    recs = rk.rank(verified, elig, geo, facs, _now(ctx), ex, prefs)
    summary = rk.summarize_wait(recs, ex)
    cards = []
    for g in state.geo_results:
        f = facs[g["facility_id"]]
        fslots = [v for v in verified if v.facility_id == f.id]
        best = min((v for v in fslots if v.verification_status in (A.VERIFIED_AVAILABLE, A.ADVERTISED_UNVERIFIED,
                                                                   A.CONTACT_REQUIRED) and v.start_utc),
                   key=lambda v: v.start_utc or datetime.max.replace(tzinfo=UTC), default=None)
        source_down = f.integration_id in state.unavailable_sources
        cards.append({
            "facility": {k: getattr(f, k) for k in ("id", "name", "city", "neighbourhood", "latitude", "longitude",
                                                    "phone", "booking_url", "booking_capability", "funding",
                                                    "wheelchair_accessible", "is_synthetic", "network")},
            "geo": g, "eligibility": elig[f.id].model_dump(mode="json") if f.id in elig else None,
            "best_slot": best.model_dump(mode="json") if best else None,
            "days_until": rk.days_until(best.start_utc, _now(ctx)) if best else None,
            "slot_count": len(fslots),
            "source_status": "UNAVAILABLE" if source_down else "OK",
            "availability_state": (A.UNKNOWN.value if source_down else (best.verification_status.value if best
                                                                         else A.UNAVAILABLE.value)),
        })
    expl = _explain(state, recs, summary)
    return {"recommendations": [r.model_dump(mode="json") for r in recs], "wait_summary": summary,
            "facility_cards": cards, "explanation": expl,
            "_explanation": f"{summary['confirmed_count']} confirmed alternative(s), "
                            f"{summary['unverified_count']} unverified possibility(ies)"}


def _explain(state: S, recs: list, summary: dict) -> str:
    label = SERVICE_LABELS.get(ServiceType(state.requested_service), state.requested_service)
    if not recs:
        return (f"I couldn't find an eligible {label} opening within {state.radius_km:g} km in the "
                f"{'synthetic demo ' if state.data_mode == 'SYNTHETIC' else ''}data.")
    parts = []
    confirmed = [r for r in recs if r.tier == rk.CONFIRMED_TIER]
    if confirmed:
        b = confirmed[0]
        parts.append(f"The earliest verified {label} opening is at {b.facility_name}, {b.days_until} day(s) away "
                     f"and {b.straight_km:.1f} km from {state.search_location}.")
        if summary.get("potential_days_saved"):
            parts.append(f"That is {summary['potential_days_saved']} day(s) sooner than your current appointment.")
    else:
        parts.append(f"I found no verified {label} openings, only unverified possibilities that need provider contact.")
    unv = len(recs) - len(confirmed)
    if unv:
        parts.append(f"{unv} other opening(s) are advertised or need a call to confirm - they are NOT confirmed.")
    if state.data_mode == "SYNTHETIC":
        parts.append("All results are demonstration data, not live availability.")
    return " ".join(parts)


# ------------------------------------------------------------------------------------- expansion loop
def expand_search_options(state: S, ctx: RunContext) -> dict:
    ds = _ds(ctx)
    from app.services.geo import haversine_km

    opts = []
    for r in SUPPORTED_RADII_KM:
        if r <= (state.radius_km or 0):
            continue
        lat, lon = state.latitude or 0.0, state.longitude or 0.0
        n = sum(1 for f in ds.facilities if ServiceType(state.requested_service) in f.services and
                haversine_km(lat, lon, f.latitude, f.longitude) <= r)
        opts.append({"radius_km": r, "facilities_offering_service": n})
    can_expand = bool(opts) and state.expansions < MAX_EXPANSIONS
    q = None
    if can_expand:
        a = approvals.create("SEARCH_RADIUS_EXPANSION", "human_approval",
                             f"No verified appointment within {state.radius_km:g} km. Expand the search?",
                             evidence=[{"confirmed_alternatives": 0, "radius_km": state.radius_km}],
                             consequences=["Results may be farther away", "Travel time increases"],
                             payload={"options": opts[:3]}, workflow_id=state.workflow_id,
                             subject_user_id=state.authenticated_user_id)
        q = {"type": "SEARCH_RADIUS_EXPANSION", "approval_id": a["id"], "options": opts[:3]}
    return {"expansion_options": opts[:3], "pending_question": q, "approval_id": q["approval_id"] if q else None,
            "workflow_status": "AWAITING_PATIENT_DECISION" if q else state.workflow_status,
            "agent_trace": ([{"node": "expansion_approval", "agent": "human_approval", "title": "Human Approval Agent", "status": "awaiting_approval",
                              "action": "Waiting for patient to approve radius expansion", "duration_ms": 0,
                              "at": _now(ctx).isoformat()}] if q else []),
            "_explanation": "Offered larger radii to the patient" if q else "No further expansion available"}


def expansion_approval(state: S, ctx: RunContext) -> dict:
    decision = interrupt({"type": "SEARCH_RADIUS_EXPANSION", "approval_id": state.approval_id,
                          "options": state.expansion_options})
    if decision.get("decision") == "APPROVED" and decision.get("radius_km") in SUPPORTED_RADII_KM:
        return {"radius_km": float(decision["radius_km"]), "expansions": state.expansions + 1,
                "pending_question": None, "approval_status": "APPROVED", "workflow_status": "RUNNING",
                "_explanation": f"Patient approved expanding to {decision['radius_km']} km - repeating search"}
    return {"pending_question": None, "approval_status": "REJECTED", "workflow_status": "RUNNING",
            "_explanation": "Patient declined expansion"}


# ------------------------------------------------------------------------------------- review & booking
def patient_review(state: S, ctx: RunContext) -> dict:
    return {"_explanation": f"Presented {len(state.recommendations)} option(s) for patient review"}


def booking_preparation(state: S, ctx: RunContext) -> dict:
    rec = next((r for r in state.recommendations if r["slot_id"] == state.selected_slot_id), None)
    if rec is None:
        return {"booking_status": "FAILED", "workflow_status": "BOOKING_NOT_POSSIBLE",
                "errors": ["Selected slot is not among current eligible results (it may have changed)."],
                "_explanation": "Selected slot not eligible after re-verification"}
    if not state.patient_consent:
        return {"booking_status": "FAILED", "workflow_status": "CONSENT_REQUIRED",
                "errors": ["Patient consent for booking handoff is required."],
                "_explanation": "Consent missing - booking handoff not prepared"}
    key = state.idempotency_key or f"{state.workflow_id}:{state.selected_slot_id}"
    bk, created = booking_svc.get_or_create(key, state.authenticated_user_id, state.workflow_id,
                                            rec["facility_id"], rec["slot_id"])
    appr_id = bk["approval_id"]
    if not appr_id:
        a = approvals.create(
            "BOOKING_SUBMISSION", "booking_assistance",
            f"Prepare a booking handoff for {rec['facility_name']} on {rec['start_local']}.",
            evidence=[{"verification_status": rec["verification_status"], "source": rec["source_id"],
                       "last_verified_at": rec["last_verified_at"], "eligibility": rec["eligibility_status"],
                       "synthetic": rec["is_synthetic"]}],
            consequences=["Provider booking instructions will be prepared for you",
                          "No information is sent to the provider by MedAccess AI",
                          "The appointment is NOT booked until the provider confirms it"],
            payload={"booking_id": bk["id"], "slot_id": rec["slot_id"], "facility_id": rec["facility_id"]},
            workflow_id=state.workflow_id, subject_user_id=state.authenticated_user_id)
        appr_id = a["id"]
        from app.database.session import session_scope
        from app.models import db as m

        with session_scope() as s:
            row = s.get(m.BookingRequest, bk["id"])
            if row is not None:
                row.approval_id = appr_id
    return {"booking": {**bk, "approval_id": appr_id}, "booking_status": "PENDING_APPROVAL", "approval_id": appr_id,
            "workflow_status": "AWAITING_APPROVAL",
            "pending_question": {"type": "BOOKING_SUBMISSION", "approval_id": appr_id},
            "agent_trace": [{"node": "human_approval", "agent": "human_approval", "title": "Human Approval Agent", "status": "awaiting_approval",
                             "action": "Waiting for patient approval of booking handoff", "duration_ms": 0,
                             "at": _now(ctx).isoformat()}],
            "_explanation": ("Created" if created else "Reused (idempotent)") + " booking request; approval requested"}


def human_approval(state: S, ctx: RunContext) -> dict:
    decision = interrupt({"type": "BOOKING_SUBMISSION", "approval_id": state.approval_id})
    if decision.get("approval_id") != state.approval_id:
        return {"approval_status": "INVALID", "workflow_status": "REJECTED", "booking_status": "FAILED",
                "errors": ["Resume value did not reference the pending approval."],
                "_explanation": "Invalid approval reference"}
    st = decision.get("decision")
    if st == "APPROVED" and state.approval_id:
        ctx.approvals.add(state.approval_id)
    return {"approval_status": st, "pending_question": None,
            "workflow_status": "RUNNING" if st == "APPROVED" else "REJECTED",
            "_explanation": f"Patient decision: {st}"}


def booking_handoff(state: S, ctx: RunContext) -> dict:
    ds = _ds(ctx)
    bk = booking_svc.get(state.booking["id"])
    if bk["status"] == "HANDOFF_PREPARED":  # resumed after a crash: never repeat
        return {"booking": bk, "booking_status": bk["status"], "_explanation": "Handoff already prepared (idempotent)"}
    f = ds.facility(bk["facility_id"])
    rec = next(r for r in state.recommendations if r["slot_id"] == bk["slot_id"])
    handoff = booking_svc.handoff_instructions(f, rec["start_local"])
    bk = booking_svc.transition(bk["id"], booking_svc.B.HANDOFF_PREPARED, "booking_assistance", handoff=handoff)
    return {"booking": bk, "booking_status": bk["status"], "_explanation": "Booking handoff instructions prepared"}


def confirmation_verification(state: S, ctx: RunContext) -> dict:
    # Synthetic / public sources cannot produce verifiable provider confirmations.
    return {"_explanation": "No verifiable provider confirmation available - status remains NOT_CONFIRMED",
            "booking": {**state.booking, "confirmation_status": "NOT_CONFIRMED"}}


def notification(state: S, ctx: RunContext) -> dict:
    if not state.authenticated_user_id:
        return {"notification": {"sent": False, "reason": "anonymous"}, "_explanation": "Skipped (anonymous)"}
    r = notifications.send(state.authenticated_user_id, "booking_handoff_ready", "in_app", state.workflow_id)
    return {"notification": r, "_explanation": "In-app notification sent" if r.get("sent") else r.get("reason")}


def audit_node(state: S, ctx: RunContext) -> dict:
    final = state.workflow_status
    if final == "RUNNING":
        final = "COMPLETED"
    return {"workflow_status": final, "token_usage": ctx.tokens, "trace_id": ctx.trace_id,
            "security_events": ctx.security_events[:], "timestamps": {"completed_at": _now(ctx).isoformat()},
            "_explanation": f"Workflow {final}; audit trail recorded"}


def new_workflow_id() -> str:
    return new_id("WF")
