"""Assessment input models.

Ratings use a 0–5 scale: 0 = not at all / none, 5 = critical / very high.
Everything the decision engine uses is captured explicitly here, so the
recommendation is fully reproducible from the request payload.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    ActionType,
    ArchitectureStyle,
    Compute,
    DataStore,
    Deployment,
    DevOpsTool,
    IdentitySecurity,
    Industry,
    Integration,
    TaskType,
)

Rating = Annotated[int, Field(ge=0, le=5)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Organization(_Base):
    name: str = Field(default="Example Enterprise", max_length=120)
    industry: Industry = Industry.GENERAL_ENTERPRISE
    size: str = Field(default="large", description="small | mid | large | enterprise")
    regulatory_intensity: Rating | None = Field(
        default=None, description="Override; defaults to an industry baseline when omitted."
    )
    ai_maturity: Rating = Field(default=2, description="Existing AI/ML delivery and MLOps capability.")
    gpu_available: bool = Field(default=False, description="GPU capacity available for self-hosted inference.")
    data_residency_regions: list[str] = Field(default_factory=list)


class CurrentArchitecture(_Base):
    deployment: list[Deployment] = Field(default_factory=lambda: [Deployment.ON_PREMISES])
    compute: list[Compute] = Field(default_factory=list)
    styles: list[ArchitectureStyle] = Field(default_factory=list)
    integration: list[Integration] = Field(default_factory=list)
    identity_security: list[IdentitySecurity] = Field(default_factory=list)
    data_stores: list[DataStore] = Field(default_factory=list)
    devops: list[DevOpsTool] = Field(default_factory=list)
    existing_systems: list[str] = Field(
        default_factory=list,
        description="Named business systems already in place, e.g. 'Transaction Rules Engine'.",
    )
    end_of_life_components: list[str] = Field(
        default_factory=list,
        description="Components the organization has already flagged as end-of-life (only these may be REPLACED).",
    )


class DataProfile(_Base):
    availability: Rating = 3
    quality: Rating = 3
    freshness: Rating = 3
    ownership: Rating = 3
    lineage: Rating = 2
    metadata: Rating = 2
    permissions: Rating = 3
    document_quality: Rating = 3
    structured_share_pct: int = Field(default=50, ge=0, le=100)
    knowledge_fragmentation: Rating = 2
    contains_pii: bool = False
    contains_financial_data: bool = False
    confidential: bool = False
    privileged: bool = Field(default=False, description="Legally privileged (e.g. attorney-client).")
    data_residency_required: bool = False
    data_sources: list[str] = Field(default_factory=list)


class UseCase(_Base):
    title: str = Field(default="Untitled use case", max_length=160)
    description: str = Field(default="", max_length=4000)
    users: str = ""
    workflow: str = ""
    pain_points: list[str] = Field(default_factory=list)
    desired_outcome: str = ""
    current_solution: str = ""
    constraints: list[str] = Field(default_factory=list)
    primary_tasks: list[TaskType] = Field(default_factory=list)
    action_types: list[ActionType] = Field(default_factory=lambda: [ActionType.READ_ONLY])
    replaces_existing_component: str | None = Field(
        default=None, description="Existing component the requester proposes to replace with AI, if any."
    )
    customer_facing: bool = False

    deterministic_requirement: Rating = 2
    prediction_requirement: Rating = 0
    generation_requirement: Rating = 0
    workflow_variability: Rating = 1
    multi_step_reasoning: Rating = 1
    cross_system_interaction: Rating = 1
    tool_requirements: Rating = 0
    proprietary_knowledge_need: Rating = 0
    citation_requirement: Rating = 0
    knowledge_change_frequency: Rating = 1
    autonomy_benefit: Rating = 1
    hallucination_tolerance: Rating = Field(default=2, description="0 = zero tolerance for fabricated output.")
    transaction_criticality: Rating = 1
    explainability_requirement: Rating = 2
    latency_sensitivity: Rating = 2
    availability_requirement: Rating = 3
    human_oversight_available: Rating = Field(default=3, description="Capacity of qualified humans to review AI output.")


class CostInputs(_Base):
    requests_per_month: int = Field(default=20_000, ge=0, le=1_000_000_000)
    avg_input_tokens: int = Field(default=1_500, ge=0, le=2_000_000)
    avg_output_tokens: int = Field(default=400, ge=0, le=200_000)
    rag_top_k: int = Field(default=5, ge=0, le=100)
    tokens_per_chunk: int = Field(default=400, ge=0, le=20_000)
    cache_hit_rate: float = Field(default=0.3, ge=0.0, le=1.0)
    small_model_routing_pct: float = Field(default=0.4, ge=0.0, le=1.0)
    batch_pct: float = Field(default=0.0, ge=0.0, le=1.0, description="Share of requests processed via batch APIs.")
    max_output_tokens: int | None = Field(default=None, ge=1, description="Response-length limit, if enforced.")
    llm_calls_per_request: float | None = Field(
        default=None, ge=0, le=50, description="Override; defaults by architecture (agents make several calls)."
    )
    human_review_pct: float = Field(default=0.2, ge=0.0, le=1.0)
    human_review_minutes: float = Field(default=3.0, ge=0.0, le=480.0)
    reviewer_hourly_cost: float = Field(default=60.0, ge=0.0)
    infrastructure_cost_month: float = Field(default=2_500.0, ge=0.0)
    current_monthly_cost: float = Field(default=0.0, ge=0.0, description="Current run-cost of the process being changed.")
    primary_model: str = "premium_model"
    small_model: str = "small_model"


class ROIInputs(_Base):
    people_involved: int = Field(default=10, ge=0)
    tasks_per_month: int = Field(default=2_000, ge=0)
    minutes_per_task: float = Field(default=20.0, ge=0.0)
    hourly_cost: float = Field(default=60.0, ge=0.0)
    error_rate_pct: float = Field(default=2.0, ge=0.0, le=100.0)
    rework_cost_per_error: float = Field(default=50.0, ge=0.0)
    existing_technology_cost_annual: float = Field(default=0.0, ge=0.0)
    implementation_cost: float = Field(default=250_000.0, ge=0.0)
    ai_operating_cost_annual: float | None = Field(
        default=None, ge=0.0, description="Override; otherwise derived from the cost engine (12 × monthly)."
    )
    expected_time_reduction_pct: float = Field(default=30.0, ge=0.0, le=100.0)
    expected_error_reduction_pct: float = Field(default=20.0, ge=0.0, le=100.0)


class AssessmentRequest(_Base):
    """Complete input for an ArchAI assessment."""

    organization: Organization = Field(default_factory=Organization)
    current_architecture: CurrentArchitecture = Field(default_factory=CurrentArchitecture)
    data_profile: DataProfile = Field(default_factory=DataProfile)
    use_case: UseCase = Field(default_factory=UseCase)
    cost_inputs: CostInputs = Field(default_factory=CostInputs)
    roi_inputs: ROIInputs = Field(default_factory=ROIInputs)
    scenario_id: str | None = None
