"""Appointment availability adapters (Agent 7 data sources).

Supported adapter types:
* ``SyntheticAvailabilityAdapter`` - Mode A demo data (implemented).
* ``FhirSlotAdapter`` - maps FHIR R4 ``Slot`` resources from an *authorized*
  scheduling server to raw slots. The mapping is implemented and tested against
  synthetic bundles; no live FHIR endpoint is configured (Mode C, planned).
* ``ProviderApiAdapter`` - interface placeholder for partner APIs (planned; raises
  ``IntegrationNotConfigured``).

Adapters never scrape booking websites or bypass access controls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from app.harness.core import ProviderUnavailableError, RateLimitedError
from app.schemas.domain import DataMode, RawSlot, ServiceType, SourceSlotStatus
from app.services.synthetic import SyntheticDataset


class IntegrationNotConfigured(RuntimeError):
    pass


class AvailabilityAdapter(Protocol):
    integration_id: str
    data_mode: DataMode

    def fetch(self, facility_ids: list[str], service: ServiceType) -> list[RawSlot]: ...


# Scenario-driven fault injection (synthetic demo only).
_FLAKY_STATE: dict[str, int] = {}


class SyntheticAvailabilityAdapter:
    data_mode = DataMode.SYNTHETIC

    def __init__(self, integration_id: str, dataset: SyntheticDataset, scenario: str | None = None,
                 workflow_id: str = "") -> None:
        self.integration_id = integration_id
        self.dataset = dataset
        self.scenario = scenario
        self.workflow_id = workflow_id

    def fetch(self, facility_ids: list[str], service: ServiceType) -> list[RawSlot]:
        if self.scenario == "provider_outage" and self.integration_id == "INT-SYN-NORTH":
            raise ProviderUnavailableError("INT-SYN-NORTH: 503 Service Unavailable (simulated outage)")
        if self.scenario == "provider_flaky" and self.integration_id == "INT-SYN-NORTH":
            key = f"{self.workflow_id}:{self.integration_id}"
            _FLAKY_STATE[key] = _FLAKY_STATE.get(key, 0) + 1
            if _FLAKY_STATE[key] == 1:
                raise RateLimitedError("INT-SYN-NORTH: 429 Too Many Requests (simulated)")
        ids = set(facility_ids)
        return [s for s in self.dataset.slots
                if s.source_id == self.integration_id and s.facility_id in ids and s.service == service]


FHIR_SLOT_STATUS = {
    "free": SourceSlotStatus.CONFIRMED_BY_FEED,
    "busy-tentative": SourceSlotStatus.ADVERTISED,
    "busy": SourceSlotStatus.BOOKED,
    "busy-unavailable": SourceSlotStatus.BOOKED,
}


class FhirSlotAdapter:
    """Maps FHIR R4 Slot resources. ``bundle_loader`` must call an authorized endpoint."""

    data_mode = DataMode.AUTHORIZED_LIVE

    def __init__(self, integration_id: str, facility_by_schedule: dict[str, str], service_by_code: dict[str, ServiceType],
                 bundle_loader=None) -> None:
        self.integration_id = integration_id
        self.facility_by_schedule = facility_by_schedule
        self.service_by_code = service_by_code
        self.bundle_loader = bundle_loader

    def map_bundle(self, bundle: dict, retrieved_at: datetime | None = None) -> list[RawSlot]:
        retrieved_at = retrieved_at or datetime.now(UTC)
        out: list[RawSlot] = []
        for entry in bundle.get("entry", []):
            r = entry.get("resource", {})
            if r.get("resourceType") != "Slot" or r.get("status") not in FHIR_SLOT_STATUS:
                continue
            sched = (r.get("schedule") or {}).get("reference", "").split("/")[-1]
            facility = self.facility_by_schedule.get(sched)
            codes = [c.get("code") for st in r.get("serviceType", []) for c in st.get("coding", [])]
            service = next((self.service_by_code[c] for c in codes if c in self.service_by_code), None)
            if facility is None or service is None:
                continue
            try:
                start = datetime.fromisoformat(r["start"].replace("Z", "+00:00")).astimezone(UTC)
            except (KeyError, ValueError):
                start = None
            meta_updated = (r.get("meta") or {}).get("lastUpdated")
            last = datetime.fromisoformat(meta_updated.replace("Z", "+00:00")) if meta_updated else retrieved_at
            out.append(RawSlot(slot_id=f"FHIR-{r.get('id')}", facility_id=facility, service=service, start_utc=start,
                               source_status=FHIR_SLOT_STATUS[r["status"]], source_id=self.integration_id,
                               last_verified_at=last, is_synthetic=False))
        return out

    def fetch(self, facility_ids: list[str], service: ServiceType) -> list[RawSlot]:
        if self.bundle_loader is None:
            raise IntegrationNotConfigured("No authorized FHIR endpoint configured (Mode C not enabled).")
        ids = set(facility_ids)
        return [s for s in self.map_bundle(self.bundle_loader(service)) if s.facility_id in ids and s.service == service]


class ProviderApiAdapter:
    data_mode = DataMode.AUTHORIZED_LIVE

    def __init__(self, integration_id: str) -> None:
        self.integration_id = integration_id

    def fetch(self, facility_ids: list[str], service: ServiceType) -> list[RawSlot]:
        raise IntegrationNotConfigured(f"{self.integration_id}: partner API credentials and agreement not configured.")
