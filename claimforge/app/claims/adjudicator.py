"""Deterministic claims adjudication engine (NO LLM).

A single pure function, :func:`decide`, contains all adjudication logic. Both the
single-claim API (:func:`adjudicate_claim`) and the batch simulator
(:func:`adjudicate_frame`) call it, so there is exactly one implementation of the rules.

Rule order (first failing rule determines the denial):
  ELIG_RULE_001 → EFF_RULE_005 → PROV_RULE_020 → COV_RULE_010 → DUP_RULE_030 →
  VIS_RULE_070 → AUTH_RULE_184 → REIMB_RULE_050 → BEN_RULE_090
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Iterable

import pandas as pd

from app.claims import rules as R
from app.claims.rulesets import RuleSet
from app.models.domain import (
    AdjudicationResult,
    BenefitType,
    Claim,
    ClaimContext,
    ClaimStatus,
    ReasonCode,
)

PLAN_COVERAGE: dict[str, frozenset[BenefitType]] = {
    "NSH-BRONZE": frozenset({BenefitType.PHYSIOTHERAPY, BenefitType.CHIROPRACTIC}),
    "NSH-SILVER": frozenset({BenefitType.PHYSIOTHERAPY, BenefitType.CHIROPRACTIC, BenefitType.MASSAGE_THERAPY}),
    "NSH-GOLD": frozenset(set(BenefitType)),
}


@dataclass(frozen=True, slots=True)
class Decision:
    status: ClaimStatus
    reason: ReasonCode
    rule_id: str
    eligible: bool
    covered: bool
    auth_required: bool
    counted_visits: int
    allowed: float
    reimbursement: float


def _deny(reason: ReasonCode, *, eligible=True, covered=True, auth_required=False, counted=0, allowed=0.0) -> Decision:
    return Decision(ClaimStatus.DENIED, reason, R.REASON_TO_RULE[reason], eligible, covered,
                    auth_required, counted, allowed, 0.0)


def decide(
    ruleset: RuleSet,
    *,
    benefit_type: BenefitType,
    plan_id: str,
    service_day: int,
    coverage_start_day: int,
    coverage_end_day: int | None,
    provider_active: bool,
    is_duplicate: bool,
    prior_completed: int,
    prior_cancelled: int,
    auth_present: bool,
    billed: float,
    ytd_paid: float,
) -> Decision:
    """Adjudicate one claim. Dates are proleptic ordinals (``date.toordinal()``)."""
    # ELIG_RULE_001 — member coverage active on date of service
    if service_day < coverage_start_day or (coverage_end_day is not None and service_day > coverage_end_day):
        return _deny(ReasonCode.MEMBER_INELIGIBLE, eligible=False)
    # EFF_RULE_005 — policy effective date
    if service_day < ruleset.policy_effective_date.toordinal():
        return _deny(ReasonCode.POLICY_NOT_EFFECTIVE, eligible=False)
    # PROV_RULE_020 — provider eligibility
    if not provider_active:
        return _deny(ReasonCode.PROVIDER_INELIGIBLE)
    # COV_RULE_010 — benefit covered by plan
    covered_set = PLAN_COVERAGE.get(plan_id, frozenset())
    if benefit_type not in covered_set or benefit_type not in ruleset.benefits:
        return _deny(ReasonCode.NOT_COVERED, covered=False)
    rule = ruleset.benefits[benefit_type]
    # DUP_RULE_030 — duplicate submission
    if is_duplicate:
        return _deny(ReasonCode.DUPLICATE)
    # VIS_RULE_070 — visit limit (completed visits only, policy P-01.3)
    if rule.max_visits is not None and prior_completed >= rule.max_visits:
        return _deny(ReasonCode.VISIT_LIMIT_EXCEEDED, counted=prior_completed)
    # AUTH_RULE_184 — prior authorization threshold
    counted = prior_completed + (prior_cancelled if rule.count_cancelled_visits else 0)
    auth_required = rule.auth_after_completed_visits is not None and counted >= rule.auth_after_completed_visits
    if auth_required and not auth_present:
        return _deny(ReasonCode.AUTH_REQUIRED, auth_required=True, counted=counted)
    # REIMB_RULE_050 — allowed amount & reimbursement percentage
    allowed = round(min(billed, rule.per_visit_allowed_max), 2)
    raw = round(allowed * rule.reimbursement_pct, 2)
    # BEN_RULE_090 — annual maximum
    remaining = round(rule.annual_max - ytd_paid, 2)
    if remaining <= 0:
        return _deny(ReasonCode.BENEFIT_MAX_REACHED, auth_required=auth_required, counted=counted, allowed=allowed)
    paid = round(min(raw, remaining), 2)
    reason = ReasonCode.PAID if paid >= raw else ReasonCode.PAID_CAPPED
    return Decision(ClaimStatus.APPROVED, reason, R.REASON_TO_RULE[reason], True, True,
                    auth_required, counted, allowed, paid)


_EXPLANATIONS = {
    ReasonCode.PAID: "Paid at {pct:.0%} of allowed amount ${allowed:.2f}.",
    ReasonCode.PAID_CAPPED: "Paid ${paid:.2f}, limited by the remaining annual maximum of ${cap:.2f}.",
    ReasonCode.MEMBER_INELIGIBLE: "Member coverage not active on date of service (P-01.2).",
    ReasonCode.POLICY_NOT_EFFECTIVE: "Date of service precedes policy effective date (P-02.2).",
    ReasonCode.PROVIDER_INELIGIBLE: "Provider not eligible on date of service (P-12.1).",
    ReasonCode.NOT_COVERED: "Benefit not covered under plan (P-10.1).",
    ReasonCode.DUPLICATE: "Duplicate of a previously adjudicated claim (P-30.1).",
    ReasonCode.VISIT_LIMIT_EXCEEDED: "Annual visit limit reached ({counted} completed visits).",
    ReasonCode.AUTH_REQUIRED: "Prior authorization required: {counted} counted visits >= threshold; none on file (P-14.3/P-20.3).",
    ReasonCode.BENEFIT_MAX_REACHED: "Annual maximum of ${cap:.2f} already reached (P-14.2).",
}


def adjudicate_claim(claim: Claim, context: ClaimContext, ruleset: RuleSet) -> AdjudicationResult:
    """Adjudicate a single validated claim deterministically."""
    d = decide(
        ruleset,
        benefit_type=claim.benefit_type,
        plan_id=claim.plan_id,
        service_day=claim.service_date.toordinal(),
        coverage_start_day=context.coverage_start.toordinal(),
        coverage_end_day=context.coverage_end.toordinal() if context.coverage_end else None,
        provider_active=context.provider_active,
        is_duplicate=context.is_duplicate,
        prior_completed=context.prior_completed_visits,
        prior_cancelled=context.prior_cancelled_visits,
        auth_present=context.authorization_present,
        billed=claim.billed_amount,
        ytd_paid=context.ytd_paid,
    )
    rule = ruleset.benefits.get(claim.benefit_type)
    explanation = _EXPLANATIONS[d.reason].format(
        pct=rule.reimbursement_pct if rule else 0, allowed=d.allowed, paid=d.reimbursement,
        cap=rule.annual_max if rule else 0, counted=d.counted_visits,
    )
    return AdjudicationResult(
        claim_id=claim.claim_id, ruleset_id=ruleset.ruleset_id, eligible=d.eligible, covered=d.covered,
        authorization_required=d.auth_required, authorization_present=context.authorization_present,
        counted_visits=d.counted_visits, allowed_amount=d.allowed, reimbursement_amount=d.reimbursement,
        status=d.status, reason_code=d.reason, rule_id=d.rule_id, explanation=explanation,
    )


RulesetSelector = Callable[[int], RuleSet]


def _selector(ruleset_or_schedule: RuleSet | Iterable[tuple[date, RuleSet]]) -> tuple[RulesetSelector, list[RuleSet]]:
    """Return a function service_day -> ruleset. A schedule is [(effective_from, ruleset), ...]."""
    if isinstance(ruleset_or_schedule, RuleSet):
        rs = ruleset_or_schedule
        return (lambda _day: rs), [rs]
    schedule = sorted(((d.toordinal(), rs) for d, rs in ruleset_or_schedule), key=lambda x: x[0])
    if not schedule:
        raise ValueError("empty ruleset schedule")

    def pick(day: int) -> RuleSet:
        chosen = schedule[0][1]
        for start, rs in schedule:
            if day >= start:
                chosen = rs
            else:
                break
        return chosen

    return pick, [rs for _, rs in schedule]


def adjudicate_frame(
    claims: pd.DataFrame,
    members: pd.DataFrame,
    providers: pd.DataFrame,
    ruleset_or_schedule: RuleSet | Iterable[tuple[date, RuleSet]],
) -> pd.DataFrame:
    """Batch-adjudicate a claims DataFrame.

    Claims are processed in (member, benefit, service date, claim id) order so the
    year-to-date accumulator and duplicate detection are deterministic. No LLM involved.
    """
    pick, _ = _selector(ruleset_or_schedule)
    mem = members.set_index("member_id")
    mem_plan = mem["plan_id"].to_dict()
    mem_start = mem["coverage_start_day"].to_dict()
    mem_end = mem["coverage_end_day"].to_dict()
    prov_active = providers.set_index("provider_id")["active"].to_dict()

    ordered = claims.sort_values(["member_id", "benefit_type", "service_day", "claim_id"], kind="mergesort")
    ytd: dict[tuple[str, str], float] = {}
    seen: set[tuple] = set()
    out_cols: dict[str, list] = {k: [] for k in (
        "claim_id", "status", "reason_code", "rule_id", "allowed_amount", "reimbursement_amount",
        "authorization_required", "counted_visits", "ruleset_id")}

    for row in ordered.itertuples(index=False):
        bt = BenefitType(row.benefit_type)
        key = (row.member_id, row.benefit_type)
        dup_key = (row.member_id, row.provider_id, row.benefit_type, row.procedure_code, row.service_day)
        is_dup = dup_key in seen
        seen.add(dup_key)
        end = mem_end.get(row.member_id)
        rs = pick(row.service_day)
        d = decide(
            rs, benefit_type=bt, plan_id=mem_plan[row.member_id], service_day=row.service_day,
            coverage_start_day=mem_start[row.member_id],
            coverage_end_day=None if pd.isna(end) else int(end),
            provider_active=bool(prov_active.get(row.provider_id, False)), is_duplicate=is_dup,
            prior_completed=row.prior_completed_visits, prior_cancelled=row.prior_cancelled_visits,
            auth_present=bool(row.authorization_present), billed=row.billed_amount,
            ytd_paid=ytd.get(key, 0.0),
        )
        if d.reimbursement:
            ytd[key] = round(ytd.get(key, 0.0) + d.reimbursement, 2)
        out_cols["claim_id"].append(row.claim_id)
        out_cols["status"].append(d.status.value)
        out_cols["reason_code"].append(d.reason.value)
        out_cols["rule_id"].append(d.rule_id)
        out_cols["allowed_amount"].append(d.allowed)
        out_cols["reimbursement_amount"].append(d.reimbursement)
        out_cols["authorization_required"].append(d.auth_required)
        out_cols["counted_visits"].append(d.counted_visits)
        out_cols["ruleset_id"].append(rs.ruleset_id)

    result = pd.DataFrame(out_cols)
    # Return in the original claim order for easy joins.
    return claims[["claim_id"]].merge(result, on="claim_id", how="left")
