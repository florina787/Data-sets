"""Deterministic claims engine: eligibility, reimbursement, annual max, authorization boundaries."""

from datetime import date

import pytest

from app.claims.adjudicator import adjudicate_claim
from app.claims.rulesets import RULESET_V1, RULESET_V2, RULESET_V2_DEFECTIVE
from app.models.domain import BenefitType, Claim, ClaimContext, ClaimLine


def claim(benefit=BenefitType.PHYSIOTHERAPY, billed=100.0, plan="NSH-GOLD", day=date(2026, 8, 3)):
    return Claim(claim_id="CLM-SYN-T", member_id="MBR-SYN-T", provider_id="PRV-SYN-T", plan_id=plan,
                 benefit_type=benefit, service_date=day, lines=[ClaimLine(procedure_code="PT-97110", billed_amount=billed)])


def test_03_eligibility_rules_deterministic():
    ctx = ClaimContext(coverage_start=date(2024, 1, 1), coverage_end=date(2026, 6, 30))
    results = {adjudicate_claim(claim(), ctx, RULESET_V2).model_dump_json() for _ in range(5)}
    assert len(results) == 1  # identical every time
    r = adjudicate_claim(claim(), ctx, RULESET_V2)
    assert r.status.value == "DENIED" and r.reason_code.value == "MEMBER_INELIGIBLE" and not r.eligible
    assert adjudicate_claim(claim(), ClaimContext(provider_active=False), RULESET_V2).reason_code.value == "PROVIDER_INELIGIBLE"
    assert adjudicate_claim(claim(BenefitType.ACUPUNCTURE, plan="NSH-BRONZE"), ClaimContext(), RULESET_V2).reason_code.value == "NOT_COVERED"
    assert adjudicate_claim(claim(), ClaimContext(is_duplicate=True), RULESET_V2).reason_code.value == "DUPLICATE"
    assert adjudicate_claim(claim(day=date(2025, 12, 31)), ClaimContext(), RULESET_V2).reason_code.value == "POLICY_NOT_EFFECTIVE"
    assert adjudicate_claim(claim(day=date(2026, 1, 1)), ClaimContext(), RULESET_V2).status.value == "APPROVED"


def test_04_reimbursement_calculation_deterministic():
    r = adjudicate_claim(claim(billed=100.0), ClaimContext(), RULESET_V2)
    assert r.allowed_amount == 100.0 and r.reimbursement_amount == 80.0 and r.reason_code.value == "PAID"
    r = adjudicate_claim(claim(billed=500.0), ClaimContext(), RULESET_V2)
    assert r.allowed_amount == 120.0 and r.reimbursement_amount == 96.0  # fee schedule cap


def test_05_annual_benefit_maximum_enforced():
    v2_cap = adjudicate_claim(claim(), ClaimContext(ytd_paid=990.0), RULESET_V2)
    assert v2_cap.reason_code.value == "PAID_CAPPED" and v2_cap.reimbursement_amount == pytest.approx(10.0)
    assert adjudicate_claim(claim(), ClaimContext(ytd_paid=1000.0), RULESET_V2).reason_code.value == "BENEFIT_MAX_REACHED"
    assert adjudicate_claim(claim(), ClaimContext(ytd_paid=750.0), RULESET_V1).reason_code.value == "BENEFIT_MAX_REACHED"
    assert adjudicate_claim(claim(), ClaimContext(ytd_paid=750.0), RULESET_V2).status.value == "APPROVED"


def test_06_authorization_threshold_correct():
    assert not adjudicate_claim(claim(), ClaimContext(prior_completed_visits=15), RULESET_V1).authorization_required
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=15), RULESET_V2)
    assert r.authorization_required and r.reason_code.value == "AUTH_REQUIRED"
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=15, authorization_present=True), RULESET_V2)
    assert r.authorization_required and r.status.value == "APPROVED"


def test_07_visit_10_boundary():
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=9), RULESET_V2)  # this claim is visit 10
    assert not r.authorization_required and r.status.value == "APPROVED"


def test_08_visit_11_behaviour():
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=10), RULESET_V2)  # visit 11
    assert r.authorization_required and r.status.value == "DENIED" and r.reason_code.value == "AUTH_REQUIRED"
    assert r.rule_id == "AUTH_RULE_184"


def test_09_cancelled_visits_excluded_from_completed_count():
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=9, prior_cancelled_visits=3), RULESET_V2)
    assert r.counted_visits == 9 and not r.authorization_required and r.status.value == "APPROVED"


def test_10_defective_release_counts_cancelled_visits():
    r = adjudicate_claim(claim(), ClaimContext(prior_completed_visits=9, prior_cancelled_visits=3), RULESET_V2_DEFECTIVE)
    assert r.counted_visits == 12 and r.authorization_required and r.reason_code.value == "AUTH_REQUIRED"
    assert RULESET_V2_DEFECTIVE.synthetic_defect is True
