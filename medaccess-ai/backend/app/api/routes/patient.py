"""Patient-facing API: copilot, search, facilities, bookings, approvals, preferences."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.copilot import christina
from app.database.session import session_scope
from app.governance import approvals, audit, builds
from app.graphs import sdlc_graph
from app.models import db as m
from app.rag.pipeline import get_index
from app.schemas.domain import SERVICE_LABELS, AvailabilityStatus, ServiceType
from app.security.auth import Principal, current_user, require
from app.services import booking as booking_svc
from app.services import geo, notifications, workflows
from app.services.gazetteer import SUPPORTED_RADII_KM, resolve_location
from app.services.synthetic import current_dataset
from app.services.verification import verify_slot

router = APIRouter(prefix="/api/v1")


# ------------------------------------------------------------------ copilot
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=40)
    scenario: str | None = None


@router.post("/copilot/greet", tags=["copilot"])
def greet(body: dict | None = None, p: Principal = Depends(require("patient:chat"))):
    return christina.greet((body or {}).get("session_id"), p.user_id, p.role)


@router.post("/copilot/chat", tags=["copilot"])
def chat(body: ChatIn, p: Principal = Depends(require("patient:chat"))):
    if body.scenario not in workflows.SCENARIOS:
        raise HTTPException(400, "unknown scenario")
    return christina.handle(body.message, body.session_id, p.user_id, p.role, body.scenario)


@router.delete("/copilot/sessions/{session_id}", tags=["copilot"])
def end_chat(session_id: str, p: Principal = Depends(require("patient:chat"))):
    christina.end_session(session_id)
    return {"ended": True}


# ------------------------------------------------------------------ search
class FacilitySearchIn(BaseModel):
    service: ServiceType
    location: str = Field(min_length=1, max_length=80)
    radius_km: int = 25


@router.post("/search/facilities", tags=["search"])
def search_facilities(body: FacilitySearchIn, p: Principal = Depends(require("patient:search"))):
    if body.radius_km not in SUPPORTED_RADII_KM:
        raise HTTPException(422, f"radius_km must be one of {SUPPORTED_RADII_KM}")
    loc = resolve_location(body.location)
    if loc is None:
        raise HTTPException(422, "Location not recognised. Try a GTA city name or postal code (e.g. M5V).")
    ds = current_dataset()
    facs = [f for f in ds.facilities if body.service in f.services]
    res = geo.within_radius(facs, loc.latitude, loc.longitude, body.radius_km)
    return {"location": loc, "radius_km": body.radius_km, "data_mode": "SYNTHETIC",
            "notice": "DEMONSTRATION DATA - fictional facilities",
            "results": [{"facility": f.model_dump(mode="json"), "geo": g.model_dump()} for f, g in res]}


@router.post("/search/appointments", tags=["search"])
def search_appointments(body: workflows.SearchParams, p: Principal = Depends(require("patient:search"))):
    try:
        return workflows.start_search(body, p.user_id, p.role, raw_payload=body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/workflows/start", tags=["workflows"])
def start_workflow(body: workflows.SearchParams, p: Principal = Depends(require("patient:search"))):
    return search_appointments(body, p)


def _owned_state(workflow_id: str, p: Principal) -> dict:
    st = workflows.get_state(workflow_id)
    if st is None:
        raise HTTPException(404, "workflow not found")
    if st.get("authenticated_user_id") != p.user_id and "agents:read" not in p.permissions:
        raise HTTPException(404, "workflow not found")
    return st


@router.get("/workflows/{workflow_id}", tags=["workflows"])
def get_workflow(workflow_id: str, p: Principal = Depends(current_user)):
    return _owned_state(workflow_id, p)


@router.get("/workflows/{workflow_id}/events", tags=["workflows"])
def workflow_events(workflow_id: str, p: Principal = Depends(current_user)):
    st = _owned_state(workflow_id, p)
    return {"workflow_id": workflow_id, "status": st["workflow_status"], "agent_trace": st.get("agent_trace", []),
            "audit_events": audit.list_events(workflow_id, limit=200)}


# ------------------------------------------------------------------ facilities / appointments
@router.get("/facilities", tags=["facilities"])
def list_facilities(service: ServiceType | None = None, city: str | None = Query(default=None, max_length=60),
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    p: Principal = Depends(require("patient:search"))):
    fs = current_dataset().facilities
    if service:
        fs = [f for f in fs if service in f.services]
    if city:
        fs = [f for f in fs if f.city.lower() == city.lower()]
    return {"total": len(fs), "limit": limit, "offset": offset, "data_mode": "SYNTHETIC",
            "items": [f.model_dump(mode="json") for f in fs[offset:offset + limit]]}


@router.get("/facilities/{facility_id}", tags=["facilities"])
def get_facility(facility_id: str, p: Principal = Depends(require("patient:search"))):
    ds = current_dataset()
    f = ds.facility(facility_id)
    if f is None:
        raise HTTPException(404, "facility not found")
    integ = ds.integration(f.integration_id)
    return {"facility": f.model_dump(mode="json"), "integration": integ.model_dump(mode="json") if integ else None}


@router.get("/appointments/{slot_id}", tags=["facilities"])
def get_appointment(slot_id: str, p: Principal = Depends(require("patient:search"))):
    ds = current_dataset()
    sl = next((s for s in ds.slots if s.slot_id == slot_id), None)
    if sl is None:
        raise HTTPException(404, "appointment slot not found")
    b = builds.active_build()
    v = verify_slot(sl, ds.facility(sl.facility_id), ds.integration(sl.source_id), mapping=b.status_mapping)
    return {"slot": v.model_dump(mode="json"), "build_version": b.version,
            "verified_at": datetime.now(UTC).isoformat()}


# ------------------------------------------------------------------ bookings
class BookingIn(BaseModel):
    search_workflow_id: str = Field(max_length=40)
    slot_id: str = Field(max_length=40)
    idempotency_key: str = Field(min_length=8, max_length=80)
    consent: bool


@router.post("/bookings/request", tags=["bookings"])
def request_booking(body: BookingIn, p: Principal = Depends(require("patient:book"))):
    src = _owned_state(body.search_workflow_id, p)
    if not body.consent:
        raise HTTPException(400, "Explicit consent is required to prepare a booking handoff.")
    with session_scope() as s:
        existing = s.scalar(select(m.BookingRequest).where(m.BookingRequest.idempotency_key == body.idempotency_key))
        if existing is not None:
            if existing.user_id != p.user_id or existing.slot_id != body.slot_id:
                raise HTTPException(409, "Idempotency key already used for a different request.")
            return {"idempotent_replay": True, "booking": booking_svc.get(existing.id),
                    "workflow_id": existing.workflow_id, "approval_id": existing.approval_id}
    crit, prefs = src.get("criteria", {}), src.get("preferences", {})
    params = workflows.SearchParams(
        service=src["requested_service"], latitude=src["latitude"], longitude=src["longitude"],
        location=src.get("search_location"), radius_km=src["radius_km"],
        existing_appointment_days=(src.get("existing_appointment") or {}).get("days_until"),
        requisition_status=crit.get("requisition_status", "UNKNOWN"), requisition_format=crit.get("requisition_format"),
        include_private_pay=crit.get("include_private_pay", False),
        needs_wheelchair_access=crit.get("needs_wheelchair_access", False),
        prefer_transit=prefs.get("prefer_transit", False), scenario=src.get("scenario"), request_booking=True,
        selected_slot_id=body.slot_id, idempotency_key=body.idempotency_key, patient_consent=True)
    notifications.set_consent(p.user_id, "booking_handoff", True, scope=f"slot:{body.slot_id}")
    wf = workflows.start_search(params, p.user_id, p.role)
    return {"idempotent_replay": False, "workflow_id": wf["workflow_id"], "workflow_status": wf["workflow_status"],
            "approval_id": wf.get("approval_id"), "booking": wf.get("booking"), "errors": wf.get("errors"),
            "pending_question": wf.get("pending_question")}


@router.get("/bookings", tags=["bookings"])
def my_bookings(p: Principal = Depends(require("patient:self"))):
    return {"items": booking_svc.list_for_user(p.user_id)}


@router.get("/bookings/{booking_id}", tags=["bookings"])
def get_booking(booking_id: str, p: Principal = Depends(current_user)):
    try:
        b = booking_svc.get(booking_id)
    except booking_svc.BookingError as e:
        raise HTTPException(404, str(e)) from e
    if b["user_id"] != p.user_id and "admin:all" not in p.permissions:
        raise HTTPException(404, "booking not found")
    return b


@router.post("/bookings/{booking_id}/patient-reported", tags=["bookings"])
def patient_reported(booking_id: str, p: Principal = Depends(require("patient:self"))):
    b = get_booking(booking_id, p)
    try:
        return booking_svc.transition(b["id"], booking_svc.B.PATIENT_REPORTED_BOOKED, p.user_id)
    except booking_svc.BookingError as e:
        raise HTTPException(409, str(e)) from e


# ------------------------------------------------------------------ approvals
class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    note: str | None = Field(default=None, max_length=500)
    answer: str | None = Field(default=None, max_length=1000)
    radius_km: int | None = None


@router.get("/approvals", tags=["approvals"])
def list_approvals(status: str | None = "PENDING", p: Principal = Depends(current_user)):
    return {"items": approvals.list_for(p.user_id, p.role, status)}


@router.get("/approvals/{approval_id}", tags=["approvals"])
def get_approval(approval_id: str, p: Principal = Depends(current_user)):
    try:
        a = approvals.get(approval_id)
    except approvals.ApprovalError as e:
        raise HTTPException(404, str(e)) from e
    visible = {x["id"] for x in approvals.list_for(p.user_id, p.role, None, limit=500)}
    if a["id"] not in visible:
        raise HTTPException(404, "approval not found")
    return a


@router.post("/approvals/{approval_id}/decision", tags=["approvals"])
def decide(approval_id: str, body: DecisionIn, p: Principal = Depends(current_user)):
    try:
        a = approvals.decide(approval_id, body.decision, p.user_id, p.role, body.note or body.answer)
    except approvals.ApprovalError as e:
        raise HTTPException(409, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    result = None
    if a["workflow_type"] == "sdlc" and a["workflow_id"]:
        result = sdlc_graph.resume(a["workflow_id"], {"decision": body.decision, "answer": body.answer,
                                                      "decided_by": p.user_id, "approval_id": approval_id})
    elif a["workflow_id"]:
        st = workflows.get_state(a["workflow_id"])
        if st and st.get("paused_at"):
            radius = body.radius_km
            if a["action_type"] == "SEARCH_RADIUS_EXPANSION" and radius is None and body.decision == "APPROVED":
                radius = (a["payload"].get("options") or [{}])[0].get("radius_km")
            result = workflows.resume(a["workflow_id"], {"decision": body.decision, "approval_id": approval_id,
                                                         "radius_km": radius}, p.user_id, p.role)
    return {"approval": a, "workflow": result}


# ------------------------------------------------------------------ notifications / consents / preferences
@router.get("/notifications", tags=["patient"])
def my_notifications(p: Principal = Depends(current_user)):
    return {"items": notifications.list_for(p.user_id), "channels": notifications.CHANNELS}


class ConsentIn(BaseModel):
    consent_type: str = Field(pattern="^(notifications|voice|booking_handoff|data_sharing)$")
    granted: bool


@router.post("/consents", tags=["patient"])
def consent(body: ConsentIn, p: Principal = Depends(current_user)):
    return notifications.set_consent(p.user_id, body.consent_type, body.granted)


@router.get("/consents", tags=["patient"])
def consents(p: Principal = Depends(current_user)):
    with session_scope() as s:
        rows = s.scalars(select(m.PatientConsent).where(m.PatientConsent.user_id == p.user_id)
                         .order_by(m.PatientConsent.created_at.desc())).all()
        latest: dict[str, dict] = {}
        for r in rows:
            latest.setdefault(r.consent_type, {"granted": r.granted, "at": r.created_at.isoformat()})
        return latest


class PrefsIn(BaseModel):
    default_radius_km: int = 25
    prefer_transit: bool = False
    needs_wheelchair_access: bool = False
    include_private_pay: bool = False
    language: str = Field(default="en-CA", pattern="^(en-CA|fr-CA)$")
    voice_enabled: bool = False
    reduced_motion: bool = False
    notifications_in_app: bool = True


@router.get("/preferences", tags=["patient"])
def get_prefs(p: Principal = Depends(current_user)):
    with session_scope() as s:
        r = s.get(m.UserPreference, p.user_id)
        return PrefsIn().model_dump() if r is None else {k: getattr(r, k) for k in PrefsIn.model_fields}


@router.put("/preferences", tags=["patient"])
def put_prefs(body: PrefsIn, p: Principal = Depends(current_user)):
    if body.default_radius_km not in SUPPORTED_RADII_KM:
        raise HTTPException(422, f"default_radius_km must be one of {SUPPORTED_RADII_KM}")
    with session_scope() as s:
        r = s.get(m.UserPreference, p.user_id) or m.UserPreference(user_id=p.user_id)
        for k, v in body.model_dump().items():
            setattr(r, k, v)
        s.merge(r)
    return body


@router.get("/searches/history", tags=["patient"])
def history(saved: bool = False, p: Principal = Depends(current_user)):
    with session_scope() as s:
        q = select(m.SearchRequest).where(m.SearchRequest.user_id == p.user_id)
        if saved:
            q = q.where(m.SearchRequest.saved.is_(True))
        rows = s.scalars(q.order_by(m.SearchRequest.created_at.desc()).limit(50)).all()
        return {"items": [{"id": r.id, "service": r.service_code, "location": r.location_label,
                           "radius_km": r.radius_km, "status": r.status, "saved": r.saved,
                           "created_at": r.created_at.isoformat()} for r in rows]}


@router.post("/searches/{search_id}/save", tags=["patient"])
def save_search(search_id: str, p: Principal = Depends(current_user)):
    with session_scope() as s:
        r = s.get(m.SearchRequest, search_id)
        if r is None or r.user_id != p.user_id:
            raise HTTPException(404, "search not found")
        r.saved = True
    notifications.send(p.user_id, "search_saved")
    return {"saved": True}


@router.delete("/me/data", tags=["patient"])
def delete_my_data(p: Principal = Depends(require("patient:self"))):
    """Data deletion workflow: removes the user's searches, bookings, consents, notifications."""
    with session_scope() as s:
        counts = {}
        for model in (m.SearchRequest, m.BookingRequest, m.PatientConsent, m.Notification):
            counts[model.__tablename__] = s.query(model).filter(model.user_id == p.user_id).delete()
    audit.record("USER_DATA_DELETED", p.user_id, {"counts": counts})
    return {"deleted": counts}


# ------------------------------------------------------------------ knowledge
@router.get("/knowledge/search", tags=["knowledge"])
def knowledge(q: str = Query(min_length=2, max_length=300), service: ServiceType | None = None,
              p: Principal = Depends(require("patient:chat"))):
    return get_index().answer(q, service.value if service else None)


@router.get("/knowledge/documents", tags=["knowledge"])
def knowledge_docs(p: Principal = Depends(current_user)):
    idx = get_index()
    return {"kb_version": idx.kb_version, "errors": idx.errors,
            "documents": [{**{k: v for k, v in d.items()}, "stale": idx.is_stale(d["document_id"]),
                           "chunks": sum(1 for c in idx.chunks if c.document_id == d["document_id"])}
                          for d in idx.docs.values()]}


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard", tags=["patient"])
def dashboard(p: Principal = Depends(current_user)):
    from app.telemetry import metrics as tm

    ds = current_dataset()
    b = builds.active_build()
    verified = [verify_slot(s, ds.facility(s.facility_id), ds.integration(s.source_id), mapping=b.status_mapping)
                for s in ds.slots]
    now = datetime.now(UTC)
    by_service: dict[str, list[int]] = {}
    for v in verified:
        if v.verification_status == AvailabilityStatus.VERIFIED_AVAILABLE and v.start_utc:
            by_service.setdefault(v.service.value, []).append((v.start_utc - now).days)
    saved = tm.STORE.summary("days_saved", synthetic=False)
    return {
        "data_mode": "SYNTHETIC", "notice": "DEMONSTRATION DATA - NOT LIVE APPOINTMENT AVAILABILITY",
        "participating_facilities": len(ds.facilities),
        "verified_available_appointments": sum(len(x) for x in by_service.values()),
        "observed_wait_days_median_by_service": {
            k: {"median_days": median(v), "n": len(v), "label": SERVICE_LABELS[ServiceType(k)]}
            for k, v in sorted(by_service.items())},
        "wait_time_qualification": "Median days to the next verified slot in the synthetic dataset; small samples, "
                                   "not representative of real wait times.",
        "potential_days_saved": {"searches_with_savings": saved.get("count", 0), "mean": saved.get("mean"),
                                 "basis": "Measured from searches run in this process (verified alternatives only)."},
        "active_searches": tm.ACTIVE_SEARCHES._value.get(),
        "build_version": b.version, "dataset_generated_at": ds.generated_at.isoformat(),
    }
