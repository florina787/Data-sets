"""Assessment output models.

Every number in these models is produced by deterministic Python code. LLMs (in
LIVE mode only) may rewrite the narrative ``executive_summary``; they never set
scores, verdicts or costs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    ActionType,
    AgenticVerdict,
    ArchitectureOption,
    AutonomyLevel,
    ChallengeVerdict,
    MatrixDecision,
    ROIVerdict,
    SourcingDecision,
)


# --------------------------------------------------------------------------- scores
class ScoreFactor(BaseModel):
    name: str
    raw: float = Field(description="Normalized input value 0..1")
    weight: float
    contribution: float = Field(description="Points contributed to the 0..100 score")


class Score(BaseModel):
    key: str
    label: str
    value: float = Field(ge=0, le=100)
    band: str = ""
    interpretation: str = ""
    factors: list[ScoreFactor] = Field(default_factory=list)
    adjustments: list[str] = Field(default_factory=list)


class ScoreCard(BaseModel):
    ai_suitability: Score
    ml_suitability: Score
    genai_suitability: Score
    rag_suitability: Score
    agentic_readiness: Score
    infrastructure_readiness: Score
    data_readiness: Score
    security_risk: Score
    operational_risk: Score
    overall_risk: Score
    roi_business_value: Score

    def as_dict(self) -> dict[str, float]:
        return {k: getattr(self, k).value for k in type(self).model_fields}


# ------------------------------------------------------------------- assessments
class Finding(BaseModel):
    area: str
    observation: str
    implication: str = ""


class DiscoveryResult(BaseModel):
    business_problem: str
    users: str
    workflow: str
    pain_points: list[str]
    desired_outcome: str
    current_solution: str
    constraints: list[str]
    information_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class InfrastructureAssessment(BaseModel):
    score: float
    maturity_label: str
    platform_summary: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    reusable_platform_capabilities: list[str] = Field(default_factory=list)


class DataReadinessAssessment(BaseModel):
    score: float
    maturity_label: str
    unstructured_share_pct: int
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    rag_prerequisites_met: bool
    rag_prerequisite_notes: list[str] = Field(default_factory=list)
    vector_database_note: str = ""


class UseCaseAssessment(BaseModel):
    workload_character: str
    is_deterministic_workload: bool
    deterministic_only_actions: list[ActionType] = Field(default_factory=list)
    high_risk_write_actions: list[ActionType] = Field(default_factory=list)
    agentic_need_signals: dict[str, int] = Field(default_factory=dict)
    agentic_need_gate_met: bool = False
    replacement_request: str | None = None
    findings: list[Finding] = Field(default_factory=list)


class RejectedAlternative(BaseModel):
    option: ArchitectureOption
    reason: str


class ActionPolicy(BaseModel):
    action: ActionType
    max_ai_autonomy: AutonomyLevel
    executor: str
    reason: str


class PatternDesign(BaseModel):
    pattern: str
    summary: str
    components: list[str] = Field(default_factory=list)
    design_notes: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    primary_architecture: ArchitectureOption
    primary_architecture_label: str
    architecture_label: str = Field(description="Concrete label, e.g. 'Existing Microservices + RAG'.")
    ai_recommended: bool
    ai_verdict_label: str
    ai_patterns: list[ArchitectureOption] = Field(default_factory=list)
    agentic_verdict: AgenticVerdict
    agentic_verdict_label: str
    agentic_answer: str = Field(description="Explicit answer to 'Does this workload actually require agents?'")
    agentic_rationale: list[str] = Field(default_factory=list)
    autonomy_level: AutonomyLevel
    autonomy_label: str
    autonomy_rationale: list[str] = Field(default_factory=list)
    requires_human_approval: bool
    human_review_mandatory: bool
    citations_mandatory: bool
    authoritative_systems: list[str] = Field(default_factory=list)
    action_policies: list[ActionPolicy] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    rejected_alternatives: list[RejectedAlternative] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)
    candidate_scores: dict[str, float] = Field(default_factory=dict)
    excluded_patterns: list[ArchitectureOption] = Field(default_factory=list)
    pattern_design: PatternDesign | None = None


class Control(BaseModel):
    category: str
    control: str
    priority: str = Field(description="MUST | SHOULD | COULD")
    reason: str = ""


class Threat(BaseModel):
    name: str
    applies: bool
    likelihood: str
    impact: str
    mitigations: list[str] = Field(default_factory=list)


class SecurityAssessment(BaseModel):
    security_risk_score: float
    data_classification: str
    controls: list[Control] = Field(default_factory=list)
    agent_threats: list[Threat] = Field(default_factory=list)
    governance_requirements: list[str] = Field(default_factory=list)
    industry_considerations: list[str] = Field(default_factory=list)
    agent_guardrail_config: dict[str, Any] = Field(default_factory=dict)


class FailureScenario(BaseModel):
    failure: str
    impact: str
    response: str


class ResilienceAssessment(BaseModel):
    principle: str
    ai_on_critical_path: bool
    degradation_chain: list[str]
    failure_scenarios: list[FailureScenario]
    patterns: dict[str, str]
    recommendations: list[str]


class SourcingOption(BaseModel):
    option: str
    fit_score: float
    rationale: str


class BuildVsBuyAssessment(BaseModel):
    decision: SourcingDecision
    summary: str
    options: list[SourcingOption]
    reasoning: list[str]


class ModelDeploymentOption(BaseModel):
    option: str
    suitable: bool
    rationale: str


class ModelDeploymentStrategy(BaseModel):
    recommended: str
    rationale: list[str]
    options: list[ModelDeploymentOption]


class CostBreakdown(BaseModel):
    requests_per_month: int
    llm_calls_per_request: float
    effective_input_tokens: float
    effective_output_tokens: float
    cost_per_request: float
    unoptimized_cost_per_request: float
    model_cost_month: float
    unoptimized_model_cost_month: float
    infrastructure_cost_month: float
    human_review_cost_month: float
    current_cost_month: float
    proposed_cost_month: float
    expected_savings_month: float
    optimization_savings_month: float
    estimated_latency_ms: float
    latency_note: str
    risk_impact: str
    risk_notes: list[str] = Field(default_factory=list)
    optimizations_applied: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    comparison_by_architecture: dict[str, float] = Field(
        default_factory=dict, description="Proposed monthly run cost if each option were chosen (same inputs)."
    )
    pricing_disclaimer: str


class ROIResult(BaseModel):
    annual_manual_effort_cost: float
    annual_error_cost: float
    annual_current_operating_cost: float
    estimated_annual_benefit: float
    estimated_ai_operating_cost: float
    estimated_implementation_cost: float
    net_annual_benefit: float
    payback_months: float | None
    three_year_roi_pct: float | None
    benefit_to_cost_ratio: float
    verdict: ROIVerdict
    notes: list[str] = Field(default_factory=list)


class MatrixRow(BaseModel):
    component: str
    decision: MatrixDecision
    reason: str


class TargetArchitecture(BaseModel):
    summary: str
    current_state_mermaid: str
    target_state_mermaid: str
    added_components: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)


class ChallengeQuestion(BaseModel):
    question: str
    verdict: ChallengeVerdict
    finding: str


class ChallengerResult(BaseModel):
    questions: list[ChallengeQuestion]
    requires_revision: bool
    exclude_patterns: list[ArchitectureOption] = Field(default_factory=list)
    revision_reason: str = ""
    revisions_applied: int = 0
    final_verdict: str = ""


class RoadmapPhase(BaseModel):
    phase: int
    name: str
    objective: str
    activities: list[str]
    exit_criteria: list[str]
    autonomy_ceiling: AutonomyLevel
    included: bool = True
    note: str = ""


class Roadmap(BaseModel):
    summary: str
    phases: list[RoadmapPhase]


class EvaluationMetric(BaseModel):
    name: str
    target: str
    why: str


class EvaluationPlan(BaseModel):
    architecture: str
    metrics: list[EvaluationMetric]
    disclaimer: str


class ADR(BaseModel):
    title: str
    status: str
    markdown: str


class TraceSpan(BaseModel):
    node: str
    duration_ms: float
    status: str = "ok"
    detail: str = ""


class TraceSummary(BaseModel):
    request_id: str
    timestamp: str
    mode: str
    workflow_path: list[str]
    agents_invoked: list[str]
    spans: list[TraceSpan]
    model_calls: int
    paid_model_calls: int
    tool_calls: int
    total_latency_ms: float
    errors: list[str] = Field(default_factory=list)


class AssessmentResult(BaseModel):
    """Complete, explainable output of an ArchAI assessment."""

    organization: str
    industry: str
    use_case: str
    discovery: DiscoveryResult
    infrastructure: InfrastructureAssessment
    data_readiness: DataReadinessAssessment
    use_case_assessment: UseCaseAssessment
    scores: ScoreCard
    decision: Decision
    security: SecurityAssessment
    resilience: ResilienceAssessment
    build_vs_buy: BuildVsBuyAssessment
    model_deployment: ModelDeploymentStrategy
    cost: CostBreakdown
    roi: ROIResult
    matrix: list[MatrixRow]
    target_architecture: TargetArchitecture
    challenger: ChallengerResult
    roadmap: Roadmap
    evaluation: EvaluationPlan
    adr: ADR
    executive_summary: str
    explanation_source: str = Field(description="'deterministic-template' or 'llm-narration'")
    trace: TraceSummary
