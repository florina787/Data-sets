"""Domain models shared by the graph, the agents and the API layer."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Task categories the supervisor can route."""

    PROJECT_STATUS = "project_status"
    RISK_ANALYSIS = "risk_analysis"
    SUMMARIZATION = "summarization"
    ISSUE_LOOKUP = "issue_lookup"
    COMPARISON = "comparison"
    ACTION_PLANNING = "action_planning"
    PEOPLE_LOOKUP = "people_lookup"
    GENERAL_QA = "general_qa"


class AgentName(str, Enum):
    """Graph nodes. Values are the LangGraph node names."""

    SUPERVISOR = "supervisor"
    RAG = "rag_agent"
    TOOLS = "tool_agent"
    ANALYSIS = "analysis_agent"
    RESPONSE = "response_agent"
    GUARDRAIL = "guardrail"


AGENT_LABELS: dict[str, str] = {
    AgentName.SUPERVISOR.value: "Supervisor",
    AgentName.RAG.value: "RAG",
    AgentName.TOOLS.value: "Tools",
    AgentName.ANALYSIS.value: "Analysis",
    AgentName.RESPONSE.value: "Response",
    AgentName.GUARDRAIL.value: "Guardrail",
}


class RetrievedChunk(BaseModel):
    """A chunk of evidence returned by the retriever, with full provenance."""

    chunk_id: str
    document_id: str
    filename: str
    title: str = ""
    section: str = ""
    chunk_index: int = 0
    text: str
    score: float = Field(default=0.0, description="Cosine similarity in [0, 1].")


class ToolCallRecord(BaseModel):
    """Result of executing one enterprise tool."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class Finding(BaseModel):
    """A statement together with the evidence keys that support it.

    ``sources`` holds chunk IDs (``<document_id>#cNNN``) or tool keys (``tool:<n>``).
    """

    text: str
    sources: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Structured output of the analysis agent."""

    summary: str = ""
    key_findings: list[Finding] = Field(default_factory=list)
    risks: list[Finding] = Field(default_factory=list)
    action_items: list[Finding] = Field(default_factory=list)
    recommendations: list[Finding] = Field(default_factory=list)


class Citation(BaseModel):
    """A numbered source shown to the user."""

    label: str = Field(description="Citation marker used in the answer, e.g. S1 or T1.")
    source_type: Literal["document", "tool"]
    document_id: str | None = None
    filename: str | None = None
    chunk_id: str | None = None
    section: str | None = None
    tool_name: str | None = None
    snippet: str = ""
    score: float | None = None


class GuardrailReport(BaseModel):
    """Outcome of the validation stage."""

    passed: bool = True
    grounding_score: float = 0.0
    citation_validity: float = 1.0
    unsupported_claims: list[str] = Field(default_factory=list)
    invalid_citations: list[str] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    needs_more_information: bool = False


class TokenUsage(BaseModel):
    """Token accounting for a request."""

    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    estimated: bool = Field(
        default=False,
        description="True in demo mode: counts are estimates of an equivalent prompt; no LLM was called.",
    )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            llm_calls=self.llm_calls + other.llm_calls,
            estimated=self.estimated or other.estimated,
        )


class AgentStep(BaseModel):
    """One node execution in the graph, for the execution panel and traces."""

    agent: str
    duration_ms: float
    detail: str = ""
    error: str | None = None
