"""LLM provider adapters. Workbook operations never depend on these: they are only used to
interpret requests the deterministic planner cannot classify and to choose tool calls.

* ``demo``      - no model; FloPilot runs entirely on its deterministic planner.
* ``anthropic`` - Claude via the official Anthropic Python SDK (server-side API key only).

Adding a provider means implementing ``LLMProvider.complete`` and returning ``LLMResponse``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..common import AppError
from ..config import get_settings


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str
    tool_uses: list[ToolUse]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    model: str
    raw_content: Any = None  # provider-native content, appended back to history unchanged
    notes: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: Any = None) -> None:
        try:
            import anthropic  # optional dependency (requirements-llm.txt)
        except ImportError as exc:  # pragma: no cover - depends on installation
            raise AppError("llm_unavailable", "The Anthropic SDK is not installed on the server.", 503) from exc

        self._anthropic = anthropic
        # The key is read from ANTHROPIC_API_KEY on the server; it never reaches the browser.
        self.client = client or anthropic.Anthropic(timeout=60.0, max_retries=2)
        self.model = get_settings().llm_model

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        a = self._anthropic
        settings = get_settings()
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=tools,
                output_config={"effort": settings.llm_effort},
                # Route policy declines to a fallback model chosen by the API (server-side fallbacks).
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except a.RateLimitError as exc:
            raise AppError("llm_rate_limited", "The AI service is busy. Try again in a moment.", 503, retryable=True) from exc
        except a.APIStatusError as exc:
            raise AppError("llm_error", f"The AI service returned an error ({exc.status_code}).", 502) from exc
        except a.APIConnectionError as exc:
            raise AppError("llm_unreachable", "The AI service could not be reached.", 503, retryable=True) from exc
        text = "".join(b.text for b in resp.content if b.type == "text")
        uses = [ToolUse(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        return LLMResponse(text=text, tool_uses=uses, stop_reason=resp.stop_reason or "", input_tokens=resp.usage.input_tokens,
                           output_tokens=resp.usage.output_tokens, model=resp.model, raw_content=resp.content)


def get_provider() -> LLMProvider | None:
    settings = get_settings()
    if settings.llm_provider == "anthropic" and (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        return AnthropicProvider()
    return None


def provider_status() -> dict:
    settings = get_settings()
    configured = settings.llm_provider == "anthropic" and bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    return {
        "provider": settings.llm_provider if configured else "demo",
        "model": settings.llm_model if configured else None,
        "mode": "llm" if configured else "deterministic-demo",
        "label": (f"AI model: {settings.llm_model}" if configured else
                  "Demo mode — deterministic rules, no AI model connected"),
    }
