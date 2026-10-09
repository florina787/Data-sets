"""Current-vs-proposed comparison and financial impact (DETERMINISTIC).

Every changed claim is classified as an *expected* consequence of the requirement or as
*unexpected*. Unexpected changes are regression signals that feed the release-risk engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.models.domain import FinancialImpact

_PAYMENT_REASONS = {"PAID", "PAID_CAPPED", "BENEFIT_MAX_REACHED"}


@dataclass(frozen=True)
class ChangeSpec:
    """What the requirement is *supposed* to change (derived from requirement analysis)."""

    benefit_type: str | None
    annual_max_changed: bool = False
    auth_threshold: int | None = None
    reimbursement_changed: bool = False
    in_scope_benefits: frozenset[str] = field(default_factory=frozenset)


def merge_results(claims: pd.DataFrame, current: pd.DataFrame, proposed: pd.DataFrame) -> pd.DataFrame:
    base = claims[["claim_id", "member_id", "provider_id", "benefit_type", "service_date",
                   "prior_completed_visits", "prior_cancelled_visits", "authorization_present", "billed_amount"]]
    cur = current.add_suffix("_cur").rename(columns={"claim_id_cur": "claim_id"})
    pro = proposed.add_suffix("_new").rename(columns={"claim_id_new": "claim_id"})
    return base.merge(cur, on="claim_id").merge(pro, on="claim_id")


def classify_changes(merged: pd.DataFrame, spec: ChangeSpec) -> pd.Series:
    """Return a classification label per row ('UNCHANGED', 'EXPECTED_*' or 'UNEXPECTED_*')."""
    labels = []
    for r in merged.itertuples(index=False):
        changed = (r.status_cur != r.status_new or r.reason_code_cur != r.reason_code_new
                   or abs(r.reimbursement_amount_cur - r.reimbursement_amount_new) > 0.005)
        if not changed:
            labels.append("UNCHANGED")
            continue
        in_scope = r.benefit_type in spec.in_scope_benefits
        if not in_scope:
            labels.append("UNEXPECTED_OUT_OF_SCOPE_BENEFIT")
            continue
        if r.reason_code_new == "AUTH_REQUIRED":
            ok = (spec.auth_threshold is not None and r.prior_completed_visits >= spec.auth_threshold
                  and not r.authorization_present)
            labels.append("EXPECTED_NEW_AUTH_REQUIREMENT" if ok else "UNEXPECTED_AUTH_DENIAL")
            continue
        if r.reason_code_cur in _PAYMENT_REASONS and r.reason_code_new in _PAYMENT_REASONS:
            if spec.annual_max_changed or spec.reimbursement_changed or spec.auth_threshold is not None:
                # Accumulator effect: a higher maximum, or earlier auth denials, shift the YTD balance.
                labels.append("EXPECTED_ANNUAL_MAX_OR_ACCUMULATOR")
            else:
                labels.append("UNEXPECTED_PAYMENT_CHANGE")
            continue
        if r.reason_code_cur == "AUTH_REQUIRED" and r.reason_code_new in _PAYMENT_REASONS:
            labels.append("EXPECTED_AUTH_RELAXED" if spec.auth_threshold is not None else "UNEXPECTED_OTHER")
            continue
        labels.append("UNEXPECTED_OTHER")
    return pd.Series(labels, index=merged.index, name="change_class")


def financial_impact(current_total: float, proposed_total: float, n_claims: int,
                     annual_claim_volume: int) -> FinancialImpact:
    """Scale the simulated reimbursement difference to the synthetic annual book of business."""
    diff = round(proposed_total - current_total, 2)
    scale = annual_claim_volume / n_claims if n_claims else 0.0
    annual = round(diff * scale, 2)
    return FinancialImpact(
        current_reimbursement=round(current_total, 2),
        proposed_reimbursement=round(proposed_total, 2),
        difference=diff,
        claims_simulated=n_claims,
        projected_annual_impact=annual,
        projected_monthly_impact=round(annual / 12, 2),
        annual_claim_volume_assumption=annual_claim_volume,
    )


def rate(series: pd.Series, value: str) -> float:
    return float((series == value).mean()) if len(series) else 0.0
