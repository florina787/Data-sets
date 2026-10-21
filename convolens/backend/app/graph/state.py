"""The single state model shared by every Flo graph node."""
from __future__ import annotations

from typing import TypedDict


class FloState(TypedDict, total=False):
    request_id: str
    session_id: str
    messages: list[dict]          # prior turns (question + finding summaries) and this question
    dataset_id: str
    mode: str                     # demo | connected
    page: str
    active_filters: dict          # explicit filters selected in the UI
    resolved_filters: dict        # active filters + scope taken from the question (recorded separately)
    scope_notes: list[str]
    question: str
    question_type: str
    unsupported_reason: str | None
    analysis_plan: list[dict]     # [{id, tool, args, purpose, status, depends_on}]
    tool_results: list[dict]      # [{step_id, tool, purpose, args, status, result, summary}]
    evidence_ids: list[str]
    validated_evidence: list[dict]
    validated_metrics: list[dict]
    limitations: list[str]
    proposed_action: dict | None
    approval_state: str           # not_required | pending | approved | saved_as_proposed | rejected
    approval: dict | None
    action_record_id: int | None
    errors: list[dict]
    response: dict | None
    iterations: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    started_at: float
    model_id: str | None
    prompt_versions: dict
    visited: list[str]
