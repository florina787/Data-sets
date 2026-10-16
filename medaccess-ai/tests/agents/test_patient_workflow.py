"""LangGraph patient workflow: happy path, branches, approvals, recovery, idempotency."""

from datetime import UTC, datetime

import pytest

from app.governance import approvals, builds
from app.services import booking as booking_svc
from app.services import notifications
from app.services.workflows import SearchParams, get_state, resume, start_search

NOW = datetime(2026, 10, 16, 14, 0, tzinfo=UTC)
U = "usr-patient-demo"
pytestmark = pytest.mark.agents


def mri(**kw):
    base = dict(service="MRI", location="Toronto", radius_km=25, existing_appointment_days=90,
                requisition_status="HAS_REQUISITION")
    base.update(kw)
    return SearchParams(**base)


def nodes(r):
    return [t["node"] for t in r["agent_trace"]]


def test_happy_path_executes_full_graph():
    r = start_search(mri(), U, "patient", free_text="I need an MRI", now=NOW)
    assert r["workflow_status"] == "COMPLETED" and not r["errors"]
    for n in ("intake", "clinical_safety", "service_classification", "facility_discovery", "geospatial",
              "availability_search", "data_quality", "availability_verification", "eligibility", "wait_time",
              "recommendation", "patient_review", "audit"):
        assert n in nodes(r)
    top = r["recommendations"][0]
    assert top["tier"] == "CONFIRMED_ALTERNATIVE" and top["facility_id"] == "FAC-003" and top["days_until"] == 5
    assert r["wait_summary"]["potential_days_saved"] == 85
    assert r["notice"].startswith("DEMONSTRATION DATA")
    assert all(rec["display_status"] == "DEMO_SIMULATED" for rec in r["recommendations"])
    assert {"source_id", "kind", "title"} <= set(r["source_references"][0])


def test_unverified_never_ranked_above_confirmed():
    r = start_search(mri(), U, "patient", now=NOW)
    tiers = [x["tier"] for x in r["recommendations"]]
    assert tiers == sorted(tiers, key=lambda t: t != "CONFIRMED_ALTERNATIVE")
    for x in r["recommendations"]:
        if x["tier"] == "CONFIRMED_ALTERNATIVE":
            assert x["verification_status"] == "VERIFIED_AVAILABLE"


def test_emergency_branch_skips_search():
    r = start_search(mri(), U, "patient", free_text="I have sudden severe headache and trouble speaking", now=NOW)
    assert r["workflow_status"] == "SAFETY_INTERRUPTED"
    assert "facility_discovery" not in nodes(r) and "safety_interruption" in nodes(r)
    assert "911" in r["explanation"]


def test_missing_input_branch():
    r = start_search(SearchParams(service="MRI"), U, "patient", now=NOW)
    assert r["workflow_status"] == "NEEDS_INPUT" and r["missing_fields"] == ["location"]


def test_unknown_service_needs_input():
    r = start_search(SearchParams(service="tarot reading", location="Toronto"), U, "patient", now=NOW)
    assert r["workflow_status"] == "NEEDS_INPUT"


def test_provider_outage_recovery_marks_source_unavailable():
    r = start_search(mri(scenario="provider_outage"), U, "patient", now=NOW)
    assert "recovery" in nodes(r) and r["unavailable_sources"] == ["INT-SYN-NORTH"]
    assert r["workflow_status"] == "COMPLETED"
    card = next(c for c in r["facility_cards"] if c["facility"]["id"] == "FAC-003")
    assert card["availability_state"] == "UNKNOWN" and card["facility"]["phone"]
    assert all(x["facility_id"] != "FAC-003" for x in r["recommendations"])


def test_flaky_provider_recovers_with_retry():
    r = start_search(mri(scenario="provider_flaky"), U, "patient", now=NOW)
    assert not r["unavailable_sources"] and r["retry_count"] >= 1
    assert any(x["facility_id"] == "FAC-003" for x in r["recommendations"])


def test_no_result_expansion_loop():
    r = start_search(mri(radius_km=2), U, "patient", now=NOW)
    assert r["workflow_status"] == "AWAITING_PATIENT_DECISION" and r["paused_at"] == ["expansion_approval"]
    q = r["pending_question"]
    approvals.decide(q["approval_id"], "APPROVED", U, "patient")
    r2 = resume(r["workflow_id"], {"decision": "APPROVED", "radius_km": 10, "approval_id": q["approval_id"]}, U,
                "patient")
    assert r2["workflow_status"] == "COMPLETED" and r2["radius_km"] == 10 and r2["expansions"] == 1
    assert nodes(r2).count("facility_discovery") == 2  # search repeated


def test_expansion_declined():
    r = start_search(mri(radius_km=2), U, "patient", now=NOW)
    r2 = resume(r["workflow_id"], {"decision": "REJECTED", "approval_id": r["approval_id"]}, U, "patient")
    assert r2["workflow_status"] == "COMPLETED" and r2["radius_km"] == 2


def test_requisition_not_accepted_excluded():
    r = start_search(mri(), U, "patient", now=NOW)
    assert all(x["facility_id"] != "FAC-005" for x in r["recommendations"])
    el = next(e for e in r["eligibility_results"] if e["facility_id"] == "FAC-005")
    assert el["status"] == "INELIGIBLE"


def _book(slot="SLOT-003-004", key=None, consent=True):
    return start_search(mri(request_booking=True, selected_slot_id=slot, patient_consent=consent,
                            idempotency_key=key), U, "patient", now=NOW)


def test_booking_requires_approval_and_never_fabricates_confirmation():
    notifications.set_consent(U, "notifications", True)
    r = _book(key="test-key-approve-0001")
    assert r["workflow_status"] == "AWAITING_APPROVAL" and r["paused_at"] == ["human_approval"]
    assert booking_svc.get(r["booking"]["id"])["status"] == "PENDING_APPROVAL"
    approvals.decide(r["approval_id"], "APPROVED", U, "patient")
    r2 = resume(r["workflow_id"], {"decision": "APPROVED", "approval_id": r["approval_id"]}, U, "patient")
    assert r2["booking_status"] == "HANDOFF_PREPARED"
    b = booking_svc.get(r["booking"]["id"])
    assert b["status"] == "HANDOFF_PREPARED" and not b["is_confirmed_booking"]
    assert b["handoff"]["confirmation_status"] == "NOT_CONFIRMED" and "not a booking" in b["handoff"]["disclaimer"]
    assert r2["notification"]["sent"] is True
    assert "confirmation_verification" in nodes(r2)


def test_booking_rejected():
    r = _book(key="test-key-reject-0001")
    r2 = resume(r["workflow_id"], {"decision": "REJECTED", "approval_id": r["approval_id"]}, U, "patient")
    assert r2["workflow_status"] == "REJECTED" and "booking_handoff" not in nodes(r2)


def test_booking_resume_with_wrong_approval_id_refused():
    r = _book(key="test-key-wrongid-0001")
    r2 = resume(r["workflow_id"], {"decision": "APPROVED", "approval_id": "APR-forged"}, U, "patient")
    assert r2["booking_status"] == "FAILED" and "booking_handoff" not in nodes(r2)


def test_booking_idempotency():
    a = _book(key="test-key-idem-0001")
    b = _book(key="test-key-idem-0001")
    assert a["booking"]["id"] == b["booking"]["id"] and a["approval_id"] == b["approval_id"]


def test_booking_needs_consent():
    r = _book(key="test-key-consent-0001", consent=False)
    assert r["workflow_status"] == "CONSENT_REQUIRED"


def test_booking_unknown_slot():
    r = _book(slot="SLOT-NOPE", key="test-key-noslot-0001")
    assert r["workflow_status"] == "BOOKING_NOT_POSSIBLE"


def test_state_contains_no_free_text():
    secret = "my name is Jane Doe and my health card is 1234-567-890-AB"
    r = start_search(mri(), U, "patient", free_text=secret, now=NOW)
    st = get_state(r["workflow_id"])
    assert "Jane" not in str(st) and "1234-567-890" not in str(st)


def test_defective_build_affects_workflow():
    builds.deploy("1.5.0", "demo-production", "test", approval_id="TEST")
    r = start_search(mri(), U, "patient", now=NOW)
    assert r["build_version"] == "1.5.0"
    assert r["recommendations"][0]["facility_id"] == "FAC-004"  # advertised slot wrongly "verified"
