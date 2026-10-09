"""Typed domain models for the synthetic firm."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    PARTNER = "PARTNER"
    SENIOR_ASSOCIATE = "SENIOR_ASSOCIATE"
    ASSOCIATE = "ASSOCIATE"
    TRAINEE = "TRAINEE"
    PARALEGAL = "PARALEGAL"
    KNOWLEDGE_LAWYER = "KNOWLEDGE_LAWYER"
    AI_GOVERNANCE = "AI_GOVERNANCE"
    ADMIN = "ADMIN"


SENSITIVITY_ORDER = ["public", "internal", "confidential", "highly_confidential", "privileged"]


def sensitivity_rank(level: str | None) -> int:
    if level is None:
        return -1
    return SENSITIVITY_ORDER.index(level)


class User(BaseModel):
    user_id: str
    name: str
    role: Role
    practice_id: str | None = None
    email: str


class ClientAIPolicy(BaseModel):
    ai_allowed: bool
    internal_ai_allowed: bool
    external_ai_allowed: bool
    allowed_external_providers: list[str] = []
    max_external_classification: str | None = None
    human_review_required: bool = True
    client_facing_ai_disclosure: bool = True
    policy_summary: str
    evidence: dict


class Client(BaseModel):
    client_id: str
    name: str
    sector: str
    ai_policy: ClientAIPolicy


class Matter(BaseModel):
    matter_id: str
    name: str
    matter_number: str
    client_id: str
    practice_id: str
    jurisdiction: str
    responsible_partner: str
    description: str
    authorized_users: list[str]
    access_model: Literal["named_team", "practice_group"]
    confidentiality: str
    risk_level: str
    status: str


class EthicalWall(BaseModel):
    wall_id: str
    matter_ids: list[str]
    screened_users: list[str]
    reason: str
    established: str
    approved_by: str


class Section(BaseModel):
    section_id: str
    heading: str
    text: str


class Document(BaseModel):
    doc_id: str
    matter_id: str
    client_id: str
    title: str
    doc_type: str
    counterparty: str | None = None
    effective_date: str | None = None
    sensitivity: str
    access_label: str
    status: str = "active"
    duplicate_of: str | None = None
    ocr_status: str = "ok"
    sections: list[Section]

    def section(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.section_id == section_id), None)


class KnowledgeDoc(BaseModel):
    doc_id: str
    kind: str
    title: str
    access_label: str
    sensitivity: str
    client_id: str | None = None
    matter_id: str | None = None
    practice_id: str | None = None
    sections: list[Section]

    def section(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.section_id == section_id), None)


class PlaybookRule(BaseModel):
    rule_id: str
    topic: str
    section_id: str
    clause_patterns: list[str]
    exclude_patterns: list[str] = []
    result: Literal["ALIGNED", "DEVIATION", "ESCALATION_REQUIRED"]
    standard_position: str
    recommendation_patterns: list[str] = []


class Playbook(BaseModel):
    playbook_id: str
    practice_id: str
    title: str
    source_doc_id: str
    version: str
    rules: list[PlaybookRule]


class Provider(BaseModel):
    provider_id: str
    name: str
    type: str
    external: bool
    approval_status: str
    status: str
    allowed_classifications: list[str]
    practice_restrictions: list[str] = Field(default_factory=list, description="If non-empty, the provider may only be used for these practices.")
    matter_restrictions: list[str] = Field(default_factory=list, description="Matters on which the provider must never be used.")
    capabilities: list[str]
    human_review: str
    owner: str
    notes: str


class Workflow(BaseModel):
    workflow_id: str
    name: str
    practice_ids: list[str]
    output_types: list[str]
    destinations: list[str]
    providers: list[str]
    agents: list[str]
    prompts: list[str]
    gates: list[str]
    hitl_level: int
    status: str
