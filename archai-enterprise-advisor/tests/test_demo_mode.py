"""DEMO mode makes zero paid LLM calls and needs no API key."""

from __future__ import annotations

import socket
import sys

import pytest

from app.config.settings import Settings, get_settings
from app.llm import provider
from app.llm.provider import AnthropicNarrator, DemoModeViolation, TemplateNarrator, get_narrator
from app.observability.tracing import METRICS
from app.resilience.patterns import RetryPolicy
from app.scenarios import list_scenarios, scenario_request
from app.services import run_assessment


# 10
def test_demo_mode_performs_zero_paid_llm_calls(monkeypatch, reset_metrics):
    def no_network(*args, **kwargs):
        raise AssertionError("Network access attempted in DEMO mode")

    def no_paid_client(*args, **kwargs):
        raise AssertionError("Paid LLM client constructed in DEMO mode")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(AnthropicNarrator, "__init__", no_paid_client)
    for s in list_scenarios():
        r = run_assessment(scenario_request(s["id"]))
        assert r.trace.paid_model_calls == 0
        assert r.trace.model_calls == 0
        assert r.explanation_source == "deterministic-template"
    assert METRICS.get("paid_llm_calls_total") == 0
    assert "langchain_anthropic" not in sys.modules
    assert "anthropic" not in sys.modules


def test_demo_mode_is_default(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert Settings(_env_file=None).demo_mode is True


def test_paid_client_cannot_be_constructed_in_demo_mode():
    with pytest.raises(DemoModeViolation):
        AnthropicNarrator(get_settings())


# 15
def test_missing_api_key_does_not_break_demo_mode(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = get_settings()
    assert settings.has_api_key is False
    assert isinstance(get_narrator(settings), TemplateNarrator)
    r = run_assessment(scenario_request("banking-policy-knowledge"))
    assert r.decision.ai_recommended


def test_live_mode_without_key_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = get_settings()
    assert settings.live_ai_enabled is False
    assert isinstance(get_narrator(settings), TemplateNarrator)
    r = run_assessment(scenario_request("banking-transaction-rules"))
    assert r.trace.paid_model_calls == 0


def test_placeholder_key_is_not_treated_as_real(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your_own_key_here")
    assert get_settings().has_api_key is False


def test_live_narration_cannot_change_decision():
    """LLM output that drops the decided architecture/verdict is discarded (fake model, no network)."""

    class FakeResponse:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeModel:
        def __init__(self, content: str) -> None:
            self.content = content

        def invoke(self, messages):
            return FakeResponse(self.content)

    facts = {"architecture_label": "Keep Existing Transaction Rules Engine", "agentic_verdict_label": "AGENTIC AI NOT RECOMMENDED"}
    narrator = AnthropicNarrator.__new__(AnthropicNarrator)  # bypass client construction
    narrator._retry = RetryPolicy(max_attempts=1)
    narrator._model = FakeModel("We recommend replacing the rules engine with autonomous agents.")
    assert narrator.narrate(facts, "TEMPLATE") == "TEMPLATE"
    consistent = "Keep Existing Transaction Rules Engine. AGENTIC AI NOT RECOMMENDED because the workload is deterministic."
    narrator._model = FakeModel(consistent)
    assert narrator.narrate(facts, "TEMPLATE") == consistent


def test_live_mode_with_key_selects_llm_narrator(monkeypatch):
    class FakeNarrator:
        source = "llm-narration"

        def __init__(self, settings):
            self.settings = settings

    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-not-a-real-key")
    monkeypatch.setattr(provider, "AnthropicNarrator", FakeNarrator)
    assert isinstance(get_narrator(get_settings()), FakeNarrator)


def test_api_key_never_in_settings_repr(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-value-supersecretvalue")
    s = get_settings()
    assert "supersecretvalue" not in repr(s)
    assert "supersecretvalue" not in s.model_dump_json()
