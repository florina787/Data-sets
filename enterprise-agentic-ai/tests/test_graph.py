"""End-to-end LangGraph execution in demo mode and with a mocked live LLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.container import build_container
from app.rag.embeddings import HashingEmbedding
from tests.conftest import DEMO_QUESTIONS, FakeLLM, make_settings

EXPECTED_ROUTES = {
    "project_status": ["Supervisor", "RAG", "Tools", "Response", "Guardrail"],
    "risk_analysis": ["Supervisor", "RAG", "Analysis", "Response", "Guardrail"],
    "summarization": ["Supervisor", "RAG", "Analysis", "Response", "Guardrail"],
    "issue_lookup": ["Supervisor", "Tools", "Response", "Guardrail"],
    "comparison": ["Supervisor", "RAG", "Tools", "Analysis", "Response", "Guardrail"],
    "action_planning": ["Supervisor", "RAG", "Tools", "Analysis", "Response", "Guardrail"],
}


@pytest.mark.parametrize("question,intent", DEMO_QUESTIONS.items())
def test_demo_questions_end_to_end(demo_container, question: str, intent: str) -> None:
    response = demo_container.copilot.ask(question)
    assert response.intent == intent
    assert response.route == EXPECTED_ROUTES[intent]
    assert response.execution_path[0] == "supervisor" and response.execution_path[-1] == "guardrail"
    for section in ("### Answer", "### Key Findings", "### Recommended Actions", "### Sources"):
        assert section in response.answer
    assert response.citations, "answers must cite sources"
    assert response.confidence >= 0.5
    assert response.errors == []
    assert response.token_usage.llm_calls == 0 and response.token_usage.estimated  # demo mode: no LLM
    assert {s.agent for s in response.agent_steps} >= {"supervisor", "response_agent", "guardrail"}


def test_issue_lookup_lists_blockers(demo_container) -> None:
    response = demo_container.copilot.ask("Which issues are blocking the October release?")
    for issue in ("PHX-214", "PHX-221", "PHX-230"):
        assert issue in response.answer
    assert [c.tool_name for c in response.tool_calls] == ["get_open_issues"]
    assert not response.retrieved_chunks


def test_summary_targets_named_document(demo_container) -> None:
    response = demo_container.copilot.ask("Summarize the architecture document.")
    assert {c.document_id for c in response.retrieved_chunks} == {"ai_platform_architecture_notes"}


def test_citations_point_to_real_chunks(demo_container) -> None:
    response = demo_container.copilot.ask("What are the major delivery risks?")
    chunk_ids = {c.chunk_id for c in response.retrieved_chunks}
    for citation in response.citations:
        if citation.source_type == "document":
            assert citation.chunk_id in chunk_ids
            assert citation.filename and citation.document_id


def test_out_of_scope_question_asks_for_more_information(demo_container) -> None:
    response = demo_container.copilot.ask("What is the price of bananas in Tokyo?")
    assert "More information is required" in response.answer
    assert response.confidence < 0.2
    assert response.guardrail.needs_more_information


def test_traces_recorded(demo_container) -> None:
    demo_container.copilot.ask("What is the current status of Project Phoenix?")
    summary = demo_container.traces.summary()
    assert summary["total_requests"] >= 1
    trace = summary["recent_traces"][0]
    assert trace["request_id"] and trace["timestamp"]
    assert trace["execution_path"][0] == "supervisor"
    assert trace["tool_calls"] and trace["retrieval_count"] > 0 and trace["latency_ms"] > 0


def test_live_mode_with_mocked_llm(tmp_path: Path) -> None:
    llm = FakeLLM()
    settings = make_settings(tmp_path, app_mode="live", anthropic_api_key="test-key-not-real")
    container = build_container(settings, llm=llm, embedding=HashingEmbedding())
    response = container.copilot.ask("How is Phoenix doing?")
    assert response.mode == "live"
    assert response.intent == "project_status"
    assert "structured:IntentDecision" in llm.calls and "generate" in llm.calls
    assert response.token_usage.llm_calls >= 3 and not response.token_usage.estimated
    assert "### Sources" in response.answer  # generated from citation labels, not by the LLM
    assert response.errors == []


def test_live_mode_llm_outage_falls_back_visibly(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, app_mode="live", anthropic_api_key="test-key-not-real")
    container = build_container(settings, llm=FakeLLM(fail=True), embedding=HashingEmbedding())
    response = container.copilot.ask("What is the current status of Project Phoenix?")
    assert "### Answer" in response.answer
    assert any("fell back" in e for e in response.errors)
