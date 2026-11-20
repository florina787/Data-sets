"""ArchAI service layer — the single entry point used by both FastAPI and Streamlit.

No decision logic lives here; it orchestrates the LangGraph workflow and the
deterministic engines so the UI and API can never diverge.
"""

from __future__ import annotations

from typing import Any

from app.config.logging_config import configure_logging, get_logger
from app.config.settings import get_settings
from app.cost.engine import simulate
from app.graph.workflow import run_graph
from app.llm.provider import get_narrator
from app.models.enums import (
    AGENTIC_VERDICT_LABELS,
    ARCHITECTURE_LABELS,
    AUTONOMY_LABELS,
    REGULATED_INDUSTRIES,
    ArchitectureOption,
    Industry,
)
from app.models.inputs import AssessmentRequest, CostInputs, ROIInputs
from app.models.outputs import AssessmentResult, CostBreakdown, ROIResult
from app.observability.tracing import METRICS, Tracer, export
from app.roi.engine import calculate_roi as _calculate_roi

logger = get_logger("service")


class AssessmentError(RuntimeError):
    """Raised when an assessment cannot be completed."""


def run_assessment(request: AssessmentRequest) -> AssessmentResult:
    """Run the full ArchAI assessment workflow."""
    settings = get_settings()
    configure_logging(settings.log_level)
    tracer = Tracer(mode=settings.mode_label)
    narrator = get_narrator(settings)
    try:
        state = run_graph(request, tracer, narrator)
    except Exception as exc:
        METRICS.increment("errors_total")
        logger.exception("assessment_failed", extra={"extra_fields": {"request_id": tracer.request_id}})
        raise AssessmentError(f"Assessment failed: {type(exc).__name__}: {exc}") from exc

    trace = tracer.summary()
    d = state["decision"]
    result = AssessmentResult(
        organization=request.organization.name,
        industry=request.organization.industry.value,
        use_case=request.use_case.title,
        discovery=state["discovery"],
        infrastructure=state["infrastructure"],
        data_readiness=state["data_readiness"],
        use_case_assessment=state["use_case_assessment"],
        scores=state["scores"],
        decision=d,
        security=state["security"],
        resilience=state["resilience"],
        build_vs_buy=state["build_vs_buy"],
        model_deployment=state["model_deployment"],
        cost=state["cost"],
        roi=state["roi"],
        matrix=state["matrix"],
        target_architecture=state["target_architecture"],
        challenger=state["challenger"],
        roadmap=state["roadmap"],
        evaluation=state["evaluation"],
        adr=state["adr"],
        executive_summary=state["executive_summary"],
        explanation_source=state["explanation_source"],
        trace=trace,
    )
    summary = {
        "primary_architecture": d.primary_architecture.value,
        "architecture_label": d.architecture_label,
        "agentic_verdict": d.agentic_verdict.value,
        "autonomy_level": int(d.autonomy_level),
        "scores": {k: round(v, 1) for k, v in result.scores.as_dict().items()},
        "rules": d.triggered_rules,
    }
    METRICS.record_assessment(trace, summary)
    export(trace, summary)
    return result


def recommend_architecture(request: AssessmentRequest) -> dict[str, Any]:
    """Architecture-focused subset of a full assessment."""
    r = run_assessment(request)
    return {
        "request_id": r.trace.request_id,
        "decision": r.decision.model_dump(mode="json"),
        "scores": r.scores.as_dict(),
        "matrix": [m.model_dump(mode="json") for m in r.matrix],
        "target_architecture": r.target_architecture.model_dump(mode="json"),
        "build_vs_buy": r.build_vs_buy.model_dump(mode="json"),
        "model_deployment": r.model_deployment.model_dump(mode="json"),
        "challenger": r.challenger.model_dump(mode="json"),
    }


def simulate_cost(
    inputs: CostInputs,
    architecture: ArchitectureOption,
    ai_patterns: list[ArchitectureOption] | None = None,
    industry: Industry = Industry.GENERAL_ENTERPRISE,
    review_mandatory: bool = False,
) -> CostBreakdown:
    """What-if cost simulation (deterministic)."""
    return simulate(inputs, architecture, ai_patterns, regulated=industry in REGULATED_INDUSTRIES, review_mandatory=review_mandatory)


def calculate_roi(inputs: ROIInputs, ai_operating_cost_annual: float | None = None) -> ROIResult:
    return _calculate_roi(inputs, ai_operating_cost_annual)


def decision_options() -> dict[str, Any]:
    """Catalogue of architecture options, verdicts and autonomy levels."""
    return {
        "architecture_options": [{"id": o.value, "label": ARCHITECTURE_LABELS[o]} for o in ArchitectureOption],
        "agentic_verdicts": [{"id": v.value, "label": label} for v, label in AGENTIC_VERDICT_LABELS.items()],
        "autonomy_levels": [{"level": int(level), "label": label} for level, label in AUTONOMY_LABELS.items()],
        "negative_recommendations_supported": ["DO NOT USE AI", "AGENTIC AI NOT RECOMMENDED", "ROI DOES NOT JUSTIFY AI"],
    }
