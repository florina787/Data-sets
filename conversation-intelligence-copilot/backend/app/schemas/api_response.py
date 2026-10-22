"""Versioned API response contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    selected_conversation_id: str | None = Field(None, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")


class ChatResponse(BaseModel):
    version: str
    request_id: str
    session_id: str
    status: Literal["completed", "insufficient_data", "unsupported", "needs_review", "failed"]
    question: str
    resolved_intent: dict[str, Any]
    dataset_scope: dict[str, Any]
    plan: dict[str, Any]
    headline: str
    answer: str
    key_points: list[str] = []
    metrics: list[dict[str, Any]] = []
    rankings: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    uncertainty_notes: list[str] = []
    method_notes: list[str] = []
    follow_up_questions: list[str] = []
    execution_trace_id: str
    model_metadata: dict[str, Any] = {}
    quality_status: dict[str, Any] = {}
    governance: list[dict[str, Any]] = []
    human_review_required: bool = False
    errors: list[dict[str, Any]] = []


class AnalyticsQuery(BaseModel):
    operation: str
    params: dict[str, Any] = {}
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    window: dict[str, Any] | None = None
    topics: list[str] = []
    products: list[str] = []
    domains: list[str] = []
    agents: list[str] = []
    sentiments: list[str] = []


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    k: int = Field(5, ge=1, le=20)
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    topics: list[str] = []
    sentiments: list[str] = []
    window: dict[str, Any] | None = None
