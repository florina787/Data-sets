"""QA test generation and execution (DETERMINISTIC).

Test cases are generated from the structured requirement's parameters, focusing on
exact boundaries (visit 10 / visit 11, annual maximum edges, effective dates) and
negative paths. Executable cases are *run* against any ruleset through the same
deterministic engine used in production simulation — they are real, not decorative.
"""

from __future__ import annotations

from datetime import date

from app.claims.adjudicator import adjudicate_claim
from app.claims.rulesets import RuleSet
from app.models.domain import BenefitType, Claim, ClaimContext, ClaimLine, Requirement, TestCase, TestResult

_DEFAULT_DATE = "2026-08-03"


def _case(test_id, title, category, given, expected, *, rule_id=None, req_id=None, critical=False) -> TestCase:
    return TestCase(test_id=test_id, title=title, category=category, given=given, expected=expected,
                    rule_id=rule_id, requirement_id=req_id, critical=critical)


def generate_test_cases(req: Requirement) -> list[TestCase]:
    p = req.parameters
    rid = req.requirement_id
    bt = req.benefit_type.value if req.benefit_type else BenefitType.PHYSIOTHERAPY.value
    pfx = f"TC-{rid}"
    cases: list[TestCase] = []
    n = 0

    def nid() -> str:
        nonlocal n
        n += 1
        return f"{pfx}-{n:03d}"

    base = {"benefit_type": bt, "plan_id": "NSH-GOLD", "billed": 100.0, "service_date": _DEFAULT_DATE}

    t = p.get("auth_threshold")
    if "AUTH_THRESHOLD_ADD" in req.facets and t is not None:
        cases += [
            _case(nid(), f"Boundary: visit {t} ({t - 1} prior completed) needs no authorization", "boundary",
                  {**base, "prior_completed": t - 1}, {"status": "APPROVED", "authorization_required": False},
                  rule_id="AUTH_RULE_184", req_id=rid, critical=True),
            _case(nid(), f"Boundary: visit {t + 1} ({t} prior completed) without authorization is denied", "boundary",
                  {**base, "prior_completed": t}, {"status": "DENIED", "reason_code": "AUTH_REQUIRED"},
                  rule_id="AUTH_RULE_184", req_id=rid, critical=True),
            _case(nid(), f"Visit {t + 1} with approved authorization is paid", "unit",
                  {**base, "prior_completed": t, "auth_present": True}, {"status": "APPROVED", "authorization_required": True},
                  rule_id="AUTH_RULE_184", req_id=rid, critical=True),
            _case(nid(), f"Cancelled visits excluded: {t - 1} completed + 3 cancelled needs no authorization", "boundary",
                  {**base, "prior_completed": t - 1, "prior_cancelled": 3},
                  {"status": "APPROVED", "authorization_required": False, "counted_visits": t - 1},
                  rule_id="AUTH_RULE_184", req_id=rid, critical=True),
            _case(nid(), f"Cancelled visits excluded: {t - 2} completed + {t} cancelled needs no authorization", "negative",
                  {**base, "prior_completed": t - 2, "prior_cancelled": t},
                  {"status": "APPROVED", "authorization_required": False},
                  rule_id="AUTH_RULE_184", req_id=rid, critical=True),
            _case(nid(), f"Visit {t + 6} without authorization is denied", "unit",
                  {**base, "prior_completed": t + 5}, {"status": "DENIED", "reason_code": "AUTH_REQUIRED"},
                  rule_id="AUTH_RULE_184", req_id=rid),
        ]
    if "BENEFIT_LIMIT_CHANGE" in req.facets:
        new, old = p["proposed_annual_max"], p["current_annual_max"]
        cases += [
            _case(nid(), f"Annual max boundary: ${new - 10:.2f} paid → $10.00 capped", "boundary",
                  {**base, "ytd_paid": new - 10, "prior_completed": 0},
                  {"status": "APPROVED", "reason_code": "PAID_CAPPED", "reimbursement_amount": 10.0},
                  rule_id="BEN_RULE_090", req_id=rid, critical=True),
            _case(nid(), f"Annual max reached: ${new:.2f} paid → denied", "boundary",
                  {**base, "ytd_paid": new}, {"status": "DENIED", "reason_code": "BENEFIT_MAX_REACHED"},
                  rule_id="BEN_RULE_090", req_id=rid, critical=True),
            _case(nid(), f"Old maximum no longer applies: ${old:.2f} paid → approved", "regression",
                  {**base, "ytd_paid": old}, {"status": "APPROVED"}, rule_id="BEN_RULE_090", req_id=rid),
        ]
    if req.facets:
        cases += [
            _case(nid(), "Reimbursement is 80% of allowed amount", "unit",
                  {**base, "billed": 100.0}, {"status": "APPROVED", "reimbursement_amount": 80.0},
                  rule_id="REIMB_RULE_050", req_id=rid),
            _case(nid(), "Billed above fee schedule is limited to allowed amount", "unit",
                  {**base, "billed": 500.0}, {"status": "APPROVED", "allowed_amount": 120.0 if bt == "PHYSIOTHERAPY" else None},
                  rule_id="REIMB_RULE_050", req_id=rid),
            _case(nid(), "Negative: member coverage terminated before service date", "negative",
                  {**base, "coverage_end": "2026-06-30"}, {"status": "DENIED", "reason_code": "MEMBER_INELIGIBLE"},
                  rule_id="ELIG_RULE_001", req_id=rid),
            _case(nid(), "Negative: service date one day before policy effective date", "boundary",
                  {**base, "service_date": "2025-12-31"}, {"status": "DENIED", "reason_code": "POLICY_NOT_EFFECTIVE"},
                  rule_id="EFF_RULE_005", req_id=rid),
            _case(nid(), "Boundary: service date on policy effective date is payable", "boundary",
                  {**base, "service_date": "2026-01-01"}, {"status": "APPROVED"}, rule_id="EFF_RULE_005", req_id=rid),
            _case(nid(), "Negative: suspended provider", "negative",
                  {**base, "provider_active": False}, {"status": "DENIED", "reason_code": "PROVIDER_INELIGIBLE"},
                  rule_id="PROV_RULE_020", req_id=rid),
            _case(nid(), "Negative: duplicate submission", "negative",
                  {**base, "is_duplicate": True}, {"status": "DENIED", "reason_code": "DUPLICATE"},
                  rule_id="DUP_RULE_030", req_id=rid),
            _case(nid(), "Negative: acupuncture not covered on Bronze plan", "negative",
                  {**base, "benefit_type": "ACUPUNCTURE", "plan_id": "NSH-BRONZE"},
                  {"status": "DENIED", "reason_code": "NOT_COVERED"}, rule_id="COV_RULE_010", req_id=rid),
            _case(nid(), "Regression: chiropractic $500 maximum unchanged", "regression",
                  {**base, "benefit_type": "CHIROPRACTIC", "ytd_paid": 500.0},
                  {"status": "DENIED", "reason_code": "BENEFIT_MAX_REACHED"}, rule_id="BEN_RULE_090", req_id=rid),
            _case(nid(), "Regression: chiropractic visit 12 needs no authorization", "regression",
                  {**base, "benefit_type": "CHIROPRACTIC", "prior_completed": 11},
                  {"status": "APPROVED", "authorization_required": False}, rule_id="AUTH_RULE_184", req_id=rid),
        ]
        cases += api_test_specs(rid, nid)
    return cases


def api_test_specs(rid: str, nid) -> list[TestCase]:
    """Generated API test *specifications* (PARTIAL: executed by tests/api, not by the executor)."""
    return [
        TestCase(test_id=nid(), title="API: POST /claims/adjudicate returns AUTH_REQUIRED for visit 11 without auth",
                 category="api", requirement_id=rid, rule_id="AUTH_RULE_184", executable=False,
                 given={"method": "POST", "path": "/claims/adjudicate", "ruleset_id": "RULESET_V2",
                        "context": {"prior_completed_visits": 10, "authorization_present": False}},
                 expected={"http_status": 200, "reason_code": "AUTH_REQUIRED"}),
        TestCase(test_id=nid(), title="API: invalid claim payload is rejected with 422", category="api",
                 requirement_id=rid, executable=False,
                 given={"method": "POST", "path": "/claims/adjudicate", "payload": {"claim": {"claim_id": "x"}}},
                 expected={"http_status": 422}),
    ]


def _build(given: dict) -> tuple[Claim, ClaimContext]:
    claim = Claim(
        claim_id="CLM-SYN-TEST", member_id="MBR-SYN-TEST", provider_id="PRV-SYN-TEST",
        plan_id=given.get("plan_id", "NSH-GOLD"), benefit_type=BenefitType(given.get("benefit_type", "PHYSIOTHERAPY")),
        service_date=date.fromisoformat(given.get("service_date", _DEFAULT_DATE)),
        lines=[ClaimLine(procedure_code="PT-97110", billed_amount=float(given.get("billed", 100.0)))],
    )
    ctx = ClaimContext(
        coverage_start=date.fromisoformat(given.get("coverage_start", "2024-01-01")),
        coverage_end=date.fromisoformat(given["coverage_end"]) if given.get("coverage_end") else None,
        provider_active=given.get("provider_active", True),
        prior_completed_visits=given.get("prior_completed", 0),
        prior_cancelled_visits=given.get("prior_cancelled", 0),
        authorization_present=given.get("auth_present", False),
        ytd_paid=given.get("ytd_paid", 0.0),
        is_duplicate=given.get("is_duplicate", False),
    )
    return claim, ctx


def run_test_cases(cases: list[TestCase], ruleset: RuleSet) -> list[TestResult]:
    results = []
    for tc in cases:
        if not tc.executable:
            continue
        claim, ctx = _build(tc.given)
        res = adjudicate_claim(claim, ctx, ruleset)
        actual = {"status": res.status.value, "reason_code": res.reason_code.value,
                  "authorization_required": res.authorization_required, "counted_visits": res.counted_visits,
                  "reimbursement_amount": res.reimbursement_amount, "allowed_amount": res.allowed_amount}
        passed = all(v is None or (abs(actual[k] - v) < 0.005 if isinstance(v, float) else actual[k] == v)
                     for k, v in tc.expected.items())
        results.append(TestResult(test_id=tc.test_id, title=tc.title, passed=passed, critical=tc.critical,
                                  expected=tc.expected, actual=actual, ruleset_id=ruleset.ruleset_id))
    return results


def summarize(results: list[TestResult]) -> dict:
    failed = [r for r in results if not r.passed]
    return {"total": len(results), "passed": len(results) - len(failed), "failed": len(failed),
            "critical_failed": sum(1 for r in failed if r.critical),
            "failed_ids": [r.test_id for r in failed]}


def regression_test_code(test_id: str, completed: int, cancelled: int, threshold: int, ruleset_id: str = "RULESET_V2_1") -> str:
    """Generate a runnable pytest regression test from a production failure (UC38)."""
    return f'''"""{test_id}: regression test generated by ClaimForge from a ClaimIQ production finding.

SYNTHETIC scenario reproduced from production evidence: a member with {completed} COMPLETED and
{cancelled} CANCELLED physiotherapy visits was denied AUTH_REQUIRED after release 2.4.
Policy P-01.3: cancelled visits do not count toward authorization thresholds.
"""
from datetime import date

from app.claims.adjudicator import adjudicate_claim
from app.claims.rulesets import get_ruleset
from app.models.domain import BenefitType, Claim, ClaimContext, ClaimLine


def test_{test_id.lower().replace("-", "_")}_cancelled_visits_not_counted():
    claim = Claim(claim_id="CLM-SYN-REG", member_id="MBR-SYN-REG", provider_id="PRV-SYN-REG",
                  plan_id="NSH-GOLD", benefit_type=BenefitType.PHYSIOTHERAPY, service_date=date(2026, 8, 3),
                  lines=[ClaimLine(procedure_code="PT-97110", billed_amount=100.0)])
    ctx = ClaimContext(prior_completed_visits={completed}, prior_cancelled_visits={cancelled},
                       authorization_present=False)
    result = adjudicate_claim(claim, ctx, get_ruleset("{ruleset_id}"))
    assert result.counted_visits == {completed}
    assert result.authorization_required is {completed >= threshold}
    assert result.status.value == "{"DENIED" if completed >= threshold else "APPROVED"}"
'''
