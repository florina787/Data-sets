"""LLM provider abstraction.

Agents depend on the small :class:`LLMProvider` protocol, not on a concrete SDK.
That keeps them testable (tests inject a fake provider, so no API credits are
used) and makes DEMO mode explicit: in demo mode no provider is constructed at
all, so a paid API call is impossible rather than merely unlikely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.config.settings import Settings
from app.models.domain import TokenUsage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns unusable output."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    usage: TokenUsage


class LLMProvider(Protocol):
    """Minimal interface the agents need from a chat model."""

    model_name: str

    def generate(self, system: str, prompt: str) -> LLMResult:
        """Return free-form text."""
        ...

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        """Return an instance of ``schema`` parsed from the model output."""
        ...


def _usage_from_message(message: object) -> TokenUsage:
    meta = getattr(message, "usage_metadata", None) or {}
    return TokenUsage(
        input_tokens=int(meta.get("input_tokens", 0)),
        output_tokens=int(meta.get("output_tokens", 0)),
        llm_calls=1,
    )


class AnthropicProvider:
    """Claude via ``langchain-anthropic``. Only constructed in LIVE mode."""

    def __init__(self, settings: Settings) -> None:
        if settings.anthropic_api_key is None:  # defensive; Settings already validates
            raise LLMError("ANTHROPIC_API_KEY is not configured.")
        from langchain_anthropic import ChatAnthropic  # imported lazily: unused in demo mode

        self.model_name = settings.anthropic_model
        optional: dict[str, float] = {}
        if settings.llm_temperature is not None:
            optional["temperature"] = settings.llm_temperature
        self._llm = ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
            **optional,
        )
        logger.info("Live LLM provider initialised (model=%s)", self.model_name)

    def generate(self, system: str, prompt: str) -> LLMResult:
        try:
            message = self._llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        except Exception as exc:  # SDK raises many types; normalise them
            raise LLMError(f"Claude call failed: {type(exc).__name__}") from exc
        text = message.content if isinstance(message.content, str) else _join_blocks(message.content)
        return LLMResult(text=text, usage=_usage_from_message(message))

    def structured(self, system: str, prompt: str, schema: type[T]) -> tuple[T, TokenUsage]:
        # Native JSON-schema structured output (forced tool calling is not supported on all models).
        runnable = self._llm.with_structured_output(schema, method="json_schema", include_raw=True)
        try:
            output = runnable.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        except Exception as exc:
            raise LLMError(f"Claude structured call failed: {type(exc).__name__}") from exc
        parsed = output.get("parsed")
        usage = _usage_from_message(output.get("raw"))
        if parsed is None:
            raise LLMError(f"Claude returned unparseable output for {schema.__name__}.")
        return parsed, usage


def _join_blocks(blocks: list) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Return a live provider in LIVE mode, otherwise ``None`` (DEMO mode)."""
    if not settings.is_live:
        logger.info("DEMO mode: no LLM provider constructed; zero external LLM calls will be made.")
        return None
    return AnthropicProvider(settings)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) used for demo-mode accounting."""
    return max(1, len(text) // 4) if text else 0
