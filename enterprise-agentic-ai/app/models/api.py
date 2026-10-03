"""Pydantic request/response models for the FastAPI layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.domain import (
    AgentStep,
    AnalysisResult,
    Citation,
    GuardrailReport,
    RetrievedChunk,
    ToolCallRecord,
)


class ChatRequest(BaseModel):
    """A business question sent to the copilot."""

    question: str = Field(min_length=3, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Question must contain at least 3 non-whitespace characters.")
        return value


class TokenUsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    llm_calls: int
    estimated: bool


class ChatResponse(BaseModel):
    """Grounded answer plus everything needed to explain how it was produced."""

    request_id: str
    mode: str
    answer: str
    intent: str
    intent_reasoning: str = ""
    route: list[str]
    execution_path: list[str]
    agent_steps: list[AgentStep]
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    tool_calls: list[ToolCallRecord]
    analysis: AnalysisResult | None = None
    guardrail: GuardrailReport
    confidence: float
    latency_ms: float
    token_usage: TokenUsageOut
    errors: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    chunks_indexed: int
    replaced_existing: bool


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    title: str
    chunks: int


class HealthResponse(BaseModel):
    status: str
    version: str
    mode: str
    live_llm_configured: bool
    llm_model: str | None
    embedding_backend: str
    embedding_fallback_reason: str | None = None
    documents_indexed: int
    chunks_indexed: int
    tools_available: int
    langsmith_tracing: bool


class ToolInfo(BaseModel):
    """MCP-compatible tool description (name, description, inputSchema)."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(serialization_alias="inputSchema")

    model_config = {"populate_by_name": True}


class MetricsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    avg_confidence: float
    total_tokens: int
    llm_calls: int
    intent_counts: dict[str, int]
    tool_usage: dict[str, int]
    agent_usage: dict[str, int]
    recent_traces: list[dict[str, Any]]
