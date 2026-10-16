"""Typed shared state for the patient appointment-discovery workflow.

Only JSON-serialisable primitives are stored so LangGraph checkpoints stay portable.
Patient free text is NOT part of state (it is passed transiently to the safety
screen via the run context) to avoid persisting health details in checkpoints.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from pydantic import BaseModel, Field


def merge_dict(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


class PatientWorkflowState(BaseModel):
    workflow_id: str
    session_id: str | None = None
    authenticated_user_id: str | None = None
    user_role: str = "patient"
    data_mode: str = "SYNTHETIC"
    build_version: str = "1.4.0"
    scenario: str | None = None
    clock: str | None = None  # ISO UTC instant used for deterministic evaluation

    # intake
    requested_service: str | None = None
    search_location: str | None = None  # coarse label only (city / FSA)
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None
    existing_appointment: dict | None = None  # {"date": "YYYY-MM-DD", "days_until": int}
    criteria: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    request_booking: bool = False
    selected_slot_id: str | None = None
    idempotency_key: str | None = None
    expansions: int = 0

    # safety
    safety: dict = Field(default_factory=dict)

    # discovery & availability
    facility_candidates: list[str] = Field(default_factory=list)
    geo_results: list[dict] = Field(default_factory=list)
    raw_slots: list[dict] = Field(default_factory=list)
    failed_sources: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    availability_results: list[dict] = Field(default_factory=list)
    verification_status: dict = Field(default_factory=dict)
    data_quality: dict = Field(default_factory=dict)
    eligibility_results: list[dict] = Field(default_factory=list)
    wait_summary: dict = Field(default_factory=dict)
    recommendations: list[dict] = Field(default_factory=list)
    facility_cards: list[dict] = Field(default_factory=list)
    expansion_options: list[dict] = Field(default_factory=list)
    explanation: str | None = None

    # approvals & booking
    patient_consent: bool = False
    approval_id: str | None = None
    approval_status: str | None = None
    pending_question: dict | None = None
    booking_status: str = "NOT_REQUESTED"
    booking: dict = Field(default_factory=dict)
    notification: dict = Field(default_factory=dict)

    # bookkeeping
    source_references: Annotated[list[dict], operator.add] = Field(default_factory=list)
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)
    agent_trace: Annotated[list[dict], operator.add] = Field(default_factory=list)
    security_events: Annotated[list[dict], operator.add] = Field(default_factory=list)
    retry_count: int = 0
    token_usage: int = 0
    estimated_cost: float = 0.0
    trace_id: str | None = None
    workflow_status: str = "RUNNING"
    timestamps: Annotated[dict[str, Any], merge_dict] = Field(default_factory=dict)
