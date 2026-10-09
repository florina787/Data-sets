"""Typed API contracts (validated inputs, structured Copilot response)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ID = r"^[A-Z]{1,8}(-[A-Z0-9]{1,12}){1,4}$"
DESTINATIONS = Literal["internal", "external_client", "external_court", "external_public", "external_counterparty"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(Strict):
    matter_id: str = Field(pattern=ID)
    message: str = Field(min_length=1, max_length=2000)
    selected_finding_id: str | None = Field(default=None, max_length=80)
    destination: DESTINATIONS | None = None


class MatterGuardRequest(Strict):
    matter_id: str = Field(pattern=ID)
    provider_id: str | None = Field(default=None, pattern=ID)
    destination: DESTINATIONS = "internal"
    intent: str = Field(default="general", max_length=40)
    doc_ids: list[str] | None = Field(default=None, max_length=500)


class RoutingRequest(Strict):
    matter_id: str = Field(pattern=ID)
    task: str = Field(min_length=1, max_length=2000)
    destination: DESTINATIONS | None = None


class KnowledgeSearchRequest(Strict):
    matter_id: str = Field(pattern=ID)
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class AnalyzeRequest(Strict):
    matter_id: str = Field(pattern=ID)
    analysis_type: Literal["change_of_control", "summary", "obligations", "timeline", "entities", "comparison"]
    doc_ids: list[str] = Field(default_factory=list, max_length=2)


class PlaybookItem(Strict):
    id: str = Field(max_length=80)
    text: str = Field(min_length=1, max_length=4000)
    kind: Literal["clause", "recommendation"] = "clause"


class PlaybookCheckRequest(Strict):
    playbook_id: str = Field(pattern=ID)
    items: list[PlaybookItem] = Field(min_length=1, max_length=200)


class CitationIn(Strict):
    doc_id: str = Field(max_length=40)
    section_id: str | None = Field(default=None, max_length=40)
    quote: str | None = Field(default=None, max_length=2000)


class PropositionIn(Strict):
    pid: str = Field(max_length=80)
    claim: str = Field(min_length=1, max_length=2000)
    citation: CitationIn | None = None
    material: bool = True


class CitationVerifyRequest(Strict):
    matter_id: str = Field(pattern=ID)
    propositions: list[PropositionIn] = Field(min_length=1, max_length=500)


class AssuranceRequest(Strict):
    matter_id: str = Field(pattern=ID)
    propositions: list[PropositionIn] = Field(default_factory=list, max_length=500)
    work_product_id: str | None = Field(default=None, max_length=80)
    destination: DESTINATIONS = "internal"


class PrivilegeRequest(Strict):
    matter_id: str = Field(pattern=ID)
    doc_ids: list[str] = Field(default_factory=list, max_length=200)
    destination: DESTINATIONS = "internal"


class DraftRequest(Strict):
    matter_id: str = Field(pattern=ID)
    draft_type: Literal["memo", "due_diligence_report", "client_communication"] = "memo"
    destination: DESTINATIONS = "internal"


class ReviewRequest(Strict):
    work_product_id: str = Field(min_length=3, max_length=80)
    destination: DESTINATIONS | None = None
    comment: str = Field(default="", max_length=2000)


class ChangeOpsRequest(Strict):
    policy_text: str = Field(min_length=5, max_length=1000)


class ChangeApproveRequest(Strict):
    change_id: str = Field(max_length=40)
    policy_text: str = Field(min_length=5, max_length=1000)


class EvaluationRequest(Strict):
    target: str = Field(max_length=60)


class PromoteRequest(Strict):
    target: str = Field(max_length=60)
    run_id: str = Field(max_length=40)


class UploadValidateRequest(Strict):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(max_length=8_000_000)


# ---- responses -----------------------------------------------------------------------------
class Metric(BaseModel):
    label: str
    value: Any
    tone: str | None = None
    hint: str | None = None


class Action(BaseModel):
    id: str
    label: str
    kind: Literal["panel", "copilot", "navigate", "review"]
    payload: dict = {}


class Card(BaseModel):
    type: str
    title: str
    severity: str | None = None
    body: str | None = None
    metrics: list[Metric] = []
    items: list[Any] = []
    actions: list[Action] = []


class TraceStep(BaseModel):
    step: int
    label: str
    agent: str
    status: Literal["ok", "warn", "blocked", "pending", "skipped", "error"]
    detail: str | None = None
    duration_ms: float | None = None
    node: str | None = None


class CopilotResponse(BaseModel):
    request_id: str
    user_id: str
    matter_id: str | None
    answer: str
    status: Literal["COMPLETED", "REVIEW_REQUIRED", "BLOCKED", "ACCESS_DENIED", "HUMAN_DECISION_REQUIRED", "NEEDS_INPUT",
                    "HALTED", "ERROR"]
    risk: str
    intent: str
    findings: list[dict] = []
    evidence: list[dict] = []
    citations: list[dict] = []
    playbook_deviations: list[dict] = []
    actions: list[Action] = []
    cards: list[Card] = []
    agent_trace: list[TraceStep] = []
    approval_required: bool
    approval: dict | None = None
    matterguard: dict | None = None
    routing: dict | None = None
    suitability: dict | None = None
    assurance: dict | None = None
    privilege_flags: list[dict] = []
    sources: list[dict] = []
    draft: dict | None = None
    work_product_id: str | None = None
    analysis: dict | None = None
    review_summary: dict | None = None
    value_estimate: dict | None = None
    injection_flags: list[dict] = []
    audit_event_ids: list[str] = []
    errors: list[str] = []
    metrics: dict
