"""Deterministic executive-summary templates (used in DEMO mode and as LIVE fallback)."""

from __future__ import annotations

from typing import Any

from app.models.outputs import CostBreakdown, Decision, ROIResult, ScoreCard


def facts_for(decision: Decision, scores: ScoreCard, cost: CostBreakdown, roi: ROIResult, org: str) -> dict[str, Any]:
    return {
        "organization": org,
        "architecture_label": decision.architecture_label,
        "primary_architecture": decision.primary_architecture_label,
        "ai_verdict": decision.ai_verdict_label,
        "agentic_verdict_label": decision.agentic_verdict_label,
        "autonomy": decision.autonomy_label,
        "scores": {k: round(v) for k, v in scores.as_dict().items()},
        "proposed_cost_month": cost.proposed_cost_month,
        "roi_verdict": roi.verdict.value,
        "net_annual_benefit": roi.net_annual_benefit,
    }


def template_summary(decision: Decision, scores: ScoreCard, cost: CostBreakdown, roi: ROIResult, org: str) -> str:
    s = scores
    head = f"RECOMMENDED ARCHITECTURE: {decision.primary_architecture_label.upper()} — {decision.architecture_label}."
    if decision.ai_recommended:
        body = (
            f"{org} should adopt {decision.architecture_label}. AI suitability is {s.ai_suitability.value:.0f}/100 and the "
            f"selected pattern(s) ({', '.join(p.value for p in decision.ai_patterns)}) met their thresholds; simpler options "
            f"were rejected for documented reasons. {decision.agentic_verdict_label}: {decision.agentic_answer} "
            f"Autonomy is set to {decision.autonomy_label}. Existing systems ({', '.join(decision.authoritative_systems[:3]) or 'current platform'}) "
            f"remain authoritative and AI integrates through existing APIs. Estimated run cost is ${cost.proposed_cost_month:,.0f}/month "
            f"(sample pricing); business case: {roi.verdict.value}."
        )
    else:
        body = (
            f"DO NOT USE AI for this workload. {decision.rationale[0] if decision.rationale else ''} "
            f"{decision.agentic_verdict_label}: {decision.agentic_answer} "
            f"AI suitability is only {s.ai_suitability.value:.0f}/100. "
            + (f"Business case for the AI alternative: {roi.verdict.value}. " if roi.verdict.name == "NOT_JUSTIFIED" else "")
            + "Keep the existing architecture and address the pain points with deterministic engineering."
        )
    risk = f"Overall risk {s.overall_risk.value:.0f}/100 ({s.overall_risk.band}); security risk {s.security_risk.value:.0f}/100."
    return f"{head}\n\n{body}\n\n{risk}"
