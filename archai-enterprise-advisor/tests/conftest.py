"""Shared fixtures. Every test runs in DEMO mode with no API key."""

from __future__ import annotations

import logging

import pytest

from app.models.enums import ActionType, Industry, TaskType
from app.models.inputs import AssessmentRequest
from app.observability.tracing import METRICS
from app.scenarios import scenario_request
from app.services import run_assessment


@pytest.fixture(autouse=True)
def demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    logging.getLogger("archai").setLevel(logging.WARNING)


@pytest.fixture
def assess():
    def _run(scenario_id: str):
        return run_assessment(scenario_request(scenario_id))

    return _run


@pytest.fixture
def reset_metrics():
    METRICS.reset()
    yield
    METRICS.reset()


def agentic_request(industry: Industry, actions: list[ActionType]) -> AssessmentRequest:
    """A variable, cross-system investigation workload on a mature platform."""
    req = scenario_request("finops-incident-investigation")
    req.organization.industry = industry
    req.organization.regulatory_intensity = None
    req.use_case.action_types = actions
    req.use_case.hallucination_tolerance = 3
    req.use_case.primary_tasks = [TaskType.INVESTIGATION, TaskType.ORCHESTRATION]
    req.data_profile.confidential = False
    return req
