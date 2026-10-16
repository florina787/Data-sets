"""Pure, in-process search pipeline built from the same deterministic services the
LangGraph tools call. Used for QA scenarios, simulations and ground-truth
comparison (no persistence, no checkpoints)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.harness.core import ProviderUnavailableError
from app.integrations.availability import SyntheticAvailabilityAdapter
from app.schemas.domain import Recommendation, ServiceType, VerifiedSlot
from app.services import eligibility as elig
from app.services import geo
from app.services import ranking as rk
from app.services.synthetic import SyntheticDataset
from app.services.verification import dedupe_slots, verify_slot


class PipelineInput(BaseModel):
    service: ServiceType
    latitude: float
    longitude: float
    radius_km: float
    existing_days: int | None = None
    criteria: elig.PatientCriteria = elig.PatientCriteria()
    prefs: rk.Preferences = rk.Preferences()


class PipelineOutput(BaseModel):
    verified: list[VerifiedSlot]
    recommendations: list[Recommendation]
    failed_sources: list[str]
    duplicates_removed: list[str]
    wait_summary: dict


def run_pipeline(inp: PipelineInput, ds: SyntheticDataset, now: datetime, mapping: str = "correct",
                 scenario: str | None = None, fail_sources: set[str] | None = None) -> PipelineOutput:
    facs = [f for f in ds.facilities if inp.service in f.services]
    in_radius = geo.within_radius(facs, inp.latitude, inp.longitude, inp.radius_km)
    ids = [f.id for f, _ in in_radius]
    by_integ: dict[str, list[str]] = {}
    for f, _ in in_radius:
        by_integ.setdefault(f.integration_id, []).append(f.id)
    if ids:
        by_integ["INT-SYN-PUBLIC"] = sorted(set(by_integ.get("INT-SYN-PUBLIC", [])) | set(ids))
    raw, failed = [], []
    for integ, fids in sorted(by_integ.items()):
        try:
            if fail_sources and integ in fail_sources:
                raise ProviderUnavailableError(f"{integ}: simulated outage")
            raw.extend(SyntheticAvailabilityAdapter(integ, ds, scenario).fetch(fids, inp.service))
        except ProviderUnavailableError:
            failed.append(integ)
    unique, dropped = dedupe_slots(raw)
    verified = [verify_slot(s, ds.facility(s.facility_id), ds.integration(s.source_id), now, mapping=mapping)
                for s in unique]
    eligibility = {f.id: elig.evaluate(f, inp.service, inp.criteria) for f, _ in in_radius}
    geos = {f.id: g for f, g in in_radius}
    recs = rk.rank(verified, eligibility, geos, {f.id: f for f in ds.facilities}, now, inp.existing_days, inp.prefs)
    return PipelineOutput(verified=verified, recommendations=recs, failed_sources=failed, duplicates_removed=dropped,
                          wait_summary=rk.summarize_wait(recs, inp.existing_days))
