"""ArchAI FastAPI application.

Uses exactly the same service layer as the Streamlit UI — no duplicated
decision logic. Never returns or logs secrets.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app import __version__
from app.config.logging_config import configure_logging
from app.config.settings import get_settings
from app.decision_engine.weights import ENGINE_VERSION
from app.graph.workflow import graph_mermaid
from app.models.enums import ArchitectureOption, Industry
from app.models.inputs import AssessmentRequest, CostInputs, ROIInputs
from app.models.outputs import AssessmentResult, CostBreakdown, ROIResult
from app.observability.tracing import METRICS
from app.scenarios import ScenarioNotFound, get_scenario, list_scenarios, scenario_request
from app.services import AssessmentError, calculate_roi, decision_options, recommend_architecture, run_assessment, simulate_cost

configure_logging(get_settings().log_level)

app = FastAPI(
    title="ArchAI — Enterprise AI Architecture Advisor",
    description='"Modernize intelligently. Agentify selectively." Deterministic decision engine; '
    "DEMO_MODE makes zero paid LLM calls. All bundled scenarios are fictional.",
    version=__version__,
)


class CostSimulationRequest(BaseModel):
    cost_inputs: CostInputs = Field(default_factory=CostInputs)
    architecture: ArchitectureOption = ArchitectureOption.RAG_GENAI
    ai_patterns: list[ArchitectureOption] | None = None
    industry: Industry = Industry.GENERAL_ENTERPRISE
    review_mandatory: bool = False


class ROIRequest(BaseModel):
    roi_inputs: ROIInputs = Field(default_factory=ROIInputs)
    ai_operating_cost_annual: float | None = Field(default=None, ge=0)


def _run(request: AssessmentRequest) -> AssessmentResult:
    try:
        return run_assessment(request)
    except AssessmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "engine_version": ENGINE_VERSION,
        "mode": s.mode_label,
        "demo_mode": s.demo_mode,
        "live_ai_available": s.live_ai_enabled,  # boolean only — the key itself is never exposed
        "paid_llm_calls_total": METRICS.get("paid_llm_calls_total"),
    }


@app.post("/assessment", response_model=AssessmentResult)
def assessment(request: AssessmentRequest) -> AssessmentResult:
    return _run(request)


@app.post("/assessment/adr", response_class=PlainTextResponse)
def assessment_adr(request: AssessmentRequest) -> str:
    """Run an assessment and return only the ADR as Markdown."""
    return _run(request).adr.markdown


@app.post("/architecture/recommend")
def architecture_recommend(request: AssessmentRequest) -> dict[str, Any]:
    try:
        return recommend_architecture(request)
    except AssessmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/cost/simulate", response_model=CostBreakdown)
def cost_simulate(body: CostSimulationRequest) -> CostBreakdown:
    try:
        return simulate_cost(body.cost_inputs, body.architecture, body.ai_patterns, body.industry, body.review_mandatory)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/roi/calculate", response_model=ROIResult)
def roi_calculate(body: ROIRequest) -> ROIResult:
    return calculate_roi(body.roi_inputs, body.ai_operating_cost_annual)


@app.get("/scenarios")
def scenarios() -> list[dict[str, Any]]:
    return list_scenarios()


@app.get("/scenarios/{scenario_id}")
def scenario(scenario_id: str) -> dict[str, Any]:
    try:
        return get_scenario(scenario_id)
    except ScenarioNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario_id}'") from exc


@app.post("/scenarios/{scenario_id}/assessment", response_model=AssessmentResult)
def scenario_assessment(scenario_id: str) -> AssessmentResult:
    try:
        req = scenario_request(scenario_id)
    except ScenarioNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{scenario_id}'") from exc
    return _run(req)


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return METRICS.snapshot()


@app.get("/decision-options")
def get_decision_options() -> dict[str, Any]:
    return decision_options()


@app.get("/workflow/mermaid", response_class=PlainTextResponse)
def workflow_mermaid() -> str:
    """Mermaid source of the LangGraph assessment workflow."""
    return graph_mermaid()
