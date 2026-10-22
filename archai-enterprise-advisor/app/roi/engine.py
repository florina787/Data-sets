"""Deterministic ROI / business-case engine.

"ROI DOES NOT JUSTIFY AI" is a first-class outcome.
"""

from __future__ import annotations

from app.decision_engine import weights as W
from app.models.enums import ROIVerdict
from app.models.inputs import ROIInputs
from app.models.outputs import ROIResult


def calculate_roi(inputs: ROIInputs, ai_operating_cost_annual: float | None = None, *, ai_proposed: bool = True) -> ROIResult:
    """Compute the annual business case.

    ``ai_operating_cost_annual`` (from the cost engine) is used unless the
    request overrides it in ``inputs.ai_operating_cost_annual``.
    """
    manual = inputs.tasks_per_month * 12 * inputs.minutes_per_task / 60 * inputs.hourly_cost
    errors = inputs.tasks_per_month * 12 * inputs.error_rate_pct / 100 * inputs.rework_cost_per_error
    current = manual + errors + inputs.existing_technology_cost_annual
    notes: list[str] = []

    if not ai_proposed:
        return ROIResult(
            annual_manual_effort_cost=round(manual, 2),
            annual_error_cost=round(errors, 2),
            annual_current_operating_cost=round(current, 2),
            estimated_annual_benefit=0.0,
            estimated_ai_operating_cost=0.0,
            estimated_implementation_cost=0.0,
            net_annual_benefit=0.0,
            payback_months=None,
            three_year_roi_pct=None,
            benefit_to_cost_ratio=0.0,
            verdict=ROIVerdict.NOT_APPLICABLE,
            notes=["No AI investment proposed; existing operating cost continues."],
        )

    benefit = manual * inputs.expected_time_reduction_pct / 100 + errors * inputs.expected_error_reduction_pct / 100
    operating = inputs.ai_operating_cost_annual if inputs.ai_operating_cost_annual is not None else (ai_operating_cost_annual or 0.0)
    if inputs.ai_operating_cost_annual is not None:
        notes.append("AI operating cost taken from request override.")
    implementation = inputs.implementation_cost
    net = benefit - operating
    payback = implementation / (net / 12) if net > 0 else None
    three_year = ((3 * net - implementation) / implementation * 100) if implementation > 0 else None
    amortized = operating + implementation / 3
    ratio = benefit / amortized if amortized > 0 else (10.0 if benefit > 0 else 0.0)

    if net <= 0:
        verdict = ROIVerdict.NOT_JUSTIFIED
        notes.append("AI operating cost exceeds the estimated annual benefit.")
    elif payback is not None and payback > W.ROI_PAYBACK_MAX_MONTHS:
        verdict = ROIVerdict.NOT_JUSTIFIED
        notes.append(f"Payback {payback:.0f} months exceeds the {W.ROI_PAYBACK_MAX_MONTHS:.0f}-month ceiling.")
    elif payback is not None and payback > W.ROI_PAYBACK_MARGINAL_MONTHS:
        verdict = ROIVerdict.MARGINAL
        notes.append(f"Payback {payback:.0f} months — validate assumptions in a narrow pilot.")
    else:
        verdict = ROIVerdict.JUSTIFIED
    notes.append("Benefits are estimates from your inputs; validate in Phase 0/1 with measured baselines.")
    return ROIResult(
        annual_manual_effort_cost=round(manual, 2),
        annual_error_cost=round(errors, 2),
        annual_current_operating_cost=round(current, 2),
        estimated_annual_benefit=round(benefit, 2),
        estimated_ai_operating_cost=round(operating, 2),
        estimated_implementation_cost=round(implementation, 2),
        net_annual_benefit=round(net, 2),
        payback_months=round(payback, 1) if payback is not None else None,
        three_year_roi_pct=round(three_year, 1) if three_year is not None else None,
        benefit_to_cost_ratio=round(ratio, 3),
        verdict=verdict,
        notes=notes,
    )
