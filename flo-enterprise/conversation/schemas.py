"""Structured UI response contract for the conversational workspace.

The frontend renders ONLY these validated models. Charts use an allowlisted, versioned visualization schema
(`flo.viz/1.0`): a chart is data plus a declared type, never code. Unknown chart types, mismatched series lengths,
non-finite numbers or oversized payloads fail validation on the server before anything reaches the browser.
"""
from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

VIZ_SCHEMA_VERSION = "flo.viz/1.0"
CONTRACT_VERSION = "flo.conversation/1.0"

ChartType = Literal["line", "area", "stacked_area", "bar", "hbar", "stacked_bar", "grouped_bar", "combo", "waterfall", "donut", "treemap",
                    "heatmap", "matrix", "scatter", "geo", "tornado", "scorecard", "agent_graph"]
CHART_TYPES: tuple[str, ...] = ChartType.__args__  # type: ignore[attr-defined]
CARTESIAN = {"line", "area", "stacked_area", "bar", "hbar", "stacked_bar", "grouped_bar", "combo", "waterfall", "donut", "tornado"}
Provenance = Literal["platform_synthetic", "user_supplied", "calculated_from_user_inputs", "illustrative_assumption", "workflow_trace"]
Interaction = Literal["tooltip", "drilldown", "filter", "compare", "export", "explain", "methodology"]
MAX_POINTS = 5000


def _finite(v: float | None) -> float | None:
    if v is not None and not math.isfinite(v):
        raise ValueError("chart values must be finite numbers")
    return v


class MetricDef(BaseModel):
    id: str
    name: str
    definition: str
    formula: str = ""
    unit: str = ""


class Axis(BaseModel):
    label: str = ""
    unit: str = ""


class Series(BaseModel):
    name: str = Field(max_length=120)
    values: list[float | None]
    unit: str = ""
    metric_id: str | None = None
    render: Literal["auto", "bar", "line", "area"] = "auto"
    role: Literal["primary", "comparison", "baseline", "scenario", "limit"] = "primary"
    stack: str | None = None

    _v = field_validator("values")(lambda cls, v: [_finite(x) for x in v])


class Node(BaseModel):
    """Treemap / donut-with-hierarchy node, scatter point, geo point or graph node, depending on chart type."""
    id: str = ""
    name: str = Field(max_length=160)
    value: float | None = None
    x: float | None = None
    y: float | None = None
    size: float | None = None
    group: str | None = None
    parent: str | None = None
    lat: float | None = None
    lon: float | None = None
    color_value: float | None = None
    status: Literal["ok", "warn", "crit", "neutral", "denied", "skipped"] | None = None
    meta: dict[str, str | float | int | bool | None] = {}

    @model_validator(mode="after")
    def _check(self):
        for k in ("value", "x", "y", "size", "lat", "lon", "color_value"):
            _finite(getattr(self, k))
        return self


class Edge(BaseModel):
    source: str
    target: str
    label: str = ""


class Lineage(BaseModel):
    sources: list[str] = []
    methodology: str = ""
    as_of: str | None = None
    refreshed_at: str | None = None
    dataset_version: str | None = None
    semantic_layer_version: str | None = None
    synthetic: bool = True
    tools: list[str] = []


class FilterSpec(BaseModel):
    id: Literal["months", "group_by"]
    label: str
    options: list[str | int]
    value: str | int


class DrillSpec(BaseModel):
    dimension: str
    prompt_template: str = Field(description="Follow-up question; '{value}' is replaced by the clicked category")


class ChartSpec(BaseModel):
    schema_version: Literal["flo.viz/1.0"] = VIZ_SCHEMA_VERSION
    chart_id: str = Field(pattern=r"^[a-z0-9_]{2,60}$")
    chart_type: ChartType
    title: str = Field(max_length=140)
    subtitle: str = Field("", max_length=300)
    metrics: list[MetricDef] = []
    categories: list[str] = []
    series: list[Series] = []
    nodes: list[Node] = []
    edges: list[Edge] = []
    x_labels: list[str] = []
    y_labels: list[str] = []
    cells: list[list[float]] = []
    x_axis: Axis = Axis()
    y_axis: Axis = Axis()
    unit: str = ""
    reference_lines: list[dict[str, float | str]] = []
    filters: dict[str, str | int] = {}
    available_filters: list[FilterSpec] = []
    drilldown: DrillSpec | None = None
    interactions: list[Interaction] = ["tooltip", "export", "explain", "methodology"]
    lineage: Lineage = Lineage()
    provenance: Provenance = "platform_synthetic"
    agent: str = "visualization_agent"
    note: str = ""

    @model_validator(mode="after")
    def _shape(self):
        t = self.chart_type
        if t in CARTESIAN:
            if not self.series or not self.categories:
                raise ValueError(f"{t} requires categories and at least one series")
            for s in self.series:
                if len(s.values) != len(self.categories):
                    raise ValueError(f"series '{s.name}' has {len(s.values)} values for {len(self.categories)} categories")
        if t in ("heatmap", "matrix"):
            if not self.x_labels or not self.y_labels or not self.cells:
                raise ValueError(f"{t} requires x_labels, y_labels and cells")
            for c in self.cells:
                if len(c) != 3 or not (0 <= c[0] < len(self.x_labels)) or not (0 <= c[1] < len(self.y_labels)):
                    raise ValueError("cells must be [x_index, y_index, value] within the label ranges")
                _finite(c[2])
        if t in ("treemap", "scatter", "geo", "scorecard", "agent_graph") and not self.nodes:
            raise ValueError(f"{t} requires nodes")
        if t == "scatter" and any(n.x is None or n.y is None for n in self.nodes):
            raise ValueError("scatter nodes need x and y")
        if t == "geo" and any(n.lat is None or n.lon is None for n in self.nodes):
            raise ValueError("geo nodes need lat and lon")
        if t == "agent_graph":
            ids = {n.id for n in self.nodes}
            if any(e.source not in ids or e.target not in ids for e in self.edges):
                raise ValueError("agent_graph edges must reference node ids")
        n = len(self.categories) * max(1, len(self.series)) + len(self.nodes) + len(self.cells)
        if n > MAX_POINTS:
            raise ValueError(f"chart exceeds {MAX_POINTS} data points")
        return self


class KPI(BaseModel):
    id: str
    label: str
    value: float | None
    unit: Literal["CAD", "%", "bps", "count", "ratio", "x", "score", "years"]
    delta: float | None = None
    delta_unit: Literal["%", "pp", "bps", "CAD", "count", ""] = ""
    delta_label: str = ""
    trend: list[float] = []
    status: Literal["good", "warn", "crit", "neutral"] = "neutral"
    metric_id: str | None = None
    provenance: Provenance = "platform_synthetic"
    note: str = ""


class EvidenceRef(BaseModel):
    agent: str
    fact: str
    value: str = ""
    tool: str | None = None


class Insight(BaseModel):
    id: str
    section: Literal["current_state", "finding", "risk", "opportunity", "limitation"]
    title: str
    detail: str = ""
    severity: Literal["info", "positive", "warning", "critical"] = "info"
    evidence: list[EvidenceRef] = []


class Recommendation(BaseModel):
    id: str
    title: str
    priority: Literal["P1", "P2", "P3"]
    rationale: str
    evidence: list[EvidenceRef] = Field(min_length=1)
    expected_benefit: str
    kpis: list[str] = []
    complexity: Literal["low", "medium", "high"]
    dependencies: list[str] = []
    owner_function: str
    timeframe: Literal["0-30 days", "31-60 days", "61-90 days", "90+ days"]
    approvals_required: list[str] = []
    validation_criteria: list[str] = []
    requires_human_review: bool = True


class RoadmapPhase(BaseModel):
    name: str
    window: str
    objectives: list[str]
    actions: list[str]
    milestones: list[str]
    kpis: list[str]
    governance_gates: list[str] = []


class ImplementationPlan(BaseModel):
    title: str
    basis: str
    phases: list[RoadmapPhase]


class Table(BaseModel):
    table_id: str
    title: str
    columns: list[str]
    rows: list[list[str | float | int | bool | None]]
    provenance: Provenance = "platform_synthetic"


class Citation(BaseModel):
    document_id: str
    title: str
    section: str = ""
    version: str = ""


class Assumption(BaseModel):
    name: str
    value: str | float | int | None
    unit: str = ""
    source: str


class ApprovalRequirement(BaseModel):
    action: str
    reason: str
    approver_roles: list[str] = []
    status: Literal["required", "pending", "approved", "not_permitted"] = "required"
    approval_id: str | None = None


class DataFreshness(BaseModel):
    as_of: str | None = None
    refreshed_at: str | None = None
    dataset_version: str | None = None
    synthetic: bool = True
    sources: list[str] = []


class Intent(BaseModel):
    classifier: str
    intent: str
    label: str
    domain: str
    persona: str
    identity: dict[str, Any]
    entities: dict[str, Any] = {}
    metrics: list[str] = []
    time_horizon_months: int | None = None
    agents: list[str] = []
    agents_authorized: list[str] = []
    agents_not_authorized: list[str] = []
    tools: list[str] = []
    data_dependencies: list[str] = []
    charts: list[str] = []
    risk_classification: str = "internal"
    approval_requirements: list[str] = []
    follow_up_of: str | None = None
    modifiers: dict[str, Any] = {}


class Answer(BaseModel):
    headline: str
    summary: list[str] = []
    body: str = ""
    depth: Literal["executive", "analyst", "advisor", "client", "operations"] = "executive"


class WorkflowInfo(BaseModel):
    workflow_id: str | None = None
    route: str | None = None
    agents: list[str] = []
    tool_calls: list[dict] = []
    policy_decisions: list[dict] = []
    errors: list[dict] = []
    model: str = ""
    model_mode: str = ""
    injection: dict | None = None
    stages: list[dict] = []
    latency_ms: int | None = None


class Discovery(BaseModel):
    known: list[str] = []
    missing: list[str] = []
    questions: list[str] = []
    integrations: list[dict] = []


class MessageResponse(BaseModel):
    contract_version: Literal["flo.conversation/1.0"] = CONTRACT_VERSION
    conversation_id: str
    message_id: str
    request_id: str
    status: Literal["complete", "partial", "denied", "needs_input", "rejected", "cancelled", "error"]
    question: str
    answer: Answer
    persona: str
    intent: Intent
    insights: list[Insight] = []
    kpis: list[KPI] = []
    charts: list[ChartSpec] = []
    tables: list[Table] = []
    recommendations: list[Recommendation] = []
    implementation_plan: ImplementationPlan | None = None
    citations: list[Citation] = []
    data_freshness: DataFreshness = DataFreshness()
    assumptions: list[Assumption] = []
    warnings: list[str] = []
    approval_requirements: list[ApprovalRequirement] = []
    suggested_followups: list[str] = []
    discovery: Discovery | None = None
    trace_id: str | None = None
    trace_ids: list[str] = []
    workflow: WorkflowInfo = WorkflowInfo()
    created_at: str
