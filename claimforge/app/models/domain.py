"""Typed Pydantic domain models for ClaimForge.

All instances in this project are SYNTHETIC. Identifiers use obviously fictional
prefixes (``MBR-SYN-``, ``PRV-SYN-``, ``CLM-SYN-``) and no personal names are generated.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- enums
class BenefitType(str, Enum):
    PHYSIOTHERAPY = "PHYSIOTHERAPY"
    CHIROPRACTIC = "CHIROPRACTIC"
    MASSAGE_THERAPY = "MASSAGE_THERAPY"
    ACUPUNCTURE = "ACUPUNCTURE"


class VisitStatus(str, Enum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ClaimStatus(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"


class ReasonCode(str, Enum):
    PAID = "PAID"
    PAID_CAPPED = "PAID_CAPPED"
    MEMBER_INELIGIBLE = "MEMBER_INELIGIBLE"
    POLICY_NOT_EFFECTIVE = "POLICY_NOT_EFFECTIVE"
    PROVIDER_INELIGIBLE = "PROVIDER_INELIGIBLE"
    NOT_COVERED = "NOT_COVERED"
    DUPLICATE = "DUPLICATE"
    VISIT_LIMIT_EXCEEDED = "VISIT_LIMIT_EXCEEDED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BENEFIT_MAX_REACHED = "BENEFIT_MAX_REACHED"


class ImpactAction(str, Enum):
    KEEP = "KEEP"
    ENHANCE = "ENHANCE"
    ADD = "ADD"
    REPLACE = "REPLACE"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReleaseDecision(str, Enum):
    READY = "READY"
    READY_WITH_APPROVAL = "READY WITH APPROVAL"
    NOT_READY = "NOT READY"
    BLOCKED = "BLOCKED"


class UseCaseStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    PLANNED = "PLANNED"


class ImplementationKind(str, Enum):
    """How a capability is implemented — shown everywhere to avoid 'fake AI'."""

    DETERMINISTIC = "DETERMINISTIC"
    STATISTICAL = "STATISTICAL"
    RETRIEVAL = "RETRIEVAL (BM25 RAG)"
    TEMPLATE = "DETERMINISTIC TEMPLATE"
    SIMULATED = "SIMULATED"
    MOCKED = "MOCKED"
    LLM_ASSISTED = "LLM-ASSISTED"


class _Model(BaseModel):
    model_config = ConfigDict(use_enum_values=False, extra="forbid")


# --------------------------------------------------------------------------- insurance domain
class Member(_Model):
    member_id: str
    display_label: str  # e.g. "Synthetic Member 000123" — never a real-looking name
    plan_id: str
    coverage_start: date
    coverage_end: date | None = None
    synthetic: bool = True


class Provider(_Model):
    provider_id: str
    display_label: str
    specialty: BenefitType
    active: bool = True
    synthetic: bool = True


class Benefit(_Model):
    benefit_type: BenefitType
    reimbursement_pct: float = Field(ge=0, le=1)
    annual_max: float = Field(ge=0)
    per_visit_allowed_max: float = Field(gt=0)
    max_visits: int | None = None
    auth_after_completed_visits: int | None = None
    count_cancelled_visits: bool = False


class Plan(_Model):
    plan_id: str
    name: str
    covered_benefits: list[BenefitType]
    effective_date: date


class PolicySection(_Model):
    doc_id: str
    section_id: str
    title: str
    text: str
    parent_section: str | None = None

    @property
    def citation(self) -> str:
        return f"[{self.doc_id} §{self.section_id}]"


class Policy(_Model):
    doc_id: str
    title: str
    version: str
    sections: list[PolicySection]
    synthetic: bool = True


class ClaimLine(_Model):
    line_no: int = 1
    procedure_code: str = Field(min_length=2, max_length=16, pattern=r"^[A-Z0-9\-]+$")
    billed_amount: float = Field(gt=0, le=10_000)


class Claim(_Model):
    claim_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9\-_]+$")
    member_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9\-_]+$")
    provider_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9\-_]+$")
    plan_id: str = Field(min_length=3, max_length=40)
    benefit_type: BenefitType
    service_date: date
    lines: list[ClaimLine] = Field(min_length=1, max_length=10)

    @property
    def billed_amount(self) -> float:
        return round(sum(line.billed_amount for line in self.lines), 2)


class Authorization(_Model):
    authorization_id: str
    member_id: str
    benefit_type: BenefitType
    effective_from: date
    status: Literal["APPROVED", "PENDING", "DENIED"] = "APPROVED"


class ClaimContext(_Model):
    """Member/provider/history context needed by the deterministic engine for one claim."""

    coverage_start: date = date(2025, 1, 1)
    coverage_end: date | None = None
    provider_active: bool = True
    prior_completed_visits: int = Field(default=0, ge=0, le=500)
    prior_cancelled_visits: int = Field(default=0, ge=0, le=500)
    authorization_present: bool = False
    ytd_paid: float = Field(default=0.0, ge=0, le=100_000)
    is_duplicate: bool = False


class AdjudicationResult(_Model):
    claim_id: str
    ruleset_id: str
    eligible: bool
    covered: bool
    authorization_required: bool
    authorization_present: bool
    counted_visits: int
    allowed_amount: float
    reimbursement_amount: float
    status: ClaimStatus
    reason_code: ReasonCode
    rule_id: str
    explanation: str
    engine: str = "DETERMINISTIC RULES ENGINE (no LLM)"


# --------------------------------------------------------------------------- SDLC domain
class AcceptanceCriterion(_Model):
    ac_id: str
    given: str
    when: str
    then: str
    rule_id: str | None = None


class BusinessRule(_Model):
    rule_id: str
    name: str
    description: str
    benefit_type: BenefitType | None = None
    policy_section: str | None = None
    change: Literal["NEW", "MODIFIED", "UNCHANGED"] = "UNCHANGED"
    current_value: Any = None
    proposed_value: Any = None


class Ambiguity(_Model):
    ambiguity_id: str
    question: str
    severity: Severity
    blocking: bool
    options: dict[str, str] = Field(default_factory=dict)
    default_assumption: str | None = None
    resolution: str | None = None
    resolved_by: Literal["HUMAN", "POLICY_EVIDENCE", "ASSUMPTION", None] = None


class Requirement(_Model):
    requirement_id: str
    title: str
    raw_text: str
    benefit_type: BenefitType | None = None
    facets: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    user_stories: list[str] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    @property
    def blocking_ambiguities(self) -> list[Ambiguity]:
        return [a for a in self.ambiguities if a.blocking and a.resolution is None]


class Component(_Model):
    component_id: str
    name: str
    type: str
    criticality: Literal["critical", "high", "medium", "low"]
    owner_team: str
    tech: str = ""
    deterministic_engine: bool = False
    depends_on: list[str] = Field(default_factory=list)
    repo_paths: list[str] = Field(default_factory=list)
    status: Literal["existing", "proposed"] = "existing"


class Impact(_Model):
    component_id: str
    component_name: str
    component_type: str
    criticality: str
    action: ImpactAction
    impact_kind: Literal["DIRECT", "INDIRECT", "NEW"]
    reason: str
    facets: list[str] = Field(default_factory=list)


class TestCase(_Model):
    __test__ = False  # not a pytest class
    test_id: str
    title: str
    category: Literal["unit", "boundary", "negative", "regression", "integration", "api"]
    requirement_id: str | None = None
    rule_id: str | None = None
    critical: bool = False
    given: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    executable: bool = True
    source: str = "QA_AGENT"


class TestResult(_Model):
    __test__ = False  # not a pytest class
    test_id: str
    title: str
    passed: bool
    critical: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    ruleset_id: str


class FinancialImpact(_Model):
    current_reimbursement: float
    proposed_reimbursement: float
    difference: float
    claims_simulated: int
    projected_annual_impact: float
    projected_monthly_impact: float
    annual_claim_volume_assumption: int
    disclaimer: str = "SIMULATED ESTIMATE BASED ON SYNTHETIC DATA."


class SimulationResult(_Model):
    simulation_id: str
    current_ruleset: str
    proposed_ruleset: str
    claims_simulated: int
    seed: int
    outcomes_changed: int
    approved_to_denied: int
    denied_to_approved: int
    payment_changed: int
    approval_rate_current: float
    approval_rate_proposed: float
    denial_rate_current: float
    denial_rate_proposed: float
    auth_required_current: int
    auth_required_proposed: int
    expected_changes: dict[str, int]
    unexpected_changes: int
    unexpected_samples: list[dict[str, Any]] = Field(default_factory=list)
    by_benefit: list[dict[str, Any]] = Field(default_factory=list)
    reason_distribution: list[dict[str, Any]] = Field(default_factory=list)
    financial: FinancialImpact
    runtime_ms: float
    label: str = "SIMULATED — deterministic engine over synthetic claims"


class ReleaseRisk(_Model):
    score: float
    level: RiskLevel
    decision: ReleaseDecision
    component_scores: dict[str, float]
    blockers: list[str]
    reasons: list[str]
    required_approvals: list[str]


class Release(_Model):
    release_id: str
    version: str
    deployed_on: date | None = None
    requirements: list[str] = Field(default_factory=list)
    changed_rules: list[str] = Field(default_factory=list)
    change_ids: list[str] = Field(default_factory=list)
    ruleset_id: str
    status: str = "PLANNED"
    approved_by: str | None = None
    notes: str = ""


class ProductionMetric(_Model):
    metric_id: str
    name: str
    segment: dict[str, str] = Field(default_factory=dict)
    period: str
    value: float
    volume: int


class Anomaly(_Model):
    anomaly_id: str
    metric: str
    segment: dict[str, str]
    baseline_mode: Literal["RELEASE_PROJECTION", "HISTORICAL"]
    baseline_value: float
    observed_value: float
    relative_change: float
    z_score: float
    baseline_volume: int
    observed_volume: int
    detected: bool
    method: str = "STATISTICAL: relative change + two-proportion z-test (no LLM)"
    summary: str = ""


class Evidence(_Model):
    evidence_id: str
    kind: str
    statement: str
    supports: str | None = None
    weight: float = 0.0
    data: dict[str, Any] = Field(default_factory=dict)


class RootCause(_Model):
    investigation_id: str
    status: Literal["CONCLUDED", "INCONCLUSIVE"]
    anomaly_summary: str
    correlated_release: str | None = None
    changed_rule: str | None = None
    source_requirement: str | None = None
    policy_section: str | None = None
    likely_defect: str | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_score: float
    evidence: list[Evidence]
    hypotheses: list[dict[str, Any]]
    affected_claims: int = 0
    wrongly_denied_amount: float = 0.0
    sample_claims: list[dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    tool_calls: int = 0
    trace_path: list[str] = Field(default_factory=list)


class Remediation(_Model):
    remediation_id: str
    recommended_change: str
    configuration_change: dict[str, Any]
    implementation_recommendation: list[str]
    code_patch: str
    additional_validation: list[str]
    regression_test: TestCase
    regression_test_code: str
    rollback_option: str
    forward_fix: str
    claims_to_reprocess: int
    verification: dict[str, Any]
    requires_human_approval: bool = True
    status: Literal["PROPOSED", "APPROVED", "REJECTED"] = "PROPOSED"
    iterations: int = 0


class Defect(_Model):
    key: str
    title: str
    issue_type: str = "Bug"
    severity: Severity
    priority: str
    status: str = "OPEN (MOCKED — not sent to any external tracker)"
    description: str
    expected: str
    actual: str
    reproduction: list[str]
    source_requirement: str
    introduced_in_release: str
    rule_id: str
    policy_section: str | None = None
    linked_incident: str | None = None
    regression_test_id: str | None = None
    affected_claims: int = 0
    labels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TraceabilityLink(_Model):
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relation: str


# --------------------------------------------------------------------------- API request models
PERSONAS = [
    "Business Analyst",
    "Product Owner",
    "Insurance Product Manager",
    "Solution Architect",
    "Developer",
    "QA Engineer",
    "Claims Analyst",
    "Operations Engineer",
    "Release Manager",
    "Compliance Reviewer",
    "Engineering Manager",
]


class RequirementRequest(_Model):
    text: str = Field(min_length=10, max_length=4_000)
    persona: str = "Business Analyst"
    clarifications: dict[str, str] = Field(default_factory=dict)

    @field_validator("persona")
    @classmethod
    def _persona(cls, v: str) -> str:
        if v not in PERSONAS:
            raise ValueError(f"persona must be one of {PERSONAS}")
        return v

    @field_validator("clarifications")
    @classmethod
    def _clar(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 20:
            raise ValueError("too many clarifications")
        for key, val in v.items():
            if len(key) > 64 or len(val) > 64:
                raise ValueError("clarification keys/values must be short codes")
        return v


class Approval(_Model):
    approver: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9 .,'\-_()]+$")
    role: str = Field(default="Release Manager", max_length=60)
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = Field(default="", max_length=500)
