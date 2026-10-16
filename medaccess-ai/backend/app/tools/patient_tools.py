"""Typed tools used by patient-workflow agents.

Each tool is a deterministic Python function with Pydantic input/output schemas,
registered with the harness (and therefore exposed through the MCP layer and as
LangChain ``StructuredTool``s). Critical decisions are never parsed from free text.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.harness.core import RunContext, ToolSpec, register_tool
from app.integrations.availability import SyntheticAvailabilityAdapter
from app.schemas.domain import (
    EligibilityResult,
    Facility,
    GeoResult,
    RawSlot,
    ServiceType,
    VerifiedSlot,
)
from app.services import eligibility as elig
from app.services import geo
from app.services.gazetteer import ResolvedLocation, resolve_location
from app.services.synthetic import current_dataset
from app.services.verification import dedupe_slots, verify_slot


def _ds(ctx: RunContext):
    return ctx.dataset or current_dataset()


def _now(ctx: RunContext) -> datetime:
    return ctx.now or datetime.now(UTC)


# --- Geolocation MCP -------------------------------------------------------------------------
class ResolveLocationIn(BaseModel):
    query: str = Field(min_length=1, max_length=80)


class ResolveLocationOut(BaseModel):
    found: bool
    location: ResolvedLocation | None = None


def _resolve(args: ResolveLocationIn, ctx: RunContext) -> ResolveLocationOut:
    loc = resolve_location(args.query)
    return ResolveLocationOut(found=loc is not None, location=loc)


class RadiusFilterIn(BaseModel):
    facility_ids: list[str]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=100)


class RadiusFilterOut(BaseModel):
    results: list[GeoResult]


def _radius(args: RadiusFilterIn, ctx: RunContext) -> RadiusFilterOut:
    ds = _ds(ctx)
    facs = [f for f in ds.facilities if f.id in set(args.facility_ids)]
    return RadiusFilterOut(results=[g for _, g in geo.within_radius(facs, args.latitude, args.longitude,
                                                                     args.radius_km)])


# --- Healthcare Facility Directory MCP ------------------------------------------------------
class DirectoryIn(BaseModel):
    service: ServiceType
    needs_wheelchair_access: bool = False


class DirectoryOut(BaseModel):
    facilities: list[Facility]
    data_mode: str


def _directory(args: DirectoryIn, ctx: RunContext) -> DirectoryOut:
    ds = _ds(ctx)
    facs = [f for f in ds.facilities if args.service in f.services]
    return DirectoryOut(facilities=facs, data_mode="SYNTHETIC")


# --- Appointment Availability MCP -----------------------------------------------------------
class FetchSlotsIn(BaseModel):
    integration_id: str
    facility_ids: list[str]
    service: ServiceType


class FetchSlotsOut(BaseModel):
    integration_id: str
    slots: list[RawSlot]


def _fetch(args: FetchSlotsIn, ctx: RunContext) -> FetchSlotsOut:
    adapter = SyntheticAvailabilityAdapter(args.integration_id, _ds(ctx), ctx.scenario, ctx.workflow_id)
    return FetchSlotsOut(integration_id=args.integration_id, slots=adapter.fetch(args.facility_ids, args.service))


class VerifyIn(BaseModel):
    slots: list[RawSlot]


class VerifyOut(BaseModel):
    verified: list[VerifiedSlot]
    duplicates_removed: list[str]
    status_mapping: str


def _verify(args: VerifyIn, ctx: RunContext) -> VerifyOut:
    ds = _ds(ctx)
    unique, dropped = dedupe_slots(args.slots)
    out = [verify_slot(sl, ds.facility(sl.facility_id), ds.integration(sl.source_id), _now(ctx),
                       mapping=ctx.status_mapping) for sl in unique]
    return VerifyOut(verified=out, duplicates_removed=dropped, status_mapping=ctx.status_mapping)


# --- Requisition Rules MCP -------------------------------------------------------------------
class EligibilityIn(BaseModel):
    facility_ids: list[str]
    service: ServiceType
    criteria: elig.PatientCriteria


class EligibilityOut(BaseModel):
    results: list[EligibilityResult]


def _eligibility(args: EligibilityIn, ctx: RunContext) -> EligibilityOut:
    ds = _ds(ctx)
    return EligibilityOut(results=[elig.evaluate(f, args.service, args.criteria)
                                   for f in ds.facilities if f.id in set(args.facility_ids)])


def register() -> None:
    register_tool(ToolSpec("geo.resolve_location", "Resolve a city / postal area to approximate coordinates.",
                           _resolve, ResolveLocationIn, ResolveLocationOut, permission="patient:search",
                           mcp_server="geolocation"))
    register_tool(ToolSpec("geo.filter_by_radius", "Straight-line radius filter with travel estimates.",
                           _radius, RadiusFilterIn, RadiusFilterOut, permission="patient:search",
                           mcp_server="geolocation"))
    register_tool(ToolSpec("directory.search_facilities", "List directory facilities offering a service.",
                           _directory, DirectoryIn, DirectoryOut, permission="patient:search",
                           mcp_server="facility_directory"))
    register_tool(ToolSpec("availability.fetch_slots", "Fetch raw slots from an authorized availability source.",
                           _fetch, FetchSlotsIn, FetchSlotsOut, permission="patient:search", untrusted_output=True,
                           mcp_server="appointment_availability"))
    register_tool(ToolSpec("availability.verify_slots", "Deterministically verify slot status and freshness.",
                           _verify, VerifyIn, VerifyOut, permission="patient:search",
                           mcp_server="appointment_availability"))
    register_tool(ToolSpec("requisition.evaluate", "Evaluate requisition/referral eligibility rules.",
                           _eligibility, EligibilityIn, EligibilityOut, permission="patient:search",
                           mcp_server="requisition_rules"))
