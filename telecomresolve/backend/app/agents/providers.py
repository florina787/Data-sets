"""Generation provider abstraction.

DEMO   - deterministic rules and templates. No model is called. Responses are
         labelled DEMO and never presented as live model output.
LIVE   - real server-side model calls through the configured provider.
HYBRID - real generation; operational connectors remain simulated.

There is no silent fallback: if the live provider is unavailable the call
raises ProviderUnavailable and the workflow records an explicit, labelled
outcome. Refusals are surfaced, not rerouted to another model.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from ..config import get_settings

M = TypeVar("M", bound=BaseModel)


class ProviderUnavailable(Exception):
    def __init__(self, reason: str, code: str = "PROVIDER_UNAVAILABLE"):
        super().__init__(reason)
        self.code = code
        self.reason = reason


class BudgetExceeded(ProviderUnavailable):
    def __init__(self, reason: str):
        super().__init__(reason, code="BUDGET_EXCEEDED")


@dataclass
class Usage:
    provider: str
    model: str
    available: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    pricing_configured_on: str | None = None
    calls: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider, "model": self.model, "usage_available": self.available,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "pricing_configured_on": self.pricing_configured_on, "calls": self.calls,
            "notes": self.notes,
        }


class CircuitBreaker:
    def __init__(self, threshold: int, reset_seconds: int):
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            if self.opened_at is None:
                return
            if time.monotonic() - self.opened_at >= self.reset_seconds:
                self.opened_at = None  # half-open: allow one attempt
                self.failures = 0
                return
            raise ProviderUnavailable("Live provider circuit breaker is open", "CIRCUIT_OPEN")

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


class Provider:
    mode = "DEMO"
    name = "deterministic-demo"
    model = "rules-v1"

    @property
    def is_live(self) -> bool:
        return self.mode in {"LIVE", "HYBRID"}

    def generate(self, *, system: str, user: str, schema: type[M], budget_used: int) -> tuple[M, Usage]:
        raise ProviderUnavailable("DEMO provider does not generate text; deterministic rules are used",
                                  "NOT_LIVE")

    def describe(self) -> dict:
        return {"generation_mode": self.mode, "provider": self.name, "model": self.model,
                "live_calls": self.is_live}


class DemoProvider(Provider):
    pass


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, mode: str):
        s = get_settings()
        self.mode = mode
        self.model = s.llm_model
        self._settings = s
        self._sem = threading.BoundedSemaphore(s.llm_max_concurrency)
        self._breaker = CircuitBreaker(s.llm_circuit_breaker_failures,
                                       s.llm_circuit_breaker_reset_seconds)
        self._client = None

    def _client_or_raise(self):
        if not self._settings.llm_api_key:
            raise ProviderUnavailable("LIVE generation selected but LLM_API_KEY is not configured",
                                      "NOT_CONFIGURED")
        if self._client is None:
            import anthropic

            # The SDK retries connection errors, 408/409/429 and 5xx with backoff;
            # 4xx validation errors are not retried.
            self._client = anthropic.Anthropic(api_key=self._settings.llm_api_key,
                                               timeout=self._settings.llm_timeout_seconds,
                                               max_retries=self._settings.llm_max_retries)
        return self._client

    def generate(self, *, system: str, user: str, schema: type[M], budget_used: int) -> tuple[M, Usage]:
        import anthropic

        s = self._settings
        if budget_used >= s.llm_case_token_budget:
            raise BudgetExceeded(f"Case token budget of {s.llm_case_token_budget} exhausted")
        self._breaker.check()
        client = self._client_or_raise()
        usage = Usage(provider=self.name, model=self.model,
                      pricing_configured_on=s.llm_pricing_configured_on)
        with self._sem:
            try:
                response = client.messages.parse(
                    model=self.model,
                    max_tokens=s.llm_max_output_tokens,
                    output_config={"effort": "low"},
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    output_format=schema,
                )
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
                self._breaker.failure()
                raise ProviderUnavailable(f"Provider rejected credentials: {type(exc).__name__}",
                                          "PROVIDER_AUTH") from exc
            except anthropic.BadRequestError as exc:
                raise ProviderUnavailable(f"Provider rejected request: {exc.message}",
                                          "PROVIDER_BAD_REQUEST") from exc
            except (anthropic.APIConnectionError, anthropic.RateLimitError,
                    anthropic.APIStatusError) as exc:
                self._breaker.failure()
                raise ProviderUnavailable(f"Provider unavailable: {type(exc).__name__}",
                                          "PROVIDER_UNAVAILABLE") from exc
        self._breaker.success()
        usage.calls = 1
        if getattr(response, "usage", None) is not None:
            usage.available = True
            usage.input_tokens = response.usage.input_tokens
            usage.output_tokens = response.usage.output_tokens
            if s.llm_price_input_per_mtok or s.llm_price_output_per_mtok:
                usage.estimated_cost_usd = round(
                    usage.input_tokens / 1e6 * s.llm_price_input_per_mtok
                    + usage.output_tokens / 1e6 * s.llm_price_output_per_mtok, 6)
            else:
                usage.notes.append("pricing not configured; cost unavailable")
        if response.stop_reason == "refusal":
            raise ProviderUnavailable("Model declined the request (refusal)", "PROVIDER_REFUSAL")
        if response.stop_reason == "max_tokens":
            raise ProviderUnavailable("Output truncated at max_tokens", "OUTPUT_TRUNCATED")
        parsed = response.parsed_output
        if parsed is None:
            raise ProviderUnavailable("Provider returned no parseable output", "INVALID_OUTPUT")
        return parsed, usage


_provider: Provider | None = None


def get_provider() -> Provider:
    global _provider
    if _provider is None:
        mode = get_settings().generation_mode
        _provider = DemoProvider() if mode == "DEMO" else AnthropicProvider(mode)
    return _provider


def set_provider(provider: Provider | None) -> None:
    """Test hook."""
    global _provider
    _provider = provider
