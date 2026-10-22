"""Typed shared state for the LangGraph workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AnalysisState(TypedDict, total=False):
    request_id: str
    session_id: str
    user_question: str
    dataset_mode: str
    selected_conversation_id: str | None
    started_at: float
    analysis_mode: str
    routing: dict
    conversation_history: list
    previous_turn: dict | None
    resolved_intent: dict
    intent_source: str
    analytical_plan: dict
    dataset_scope: dict
    tool_results: dict
    retrieved_evidence: list
    retrieval_meta: dict
    evidence: list
    verified_metrics: dict
    explanation: dict
    explanation_source: str
    visualizations: list
    graphs: list
    dashboard: dict | None
    evidence_review: dict | None
    recommendations: list
    uncertainty_notes: list
    governance_findings: list
    qa_results: dict
    # Parallel branches (specialist + retrieval) both append, so these use reducers.
    execution_trace: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    final_response: dict[str, Any]
