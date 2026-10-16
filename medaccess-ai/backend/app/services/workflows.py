"""Workflow service: starts / resumes the patient LangGraph and persists results."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agents.patient_nodes import new_workflow_id, privacy_check
from app.config.settings import get_settings
from app.database.session import ROLE_PERMISSIONS, session_scope
from app.governance import audit, builds
from app.graphs.patient_graph import compiled_graph
from app.graphs.state import PatientWorkflowState
from app.harness.core import RunContext
from app.models import db as m
from app.schemas.domain import RequisitionStatus
from app.services.synthetic import generate_dataset
from app.telemetry import metrics as tm
from app.telemetry.tracing import current_trace_id, langchain_callbacks, request_id_var, tracer

PAUSED = {"AWAITING_APPROVAL", "AWAITING_PATIENT_DECISION"}
SCENARIOS = {None, "provider_outage", "provider_flaky"}


class SearchParams(BaseModel):
    service: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=25, gt=0, le=100)
    existing_appointment_date: str | None = Field(default=None, max_length=10)
    existing_appointment_days: int | None = Field(default=None, ge=0, le=730)
    requisition_status: RequisitionStatus = RequisitionStatus.UNKNOWN
    requisition_format: str | None = Field(default=None, max_length=80)
    include_private_pay: bool = False
    needs_wheelchair_access: bool = False
    prefer_transit: bool = False
    max_travel_minutes: int | None = Field(default=None, ge=5, le=600)
    scenario: str | None = None
    request_booking: bool = False
    selected_slot_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=80)
    patient_consent: bool = False


def _clock(now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(UTC)


def _make_ctx(wf_id: str, user_id: str | None, role: str, scenario: str | None, clock: datetime,
              build_version: str | None = None) -> RunContext:
    b = builds.BUILDS[build_version] if build_version else builds.active_build()
    ctx = RunContext(workflow_id=wf_id, user_id=user_id, role=role, permissions=set(ROLE_PERMISSIONS.get(role, ())),
                     scenario=scenario, request_id=request_id_var.get(), now=clock,
                     dataset=generate_dataset(clock.replace(minute=0, second=0, microsecond=0)),
                     build_version=b.version, status_mapping=b.status_mapping)
    return ctx


def _config(ctx: RunContext) -> dict:
    return {"configurable": {"thread_id": ctx.workflow_id, "ctx": ctx},
            "callbacks": langchain_callbacks(ctx.workflow_id), "recursion_limit": 60,
            "run_name": "patient_appointment_discovery", "metadata": {"workflow_id": ctx.workflow_id}}


def start_search(params: SearchParams, user_id: str | None, role: str, free_text: str | None = None,
                 now: datetime | None = None, raw_payload: dict | None = None) -> dict:
    if params.scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {params.scenario}")
    clock = _clock(now)
    wf_id = new_workflow_id()
    ctx = _make_ctx(wf_id, user_id, role, params.scenario, clock)
    ctx.free_text = free_text
    ex = None
    if params.existing_appointment_date or params.existing_appointment_days is not None:
        ex = {"date": params.existing_appointment_date, "days_until": params.existing_appointment_days}
    state = PatientWorkflowState(
        workflow_id=wf_id, authenticated_user_id=user_id, user_role=role, build_version=ctx.build_version,
        data_mode=get_settings().data_mode, scenario=params.scenario, clock=clock.isoformat(),
        requested_service=params.service, search_location=params.location, latitude=params.latitude,
        longitude=params.longitude, radius_km=params.radius_km, existing_appointment=ex,
        criteria={"requisition_status": params.requisition_status.value, "requisition_format": params.requisition_format,
                  "include_private_pay": params.include_private_pay,
                  "needs_wheelchair_access": params.needs_wheelchair_access},
        preferences={"prefer_transit": params.prefer_transit, "max_travel_minutes": params.max_travel_minutes},
        request_booking=params.request_booking, selected_slot_id=params.selected_slot_id,
        idempotency_key=params.idempotency_key, patient_consent=params.patient_consent,
        security_events=privacy_check(ctx, raw_payload or {}, free_text),
        timestamps={"started_at": clock.isoformat()},
    )
    with session_scope() as s:
        s.add(m.WorkflowExecution(id=wf_id, workflow_type="patient_search", user_id=user_id, status="RUNNING",
                                  request_id=ctx.request_id, build_version=ctx.build_version,
                                  summary={"scenario": params.scenario}))
    audit.record("WORKFLOW_STARTED", user_id or "anonymous", {"type": "patient_search",
                                                             "service": params.service, "scenario": params.scenario},
                 wf_id)
    tm.ACTIVE_SEARCHES.inc()
    t0 = time.perf_counter()
    try:
        with tracer().start_as_current_span("workflow.patient_search") as span:
            span.set_attribute("medaccess.workflow_id", wf_id)
            ctx.trace_id = current_trace_id()
            compiled_graph().invoke(state, _config(ctx))
    finally:
        tm.ACTIVE_SEARCHES.dec()
    return _finalize(ctx, (time.perf_counter() - t0) * 1000)


def resume(workflow_id: str, resume_value: dict, actor_user_id: str | None, actor_role: str) -> dict:
    snap = compiled_graph().get_state({"configurable": {"thread_id": workflow_id}})
    if not snap or not snap.values:
        raise LookupError("workflow not found")
    st = snap.values
    if not snap.next:
        raise ValueError("workflow is not paused")
    clock = datetime.fromisoformat(st["clock"])
    ctx = _make_ctx(workflow_id, st.get("authenticated_user_id"), st.get("user_role", "patient"), st.get("scenario"),
                    clock, st.get("build_version"))
    t0 = time.perf_counter()
    with tracer().start_as_current_span("workflow.resume") as span:
        span.set_attribute("medaccess.workflow_id", workflow_id)
        ctx.trace_id = current_trace_id()
        compiled_graph().invoke(Command(resume=resume_value), _config(ctx))
    audit.record("WORKFLOW_RESUMED", actor_user_id or "system", {"decision": resume_value.get("decision")},
                 workflow_id)
    return _finalize(ctx, (time.perf_counter() - t0) * 1000)


def get_state(workflow_id: str) -> dict | None:
    snap = compiled_graph().get_state({"configurable": {"thread_id": workflow_id}})
    if not snap or not snap.values:
        return None
    v = _with_defaults(snap.values)
    v.pop("raw_slots", None)
    v["paused_at"] = list(snap.next) if snap.next else []
    return v


def _with_defaults(values: dict) -> dict:
    defaults = PatientWorkflowState(workflow_id=values.get("workflow_id", "")).model_dump()
    return {**defaults, **dict(values)}


def _finalize(ctx: RunContext, duration_ms: float) -> dict:
    snap = compiled_graph().get_state({"configurable": {"thread_id": ctx.workflow_id}})
    v = _with_defaults(snap.values)
    paused = bool(snap.next)
    status = v.get("workflow_status", "UNKNOWN")
    if paused and status not in PAUSED:
        status = "AWAITING_APPROVAL"
    v["workflow_status"] = status
    v["paused_at"] = list(snap.next) if snap.next else []
    v.pop("raw_slots", None)
    tm.WORKFLOWS.labels(type="patient_search", status=status).inc()
    tm.STORE.add("workflow_latency_ms", duration_ms, {"status": status})
    tm.STORE.add("workflow_completed", 0 if status in {"FAILED", "HALTED"} else 1, {"status": status})
    recs = v.get("recommendations", [])
    ws = v.get("wait_summary") or {}
    tm.BUSINESS.labels(event="search_request").inc()
    tm.STORE.add("search_request", 1)
    counts = (v.get("verification_status") or {}).get("counts", {})
    total = sum(counts.values())
    if total:
        tm.STORE.add("verification_rate", counts.get("VERIFIED_AVAILABLE", 0) / total)
    ages = sorted(a["data_age_hours"] for a in v.get("availability_results", []) if a.get("data_age_hours") is not None)
    if ages:
        tm.DATA_AGE.set(ages[len(ages) // 2])
        tm.STORE.add("data_age_hours_median", ages[len(ages) // 2])
    if ws.get("potential_days_saved"):
        tm.STORE.add("days_saved", ws["potential_days_saved"])
    if v.get("radius_km") and v.get("expansions"):
        tm.BUSINESS.labels(event="radius_expansion").inc()
    if v.get("booking_status") == "HANDOFF_PREPARED":
        tm.BUSINESS.labels(event="booking_handoff").inc()
        tm.STORE.add("booking_handoff", 1)
    with session_scope() as s:
        row = s.get(m.WorkflowExecution, ctx.workflow_id)
        assert row is not None
        row.status, row.trace_id, row.duration_ms = status, ctx.trace_id, round(duration_ms, 2)
        row.summary = {"scenario": v.get("scenario"), "service": v.get("requested_service"),
                       "confirmed": ws.get("confirmed_count"), "unverified": ws.get("unverified_count"),
                       "errors": len(v.get("errors", []))}
        if not s.get(m.SearchRequest, ctx.workflow_id):
            s.add(m.SearchRequest(id=ctx.workflow_id, user_id=ctx.user_id, workflow_id=ctx.workflow_id,
                                  service_code=v.get("requested_service"), location_label=v.get("search_location"),
                                  radius_km=int(v["radius_km"]) if v.get("radius_km") else None, status=status,
                                  params={"criteria": v.get("criteria"), "preferences": v.get("preferences")}))
            s.flush()
            for c in v.get("facility_cards", []):
                s.add(m.SearchResult(search_id=ctx.workflow_id, facility_id=c["facility"]["id"],
                                     slot_id=(c.get("best_slot") or {}).get("slot_id"),
                                     verification_status=c["availability_state"],
                                     eligibility_status=(c.get("eligibility") or {}).get("status", "UNKNOWN"),
                                     straight_km=c["geo"]["straight_km"]))
            for r in recs:
                s.add(m.RecommendationRow(search_id=ctx.workflow_id, rank=r["rank"], tier=r["tier"],
                                          facility_id=r["facility_id"], slot_id=r["slot_id"],
                                          days_until=r["days_until"], days_saved=r["days_saved"],
                                          verification_status=r["verification_status"],
                                          build_version=ctx.build_version))
            for a in v.get("availability_results", []):
                s.add(m.SlotVerification(slot_id=a["slot_id"], workflow_id=ctx.workflow_id,
                                         verification_status=a["verification_status"],
                                         build_version=ctx.build_version, reasons=a["verification_reasons"],
                                         data_age_hours=a.get("data_age_hours")))
        else:
            sr = s.get(m.SearchRequest, ctx.workflow_id)
            if sr is not None:
                sr.status = status
        for t in ctx.tool_log:
            s.add(m.ToolExecution(workflow_id=ctx.workflow_id, agent=t["agent"], tool=t["tool"], status=t["status"],
                                  duration_ms=t["duration_ms"], attempt=t["attempt"], error=t["error"]))
            if t["status"] != "ok" and t["tool"] == "availability.fetch_slots":
                s.add(m.IntegrationError(integration_id=(t.get("error") or "").split(":")[0][:30] or "unknown",
                                         workflow_id=ctx.workflow_id, error_type=t["status"],
                                         message=t["error"] or ""))
    audit.record("WORKFLOW_" + ("PAUSED" if paused else "FINISHED"), "supervisor",
                 {"status": status, "duration_ms": round(duration_ms, 2),
                  "security_events": len(v.get("security_events", []))}, ctx.workflow_id)
    v["duration_ms"] = round(duration_ms, 2)
    v["request_id"] = ctx.request_id
    v["notice"] = ("DEMONSTRATION DATA - NOT LIVE APPOINTMENT AVAILABILITY" if v.get("data_mode") == "SYNTHETIC"
                   else None)
    return v
