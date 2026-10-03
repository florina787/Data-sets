"""Supervisor intent classification and routing."""

from __future__ import annotations

import pytest

from app.agents.supervisor import ROUTING_PLANS, SupervisorAgent, classify_intent_rules, route_from_supervisor
from app.models.domain import AgentName, Intent
from tests.conftest import DEMO_QUESTIONS


@pytest.mark.parametrize("question,expected", DEMO_QUESTIONS.items())
def test_demo_questions_classified(question: str, expected: str) -> None:
    intent, reasoning = classify_intent_rules(question)
    assert intent.value == expected
    assert reasoning


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Who is the engineering manager for Phoenix?", Intent.PEOPLE_LOOKUP),
        ("What is the data residency requirement?", Intent.GENERAL_QA),
        ("Give me an overview of the PRD", Intent.SUMMARIZATION),
    ],
)
def test_other_intents(question: str, expected: Intent) -> None:
    assert classify_intent_rules(question)[0] is expected


def test_demo_questions_take_different_paths() -> None:
    plans = {tuple(ROUTING_PLANS[Intent(v)]) for v in DEMO_QUESTIONS.values()}
    assert len(plans) >= 4, "demo questions should exercise several distinct graph paths"


def test_supervisor_first_visit_plans_route(demo_container) -> None:
    supervisor = SupervisorAgent(demo_container.repository)
    update = supervisor({"user_query": "Compare the project status with the delivery metrics."})
    assert update["intent"] is Intent.COMPARISON
    assert update["next_agent"] == AgentName.RAG.value
    assert update["plan"] == [AgentName.TOOLS.value, AgentName.ANALYSIS.value]


def test_supervisor_resolves_project_from_release(demo_container) -> None:
    supervisor = SupervisorAgent(demo_container.repository)
    update = supervisor({"user_query": "Which issues are blocking the October release?"})
    assert update["project_ids"] == ["PRJ-PHOENIX"]
    assert update["next_agent"] == AgentName.TOOLS.value


def test_supervisor_finishes_when_plan_exhausted(demo_container) -> None:
    supervisor = SupervisorAgent(demo_container.repository)
    update = supervisor({"user_query": "x", "intent": Intent.GENERAL_QA, "plan": [], "execution_path": ["rag_agent"]})
    assert update["next_agent"] == AgentName.RESPONSE.value
    assert route_from_supervisor({**update}) == AgentName.RESPONSE.value


def test_supervisor_adds_tools_when_retrieval_empty(demo_container) -> None:
    supervisor = SupervisorAgent(demo_container.repository)
    state = {
        "user_query": "phoenix",
        "intent": Intent.GENERAL_QA,
        "plan": [],
        "project_ids": ["PRJ-PHOENIX"],
        "retrieved_documents": [],
        "execution_path": ["supervisor", "rag_agent"],
    }
    assert supervisor(state)["next_agent"] == AgentName.TOOLS.value


def test_supervisor_uses_llm_when_available(demo_container, fake_llm) -> None:
    update = SupervisorAgent(demo_container.repository, fake_llm)({"user_query": "How is Phoenix doing?"})
    assert update["intent"] is Intent.PROJECT_STATUS
    assert update["token_usage"].llm_calls == 1
    assert fake_llm.calls == ["structured:IntentDecision"]


def test_supervisor_falls_back_to_rules_on_llm_error(demo_container) -> None:
    from tests.conftest import FakeLLM

    update = SupervisorAgent(demo_container.repository, FakeLLM(fail=True))(
        {"user_query": "What are the major delivery risks?"}
    )
    assert update["intent"] is Intent.RISK_ANALYSIS
    assert any("fell back" in e for e in update["errors"])
