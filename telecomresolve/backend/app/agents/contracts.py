"""Validated input/output contracts for the four agent nodes."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["AREA_INCIDENT", "LINE_IMPAIRMENT", "EQUIPMENT_FAULT", "HOME_NETWORK",
                   "UNDECLARED_AREA_ISSUE", "INSUFFICIENT_EVIDENCE", "CONTRADICTORY_EVIDENCE"]
CAUSAL_CATEGORIES = ("AREA_INCIDENT", "LINE_IMPAIRMENT", "EQUIPMENT_FAULT", "HOME_NETWORK",
                     "UNDECLARED_AREA_ISSUE")
Sufficiency = Literal["strong", "moderate", "weak", "insufficient"]
SpecialRequest = Literal["restoration_guarantee", "bill_credit", "compensation", "appointment_slot"]
KNOWN_PRIOR_ACTIONS = ("modem_restart", "remote_line_check", "filter_check", "power_adapter_check",
                       "wifi_check")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------- Triage ----------------
class TriageInput(Strict):
    case_id: str
    product: str
    complaint_text: str
    prior_contact_count: int


class TriageOutput(Strict):
    symptom_pattern: Literal["intermittent_disconnection", "total_outage", "slow_speed", "unknown"]
    frequency: str = Field(description="Customer-reported frequency, verbatim-ish; 'unknown' if absent")
    affected_devices: Literal["all", "wifi_only", "wired_only", "unknown"]
    onset: str = Field(description="Customer-reported onset ('this morning', 'this week', 'unknown')")
    lookback_hours: int = Field(ge=1, le=168)
    customer_reported_actions: list[str]
    special_requests: list[SpecialRequest]
    mentions_prior_incident: bool
    clarifying_questions: list[str]
    missing_information: list[str]


# ---------------- Evidence ----------------
class EvidenceItem(Strict):
    ref_id: str
    source_type: Literal["diagnostic_series", "diagnostic_sample", "peer_health", "incident",
                         "service_mapping", "support_interaction", "customer_statement",
                         "equipment", "knowledge"]
    source_id: str
    source_version: str
    authority: Literal["measurement", "system_record", "policy", "runbook", "guide",
                       "customer_statement", "agent_note", "customer_note", "analyst_note"]
    kind: Literal["observation", "statement", "note", "policy", "record"]
    excerpt: str
    freshness: Literal["fresh", "stale", "n/a"]
    supports: list[str] = Field(default_factory=list)
    opposes: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    retrieved_at: str
    data: dict = Field(default_factory=dict)


class EvidenceBundle(Strict):
    window_start: str
    window_end: str
    items: list[EvidenceItem]
    facts: list[str]
    missing_evidence: list[str]
    prior_actions: list[dict]
    knowledge_queries: list[str]


class EvidencePlanLLM(Strict):
    """LIVE-mode output of the evidence node: knowledge queries only. Tool
    execution itself stays deterministic and scope-checked."""

    knowledge_queries: list[str] = Field(max_length=4)


# ---------------- Diagnosis ----------------
class HypothesisOut(Strict):
    category: Category
    statement: str
    supporting_refs: list[str]
    opposing_refs: list[str]
    sufficiency: Sufficiency = "insufficient"


class DiagnosisOutput(Strict):
    hypotheses: list[HypothesisOut]
    conclusion: Category
    observations: list[str]
    needs_more_evidence: list[str]
    escalate: bool
    summary: str


class DiagnosisLLM(Strict):
    hypotheses: list[HypothesisOut]
    summary: str


# ---------------- Action planning ----------------
class PriorIntervention(Strict):
    source_ref: str
    action: str
    outcome: str
    repeated_in_recommendation: bool
    justification: str


class RefusedRequest(Strict):
    request: str
    reason: str
    citations: list[str]


class RecommendationDraft(Strict):
    action_type: str
    payload: dict
    purpose: str
    prerequisites: list[str]
    evidence_refs: list[str]
    uncertainty: str
    prior_interventions: list[PriorIntervention]
    refused_requests: list[RefusedRequest]
    alternatives: list[dict]


class ActionPlanLLM(Strict):
    action_type: str
    purpose: str
    uncertainty: str
