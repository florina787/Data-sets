"""Shared fixtures. Tests never call a real LLM and never download models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from app.config.settings import PROJECT_ROOT, Settings
from app.container import Container, build_container
from app.llm.provider import LLMError, LLMResult
from app.models.domain import TokenUsage
from app.rag.embeddings import HashingEmbedding

T = TypeVar("T", bound=BaseModel)

DEMO_QUESTIONS = {
    "What is the current status of Project Phoenix?": "project_status",
    "What are the major delivery risks?": "risk_analysis",
    "Summarize the architecture document.": "summarization",
    "Which issues are blocking the October release?": "issue_lookup",
    "Compare the project status with the delivery metrics.": "comparison",
    "What actions should the engineering manager take this week?": "action_planning",
}


def make_settings(tmp: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = dict(
        _env_file=None,
        app_mode="demo",
        embedding_provider="hashing",
        chroma_dir=tmp / "chroma",
        trace_dir=tmp / "traces",
        uploads_dir=tmp / "uploads",
        documents_dir=PROJECT_ROOT / "data" / "documents",
        synthetic_data_dir=PROJECT_ROOT / "data" / "synthetic",
        log_level="WARNING",
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
def demo_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    return make_settings(tmp_path_factory.mktemp("demo"))


@pytest.fixture(scope="session")
def demo_container(demo_settings: Settings) -> Container:
    return build_container(demo_settings, embedding=HashingEmbedding())


class FakeLLM:
    """Stand-in for Claude. Returns schema-appropriate canned outputs and counts calls."""

    model_name = "fake-claude"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def _usage(self) -> TokenUsage:
        return TokenUsage(input_tokens=100, output_tokens=50, llm_calls=1)

    def generate(self, system: str, prompt: str) -> LLMResult:
        self.calls.append("generate")
        if self.fail:
            raise LLMError("simulated outage")
        text = (
            "### Answer\nProject Phoenix is AMBER at 68% complete and targets release 2026.10 [T1].\n\n"
            "### Key Findings\n- Open release blockers include PHX-214, PHX-221 and PHX-230 [T2].\n\n"
            "### Recommended Actions\n- Resolve the release blockers before code freeze [T2]."
        )
        return LLMResult(text=text, usage=self._usage())

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        self.calls.append(f"structured:{schema.__name__}")
        if self.fail:
            raise LLMError("simulated outage")
        name = schema.__name__
        if name == "IntentDecision":
            data: dict[str, Any] = {"intent": "project_status", "project_ids": ["PRJ-PHOENIX"], "reasoning": "status question"}
        elif name == "ToolPlan":
            data = {
                "calls": [
                    {"tool_name": "get_project_status", "arguments": {"project_id": "PRJ-PHOENIX"}},
                    {"tool_name": "get_open_issues", "arguments": {"project_id": "PRJ-PHOENIX", "blocking_only": True}},
                ]
            }
        elif name == "AnalysisResult":
            data = {"summary": "Phoenix is at risk.", "key_findings": [{"text": "Three blockers are open.", "sources": ["T2"]}]}
        else:
            raise LLMError(f"unexpected schema {name}")
        return schema.model_validate(data), self._usage()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
