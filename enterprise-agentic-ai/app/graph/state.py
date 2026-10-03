"""Typed LangGraph state for the copilot workflow.

Fields that several nodes append to use reducers (``Annotated[..., reducer]``)
so LangGraph merges partial updates instead of overwriting them.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.models.domain import (
    AgentStep,
    AnalysisResult,
    Citation,
    GuardrailReport,
    Intent,
    RetrievedChunk,
    TokenUsage,
    ToolCallRecord,
)


def add_usage(left: TokenUsage | None, right: TokenUsage | None) -> TokenUsage:
    """Reducer that sums token usage reported by individual nodes."""
    return (left or TokenUsage()) + (right or TokenUsage())


class CopilotState(TypedDict, total=False):
    """State carried through one copilot request."""

    # --- input -----------------------------------------------------------
    request_id: str
    user_query: str
    top_k: int
    messages: Annotated[list[AnyMessage], add_messages]

    # --- supervisor ------------------------------------------------------
    intent: Intent
    intent_reasoning: str
    project_ids: list[str]
    plan: list[str]  # remaining specialist agents to run, in order
    next_agent: str

    # --- specialists -----------------------------------------------------
    retrieved_documents: list[RetrievedChunk]
    tool_results: list[ToolCallRecord]
    analysis: AnalysisResult | None

    # --- response + validation -----------------------------------------
    draft_answer: str
    final_answer: str
    citations: list[Citation]
    guardrail: GuardrailReport
    confidence: float

    # --- telemetry (append-only via reducers) ----------------------------
    execution_path: Annotated[list[str], operator.add]
    agent_steps: Annotated[list[AgentStep], operator.add]
    token_usage: Annotated[TokenUsage, add_usage]
    errors: Annotated[list[str], operator.add]
