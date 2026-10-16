"""Unit tests for deterministic engines: geo, verification, eligibility, ranking, wait time."""

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.domain import AvailabilityStatus as A
from app.schemas.domain import EligibilityStatus as E
from app.schemas.domain import RawSlot, RequisitionStatus, ServiceType, SourceSlotStatus
from app.services import eligibility as elig
from app.services import geo
from app.services import ranking as rk
from app.services.gazetteer import nearest_supported_radius, resolve_location
from app.services.synthetic import generate_dataset
from app.services.verification import dedupe_slots, verify_slot

NOW = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def ds():
    return generate_dataset(NOW)


def slot(ds, sid):
    return next(s for s in ds.slots if s.slot_id == sid)


def v(ds, sid, mapping="correct"):
    s = slot(ds, sid)
    return verify_slot(s, ds.facility(s.facility_id), ds.integration(s.source_id), NOW, mapping=mapping)


def test_dataset_is_reproducible():
    a, b = generate_dataset(NOW), generate_dataset(NOW)
    assert [f.model_dump() for f in a.facilities] == [f.model_dump() for f in b.facilities]
    assert [s.model_dump() for s in a.slots] == [s.model_dump() for s in b.slots]


def test_dataset_is_clearly_fictional(ds):
    assert all(f.is_synthetic and "(Demo)" in f.name for f in ds.facilities)
    assert all("555-01" in f.phone for f in ds.facilities)
    assert all(f.booking_url is None or ".invalid/" in f.booking_url for f in ds.facilities)


def test_haversine_known_distance():
    assert geo.haversine_km(43.6532, -79.3832, 43.6532, -79.3832) == 0
    assert 21 < geo.haversine_km(43.6532, -79.3832, 43.5890, -79.6441) < 22.5


def test_haversine_rejects_invalid_coordinates():
    with pytest.raises(ValueError):
        geo.haversine_km(95, 0, 0, 0)


@pytest.mark.parametrize("radius", [2, 3, 5, 10, 25, 50, 100])
def test_radius_filter_respects_every_supported_radius(ds, radius):
    res = geo.within_radius(ds.facilities, 43.6532, -79.3832, radius)
    assert all(g.straight_km <= radius + 0.01 for _, g in res)
    assert [g.straight_km for _, g in res] == sorted(g.straight_km for _, g in res)


def test_radius_boundary_inclusive(ds):
    f = ds.facility("FAC-002")
    d = geo.haversine_km(43.6532, -79.3832, f.latitude, f.longitude)
    assert geo.within_radius([f], 43.6532, -79.3832, d)
    assert not geo.within_radius([f], 43.6532, -79.3832, d - 0.001)


def test_travel_estimates_are_labelled(ds):
    g = geo.geo_for(ds.facility("FAC-001"), 43.6532, -79.3832)
    assert "estimate" in g.method and g.est_driving_km >= g.straight_km


@pytest.mark.parametrize("sid,expected", [
    ("SLOT-003-004", A.VERIFIED_AVAILABLE), ("SLOT-004-007", A.ADVERTISED_UNVERIFIED),
    ("SLOT-007-012", A.CONTACT_REQUIRED), ("SLOT-007-013", A.ADVERTISED_UNVERIFIED),
    ("SLOT-008-014", A.ADVERTISED_UNVERIFIED), ("SLOT-008-015", A.UNAVAILABLE),
    ("SLOT-002-016", A.UNAVAILABLE), ("SLOT-DQ-NOTIME", A.UNKNOWN), ("SLOT-DQ-WRONGSVC", A.UNAVAILABLE),
])
def test_verification_status_mapping(ds, sid, expected):
    assert v(ds, sid).verification_status == expected


def test_synthetic_slots_display_as_demo(ds):
    r = v(ds, "SLOT-003-004")
    assert r.display_status == A.DEMO_SIMULATED and r.is_synthetic


def test_defective_mapping_reproduces_demo_defect(ds):
    assert v(ds, "SLOT-004-007", "defect_unverified_as_confirmed").verification_status == A.VERIFIED_AVAILABLE


def test_unknown_facility_is_unknown(ds):
    s = slot(ds, "SLOT-003-004")
    assert verify_slot(s, None, ds.integration(s.source_id), NOW).verification_status == A.UNKNOWN


def test_unauthorized_source_is_unknown(ds):
    s = slot(ds, "SLOT-003-004")
    integ = ds.integration(s.source_id).model_copy(update={"authorized": False})
    assert verify_slot(s, ds.facility(s.facility_id), integ, NOW).verification_status == A.UNKNOWN


def test_local_time_conversion(ds):
    r = v(ds, "SLOT-003-004")
    assert r.start_local.endswith("T08:00-04:00")


def test_dedupe_keeps_most_recent():
    t = NOW + timedelta(days=3)
    a = RawSlot(slot_id="a", facility_id="F", service=ServiceType.MRI, start_utc=t, source_id="X",
                source_status=SourceSlotStatus.ADVERTISED, last_verified_at=NOW - timedelta(hours=5))
    b = a.model_copy(update={"slot_id": "b", "last_verified_at": NOW - timedelta(hours=1)})
    kept, dropped = dedupe_slots([a, b])
    assert [k.slot_id for k in kept] == ["b"] and dropped == ["a"]


def test_eligibility_rules(ds):
    std = elig.PatientCriteria(requisition_status=RequisitionStatus.HAS_REQUISITION)
    assert elig.evaluate(ds.facility("FAC-002"), ServiceType.MRI, std).status == E.ELIGIBLE
    assert elig.evaluate(ds.facility("FAC-005"), ServiceType.MRI, std).status == E.INELIGIBLE
    net = elig.PatientCriteria(requisition_status=RequisitionStatus.HAS_REQUISITION,
                               requisition_format="network_form:Demo Lakeshore Health Network")
    assert elig.evaluate(ds.facility("FAC-005"), ServiceType.MRI, net).status == E.ELIGIBLE
    none = elig.PatientCriteria(requisition_status=RequisitionStatus.NO_REQUISITION)
    r = elig.evaluate(ds.facility("FAC-002"), ServiceType.MRI, none)
    assert r.status == E.NEEDS_REVIEW and any("clinician" in a for a in r.actions)
    assert elig.evaluate(ds.facility("FAC-006"), ServiceType.MRI, std).status == E.INELIGIBLE
    pp = std.model_copy(update={"include_private_pay": True})
    assert elig.evaluate(ds.facility("FAC-006"), ServiceType.MRI, pp).status == E.ELIGIBLE_WITH_CONDITIONS


def test_coverage_is_never_guaranteed(ds):
    for f in ds.facilities:
        for s in f.services:
            note = elig.evaluate(f, s, elig.PatientCriteria()).coverage_note.lower()
            assert "guarantee" not in note or "not guaranteed" in note


def test_days_until_and_saved():
    assert rk.days_until(NOW + timedelta(days=5), NOW) == 5
    assert rk.days_saved(90, 5) == 85
    assert rk.days_saved(5, 90) == 0
    assert rk.days_saved(None, 5) is None


def test_location_resolution():
    assert resolve_location("Toronto").precision == "city_centroid"
    loc = resolve_location("m5v 2t6")
    assert loc.query == "M5V" and loc.precision == "fsa_centroid"  # full postal code not retained
    assert resolve_location("Atlantis") is None
    assert nearest_supported_radius(7) == 10 and nearest_supported_radius(500) == 100
