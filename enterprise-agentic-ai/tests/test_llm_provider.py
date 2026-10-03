"""LLM provider construction (offline; no API calls are made)."""

from __future__ import annotations

from app.config.settings import Settings
from app.llm.provider import AnthropicProvider, build_llm_provider


def test_demo_mode_builds_no_llm() -> None:
    assert build_llm_provider(Settings(_env_file=None)) is None


def test_live_provider_omits_temperature_by_default() -> None:
    # Some Claude models reject non-default temperatures, so it must be opt-in.
    settings = Settings(_env_file=None, app_mode="live", anthropic_api_key="test-key-not-real")
    provider = AnthropicProvider(settings)
    assert provider._llm.temperature is None
    assert provider.model_name == settings.anthropic_model


def test_live_provider_passes_explicit_temperature() -> None:
    settings = Settings(_env_file=None, app_mode="live", anthropic_api_key="test-key-not-real", llm_temperature=0.2)
    assert AnthropicProvider(settings)._llm.temperature == 0.2
