"""Deterministic synthetic healthcare dataset (Data Mode A).

Every facility, provider integration and appointment slot produced here is
FICTIONAL. Names carry a "(Demo)" suffix, phone numbers use the reserved 555-01xx
range and booking URLs use the reserved ``.invalid`` top-level domain so that
nothing can be mistaken for, or accidentally reach, a real provider.

The dataset is reproducible: the same ``seed`` and ``now`` always yield the same
records. Slot times are generated relative to ``now`` so freshness rules behave
consistently whenever the demo is run.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from app.schemas.domain import (
    DataMode,
    Facility,
    FacilityType,
    ProviderIntegration,
    RawSlot,
    ServiceType,
    SourceSlotStatus,
)

TORONTO_TZ = ZoneInfo("America/Toronto")
DEFAULT_SEED = 20261016
S = ServiceType

STD_IMAGING = "standard_imaging_requisition"
STD_LAB = "standard_lab_requisition"
REFERRAL = "specialist_referral_letter"

INTEGRATIONS: list[ProviderIntegration] = [
    ProviderIntegration(id="INT-SYN-A", name="Synthetic Scheduling Feed A", adapter_type="synthetic_demo",
                        reliability=0.97, notes="Simulates a provider scheduling API with confirmed slots."),
    ProviderIntegration(id="INT-SYN-B", name="Synthetic Scheduling Feed B", adapter_type="synthetic_demo",
                        reliability=0.92, notes="Simulates a partner integration."),
    ProviderIntegration(id="INT-SYN-NORTH", name="Synthetic Northern Imaging API", adapter_type="synthetic_demo",
                        reliability=0.93, notes="Used by the 'Provider API Failure' scenario to simulate an outage."),
    ProviderIntegration(id="INT-SYN-LOWREL", name="Synthetic Low-Reliability Feed", adapter_type="synthetic_demo",
                        reliability=0.55, notes="Simulates a feed with poor historical accuracy."),
    ProviderIntegration(id="INT-SYN-PUBLIC", name="Synthetic Public Advertised Feed", adapter_type="synthetic_demo",
                        reliability=0.85, notes="Simulates an approved public feed that only advertises openings."),
]

_HOURS_STD = {"mon": "07:30-20:00", "tue": "07:30-20:00", "wed": "07:30-20:00", "thu": "07:30-20:00",
              "fri": "07:30-18:00", "sat": "08:00-14:00", "sun": "closed"}
_HOURS_HOSP = {d: "00:00-23:59" for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
_HOURS_CLINIC = {"mon": "09:00-17:00", "tue": "09:00-17:00", "wed": "09:00-19:00", "thu": "09:00-17:00",
                 "fri": "09:00-16:00", "sat": "closed", "sun": "closed"}

# Hand-crafted anchors so the "90-Day MRI" scenario is reproducible around downtown Toronto.
# (id, name, type, network, city, neighbourhood, lat, lon, services, funding, formats, integration, extra)
_ANCHORS = [
    ("FAC-001", "Harbourline Imaging Centre (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Toronto", "Downtown", 43.6420, -79.4080, [S.MRI, S.CT, S.ULTRASOUND, S.XRAY], "public_demo",
     [STD_IMAGING], "INT-SYN-A", {"transit_score": 95, "parking": False}),
    ("FAC-002", "Riverdale Diagnostic Imaging (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Toronto", "East York", 43.7012, -79.3405, [S.MRI, S.ULTRASOUND, S.XRAY], "public_demo",
     [STD_IMAGING], "INT-SYN-A", {"transit_score": 80}),
    ("FAC-003", "Northgate MRI & CT Clinic (Demo)", FacilityType.IMAGING_CENTRE, "Demo Northern Imaging Group",
     "Toronto", "North York", 43.7766, -79.4153, [S.MRI, S.CT], "public_demo",
     [STD_IMAGING], "INT-SYN-NORTH", {"transit_score": 85}),
    ("FAC-004", "Bayfield Advanced Imaging (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Markham", "Unionville", 43.8430, -79.3290, [S.MRI, S.CT, S.ULTRASOUND], "public_demo",
     [STD_IMAGING], "INT-SYN-PUBLIC", {"transit_score": 45}),
    ("FAC-005", "Lakeshore Health Network Imaging (Demo)", FacilityType.HOSPITAL, "Demo Lakeshore Health Network",
     "Toronto", "Etobicoke", 43.6460, -79.5150, [S.MRI, S.CT, S.ULTRASOUND, S.XRAY, S.MAMMOGRAPHY], "public_demo",
     ["network_form:Demo Lakeshore Health Network"], "INT-SYN-B", {"transit_score": 60}),
    ("FAC-006", "Summitview Private Imaging (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Vaughan", "Concord", 43.7990, -79.4900, [S.MRI, S.CT], "private_pay_demo",
     [STD_IMAGING], "INT-SYN-A", {"transit_score": 30}),
    ("FAC-007", "Willowmere Imaging Clinic (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Toronto", "Scarborough", 43.7700, -79.2700, [S.MRI, S.ULTRASOUND, S.XRAY, S.MAMMOGRAPHY], "public_demo",
     [STD_IMAGING], "INT-SYN-B", {"transit_score": 70}),
    ("FAC-008", "Pinecrest Imaging (Demo)", FacilityType.IMAGING_CENTRE, "Independent (Demo)",
     "Toronto", "Midtown", 43.7040, -79.3980, [S.MRI, S.XRAY], "public_demo",
     [STD_IMAGING], "INT-SYN-LOWREL", {"transit_score": 90}),
]

# Explicit slot plans for anchors: (facility, service, day_offset, hour, source_status, verified_hours_ago, integration)
_ANCHOR_SLOTS = [
    ("FAC-001", S.MRI, 90, 9, SourceSlotStatus.CONFIRMED_BY_FEED, 1.0, None),
    ("FAC-001", S.MRI, 96, 14, SourceSlotStatus.CONFIRMED_BY_FEED, 1.0, None),
    ("FAC-002", S.MRI, 12, 10, SourceSlotStatus.CONFIRMED_BY_FEED, 0.5, None),
    ("FAC-002", S.MRI, 19, 15, SourceSlotStatus.CONFIRMED_BY_FEED, 0.5, None),
    ("FAC-003", S.MRI, 5, 8, SourceSlotStatus.CONFIRMED_BY_FEED, 2.0, None),
    ("FAC-003", S.MRI, 9, 13, SourceSlotStatus.CONFIRMED_BY_FEED, 2.0, None),
    ("FAC-003", S.CT, 4, 11, SourceSlotStatus.CONFIRMED_BY_FEED, 2.0, None),
    ("FAC-004", S.MRI, 3, 16, SourceSlotStatus.ADVERTISED, 3.0, None),
    ("FAC-004", S.MRI, 3, 16, SourceSlotStatus.ADVERTISED, 3.0, "INT-SYN-PUBLIC"),  # duplicate record
    ("FAC-004", S.CT, 6, 9, SourceSlotStatus.ADVERTISED, 3.0, None),
    ("FAC-005", S.MRI, 7, 12, SourceSlotStatus.CONFIRMED_BY_FEED, 1.5, None),
    ("FAC-006", S.MRI, 2, 18, SourceSlotStatus.CONFIRMED_BY_FEED, 0.5, None),
    ("FAC-007", S.MRI, 15, 10, SourceSlotStatus.CALL_TO_CONFIRM, 4.0, None),
    ("FAC-007", S.MRI, 21, 9, SourceSlotStatus.CONFIRMED_BY_FEED, 30.0, None),  # stale
    ("FAC-008", S.MRI, 4, 7, SourceSlotStatus.CONFIRMED_BY_FEED, 1.0, None),  # low-reliability source
    ("FAC-008", S.MRI, -2, 10, SourceSlotStatus.CONFIRMED_BY_FEED, 1.0, None),  # expired
    ("FAC-002", S.MRI, 30, 11, SourceSlotStatus.BOOKED, 0.5, None),
]

_PREFIXES = ["Maplewyn", "Cedarlune", "Brightvale", "Ashgrove", "Stonebridge", "Elmhurst", "Fernwood", "Glenmoor",
             "Hollyridge", "Ironwood", "Juniper Bay", "Kingsmere", "Larchfield", "Meadowcrest", "Northwind",
             "Orchard Hill", "Pebblecreek", "Quarry Lane", "Rosemont", "Silverbirch", "Thornbury", "Upland",
             "Valewood", "Westbrook", "Yarrowdale", "Zephyr Point", "Amberly", "Birchmount", "Clearwater", "Driftwood"]

_TYPE_PROFILES = {
    FacilityType.IMAGING_CENTRE: ("Imaging", [S.ULTRASOUND, S.XRAY, S.MRI, S.CT, S.MAMMOGRAPHY], _HOURS_STD),
    FacilityType.LABORATORY: ("Medical Laboratory", [S.BLOOD_TEST, S.URINE_TEST, S.LAB_INVESTIGATION], _HOURS_STD),
    FacilityType.FAMILY_CLINIC: ("Family Health Clinic", [S.FAMILY_PHYSICIAN], _HOURS_CLINIC),
    FacilityType.SPECIALIST_CLINIC: ("Specialist Consultation Clinic", [S.SPECIALIST], _HOURS_CLINIC),
    FacilityType.HOSPITAL: ("Community Hospital", [S.MRI, S.CT, S.ULTRASOUND, S.XRAY, S.BLOOD_TEST,
                                                    S.LAB_INVESTIGATION, S.SPECIALIST], _HOURS_HOSP),
}

_CITY_POINTS = [
    ("Toronto", "Downtown", 43.6532, -79.3832), ("Toronto", "North York", 43.7615, -79.4111),
    ("Toronto", "Scarborough", 43.7731, -79.2578), ("Toronto", "Etobicoke", 43.6205, -79.5132),
    ("Toronto", "East York", 43.6910, -79.3280), ("Mississauga", "City Centre", 43.5890, -79.6441),
    ("Brampton", "Downtown", 43.7315, -79.7624), ("Markham", "Markham Centre", 43.8561, -79.3370),
    ("Vaughan", "Woodbridge", 43.8372, -79.5083), ("Richmond Hill", "Centre", 43.8828, -79.4403),
    ("Oakville", "Downtown", 43.4675, -79.6877), ("Pickering", "City Centre", 43.8384, -79.0868),
    ("Ajax", "Central", 43.8509, -79.0204), ("Oshawa", "Downtown", 43.8971, -78.8658),
    ("Newmarket", "Central", 44.0592, -79.4613), ("Burlington", "Downtown", 43.3255, -79.7990),
    ("Hamilton", "Downtown", 43.2557, -79.8711), ("Milton", "Central", 43.5183, -79.8774),
    ("Barrie", "Downtown", 44.3894, -79.6903),
]

_PROC_TYPES = ([FacilityType.IMAGING_CENTRE] * 9 + [FacilityType.LABORATORY] * 10 + [FacilityType.FAMILY_CLINIC] * 6
               + [FacilityType.SPECIALIST_CLINIC] * 5 + [FacilityType.HOSPITAL] * 3)


@dataclass
class SyntheticDataset:
    generated_at: datetime
    seed: int
    facilities: list[Facility]
    integrations: list[ProviderIntegration]
    slots: list[RawSlot]

    def facility(self, facility_id: str) -> Facility | None:
        return next((f for f in self.facilities if f.id == facility_id), None)

    def integration(self, integration_id: str) -> ProviderIntegration | None:
        return next((i for i in self.integrations if i.id == integration_id), None)


def _local_to_utc(now_local: datetime, day_offset: int, hour: int, minute: int = 0) -> datetime:
    d = (now_local + timedelta(days=day_offset)).date()
    return datetime.combine(d, time(hour, minute), tzinfo=TORONTO_TZ).astimezone(UTC)


def _make_facility(fid: str, name: str, ftype: FacilityType, network: str, city: str, hood: str, lat: float,
                   lon: float, services: list[ServiceType], funding: str, formats: list[str], integration: str,
                   n: int, extra: dict | None = None) -> Facility:
    extra = extra or {}
    hours = _TYPE_PROFILES[ftype][2]
    referral_for = [s for s in services if s == S.SPECIALIST]
    capability = "online_handoff" if n % 3 != 2 else "phone_only"
    return Facility(
        id=fid, name=name, facility_type=ftype, network=network, city=city, neighbourhood=hood,
        address=f"{100 + n * 7} Demo Street (synthetic address)", postal_code="X0X 0X0",
        latitude=round(lat, 5), longitude=round(lon, 5), phone=f"416-555-01{n % 100:02d}",
        booking_url=f"https://booking.{fid.lower()}.medaccess-demo.invalid/" if capability == "online_handoff" else None,
        booking_capability=capability, services=services,
        wheelchair_accessible=extra.get("wheelchair", n % 5 != 3), transit_score=extra.get("transit_score", 50),
        parking=extra.get("parking", True), hours=hours, funding=funding, accepted_requisition_formats=formats,
        referral_required_for=referral_for, integration_id=integration, data_mode=DataMode.SYNTHETIC,
    )


def generate_dataset(now: datetime | None = None, seed: int = DEFAULT_SEED) -> SyntheticDataset:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    now_local = now.astimezone(TORONTO_TZ)
    rng = random.Random(seed)
    facilities: list[Facility] = []
    slots: list[RawSlot] = []

    for i, (a_id, a_name, a_type, a_net, a_city, a_hood, a_lat, a_lon, a_svcs, a_fund, a_fmts, a_integ, a_extra) in \
            enumerate(_ANCHORS, start=1):
        facilities.append(_make_facility(a_id, a_name, a_type, a_net, a_city, a_hood, a_lat, a_lon, a_svcs, a_fund,
                                         a_fmts, a_integ, i, a_extra))
    fac_by_id = {f.id: f for f in facilities}
    for j, (fid, svc, days, hour, status, age_h, slot_integ) in enumerate(_ANCHOR_SLOTS):
        f = fac_by_id[fid]
        slots.append(RawSlot(
            slot_id=f"SLOT-{fid[4:]}-{j:03d}", facility_id=fid, service=svc,
            start_utc=_local_to_utc(now_local, days, hour), source_status=status,
            source_id=slot_integ or f.integration_id, last_verified_at=now - timedelta(hours=age_h)))

    # Procedurally generated facilities across the GTA.
    integ_cycle = ["INT-SYN-A", "INT-SYN-B", "INT-SYN-A", "INT-SYN-PUBLIC", "INT-SYN-B", "INT-SYN-LOWREL"]
    for k, ftype in enumerate(_PROC_TYPES):
        n = len(facilities) + 1
        city, hood, clat, clon = _CITY_POINTS[k % len(_CITY_POINTS)]
        ang, dist_km = rng.uniform(0, 2 * math.pi), rng.uniform(0.3, 4.5)
        lat = clat + (dist_km / 111.0) * math.sin(ang)
        lon = clon + (dist_km / (111.0 * math.cos(math.radians(clat)))) * math.cos(ang)
        label, pool, _ = _TYPE_PROFILES[ftype]
        if ftype == FacilityType.IMAGING_CENTRE:
            services = sorted(set(rng.sample(pool, rng.randint(2, 4))), key=lambda s: s.value)
        else:
            services = list(pool)
        funding = "private_pay_demo" if rng.random() < 0.12 else "public_demo"
        formats: list[str] = []
        if any(s in services for s in (S.MRI, S.CT, S.ULTRASOUND, S.XRAY, S.MAMMOGRAPHY)):
            formats.append(STD_IMAGING)
        if any(s in services for s in (S.BLOOD_TEST, S.URINE_TEST, S.LAB_INVESTIGATION)):
            formats.append(STD_LAB)
        if S.SPECIALIST in services:
            formats.append(REFERRAL)
        network = "Independent (Demo)"
        if ftype == FacilityType.HOSPITAL:
            network = f"Demo {city} Regional Health"
            formats = [f"network_form:{network}"] + formats
        name = f"{_PREFIXES[k % len(_PREFIXES)]} {label} (Demo)"
        integ = integ_cycle[k % len(integ_cycle)]
        fid = f"FAC-{n:03d}"
        f = _make_facility(fid, name, ftype, network, city, hood, lat, lon, services, funding, formats, integ, n,
                           {"transit_score": rng.randint(20, 95), "parking": rng.random() > 0.3})
        facilities.append(f)
        for svc in services:
            base_wait = {S.MRI: 45, S.CT: 25, S.ULTRASOUND: 14, S.XRAY: 3, S.MAMMOGRAPHY: 20, S.BLOOD_TEST: 1,
                         S.URINE_TEST: 1, S.LAB_INVESTIGATION: 3, S.FAMILY_PHYSICIAN: 7, S.SPECIALIST: 60}[svc]
            for m in range(rng.randint(2, 4)):
                days = max(0, int(rng.gauss(base_wait, base_wait * 0.5))) + m * rng.randint(1, 5)
                roll = rng.random()
                if integ == "INT-SYN-PUBLIC":
                    status = SourceSlotStatus.ADVERTISED
                elif roll < 0.68:
                    status = SourceSlotStatus.CONFIRMED_BY_FEED
                elif roll < 0.83:
                    status = SourceSlotStatus.ADVERTISED
                elif roll < 0.95:
                    status = SourceSlotStatus.CALL_TO_CONFIRM
                else:
                    status = SourceSlotStatus.BOOKED
                age = rng.choice([0.25, 0.5, 1, 2, 3, 5, 8, 26])
                slots.append(RawSlot(
                    slot_id=f"SLOT-{fid[4:]}-{svc.value[:3]}-{m}", facility_id=fid, service=svc,
                    start_utc=_local_to_utc(now_local, days + 1, rng.choice([8, 9, 10, 11, 13, 14, 15, 16]),
                                            rng.choice([0, 15, 30, 45])),
                    source_status=status, source_id=integ, last_verified_at=now - timedelta(hours=age)))

    # Data-quality fixtures: a slot with a missing timestamp and one referencing a service the facility lacks.
    slots.append(RawSlot(slot_id="SLOT-DQ-NOTIME", facility_id="FAC-002", service=S.MRI, start_utc=None,
                         source_status=SourceSlotStatus.CONFIRMED_BY_FEED, source_id="INT-SYN-A",
                         last_verified_at=now))
    slots.append(RawSlot(slot_id="SLOT-DQ-WRONGSVC", facility_id="FAC-008", service=S.CT,
                         start_utc=_local_to_utc(now_local, 2, 10), source_status=SourceSlotStatus.CONFIRMED_BY_FEED,
                         source_id="INT-SYN-LOWREL", last_verified_at=now))

    return SyntheticDataset(generated_at=now, seed=seed, facilities=facilities, integrations=list(INTEGRATIONS),
                            slots=slots)


@lru_cache(maxsize=4)
def _cached(hour_bucket: str, seed: int) -> SyntheticDataset:
    return generate_dataset(datetime.fromisoformat(hour_bucket), seed)


def current_dataset(seed: int = DEFAULT_SEED) -> SyntheticDataset:
    """Dataset anchored to the current UTC hour (stable within an hour, reproducible across runs)."""
    bucket = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return _cached(bucket.isoformat(), seed)


def export_dataset(path: Path, now: datetime | None = None) -> Path:
    ds = generate_dataset(now)
    payload = {
        "notice": "SYNTHETIC DEMONSTRATION DATA - fictional facilities and appointments. Not live availability.",
        "generated_at": ds.generated_at.isoformat(), "seed": ds.seed,
        "facilities": [f.model_dump(mode="json") for f in ds.facilities],
        "integrations": [i.model_dump(mode="json") for i in ds.integrations],
        "slots": [s.model_dump(mode="json") for s in ds.slots],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


if __name__ == "__main__":  # python -m app.services.synthetic
    out = export_dataset(Path(__file__).resolve().parents[3] / "data" / "synthetic" / "dataset_snapshot.json")
    print(f"wrote {out}")
