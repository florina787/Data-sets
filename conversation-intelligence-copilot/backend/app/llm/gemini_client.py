"""Gemini adapter (google-genai SDK) behind a small provider interface.

Every call is bounded: rate-limited, timed out, retried with jittered backoff
only on retryable errors, short-circuited when the circuit breaker is open,
cached when deterministic, and recorded in telemetry with token usage.
Callers must handle `LLMUnavailable` by falling back to deterministic behaviour.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.llm.cache import ResponseCache, cache_key
from app.llm.budget import DeadlineExceeded
from app.llm.resilience import RETRYABLE_CODES, CircuitBreaker, RateLimiter, backoff_delay, retry_after_seconds
from app.llm.usage import Usage, aggregate_stream_usage, estimate_cost, usage_from_metadata
from app.observability.store import get_telemetry
from app.prompts.registry import PromptVersion

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
PERMANENT_HINTS = ("API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED", "PERMISSION_DENIED", "UNAUTHENTICATED", "not found for API version")


class LLMUnavailable(RuntimeError):
    """The model could not produce a valid answer; use the deterministic path."""


@dataclass
class LLMResult:
    text: str
    parsed: BaseModel | None
    model: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    retries: int = 0
    cache_hit: bool = False
    repaired: bool = False


class LLMClient(Protocol):
    name: str
    model: str

    def available(self) -> bool: ...
    def status(self) -> dict: ...
    def generate_json(self, prompt: PromptVersion, user: str, schema: type[T], request_id: str | None = None, purpose: str = "") -> LLMResult: ...
    def generate_text(self, prompt: PromptVersion, user: str, request_id: str | None = None, purpose: str = "") -> LLMResult: ...


class DisabledLLM:
    """Used when no key is configured or the model is switched off."""

    name = "disabled"

    def __init__(self, reason: str, model: str = "none"):
        self.reason = reason
        self.model = model

    def available(self) -> bool:
        return False

    def status(self) -> dict:
        return {"provider": "gemini", "mode": "deterministic", "available": False, "model": self.model, "reason": self.reason, "circuit": "n/a"}

    def generate_json(self, *a, **k) -> LLMResult:
        raise LLMUnavailable(self.reason)

    def generate_text(self, *a, **k) -> LLMResult:
        raise LLMUnavailable(self.reason)


class GeminiClient:
    name = "gemini"

    def __init__(self, settings: Settings, sdk_client=None, sleep=time.sleep):
        self.settings = settings
        self.model = settings.gemini_model
        if sdk_client is None:
            from google import genai
            from google.genai import types

            sdk_client = genai.Client(api_key=settings.gemini_api_key, vertexai=settings.gemini_use_vertex or None,
                                      http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_seconds * 1000)))
        self._client = sdk_client
        self._sleep = sleep
        self.limiter = RateLimiter(settings.gemini_requests_per_minute, settings.gemini_max_concurrency, sleep=sleep)
        self.breaker = CircuitBreaker(settings.gemini_circuit_threshold, settings.gemini_circuit_cooldown_seconds)
        self.cache = ResponseCache(settings.llm_cache_path)
        self.last_success: str | None = None
        self.provider = "vertex-ai" if settings.gemini_use_vertex else "gemini"
        self.label = "Gemini"
        self.costs = (settings.gemini_input_cost_per_mtok, settings.gemini_output_cost_per_mtok)

    # -- status -----------------------------------------------------------
    def available(self) -> bool:
        return self.breaker.allow()

    def status(self) -> dict:
        state = self.breaker.state
        return {
            "provider": self.provider, "model": self.model, "available": state != "open",
            "mode": "llm" if state != "open" else "deterministic", "circuit": state,
            "reason": self.breaker.last_error, "last_success": self.last_success, "rpm_limit": self.settings.gemini_requests_per_minute,
        }

    # -- core call ----------------------------------------------------------
    def _config(self, prompt: PromptVersion, schema: type[BaseModel] | None):
        from google.genai import types

        mc = prompt.model_config
        kwargs = dict(
            system_instruction=prompt.system,
            temperature=mc.get("temperature", self.settings.gemini_temperature),
            max_output_tokens=mc.get("max_output_tokens", self.settings.gemini_max_output_tokens),
        )
        if schema is not None:
            kwargs.update(response_mime_type="application/json", response_schema=schema)
        if "thinking_budget" in mc:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=mc["thinking_budget"])
        return types.GenerateContentConfig(**kwargs)

    def _invoke(self, prompt: PromptVersion, user: str, schema: type[BaseModel] | None, stream: bool) -> tuple[str, Usage]:
        """One provider request (no retries). Subclasses for other providers override only this."""
        config = self._config(prompt, schema)
        if stream:
            chunks = list(self._client.models.generate_content_stream(model=self.model, contents=user, config=config))
            return "".join(c.text or "" for c in chunks), aggregate_stream_usage([c.usage_metadata for c in chunks])
        resp = self._client.models.generate_content(model=self.model, contents=user, config=config)
        return resp.text or "", usage_from_metadata(resp.usage_metadata)

    def _call(self, prompt: PromptVersion, user: str, schema: type[BaseModel] | None, stream: bool = False) -> tuple[str, Usage, int]:
        if not self.breaker.allow():
            raise LLMUnavailable(f"{self.label} circuit open: {self.breaker.last_error}")
        retries = 0
        max_retries = self.settings.gemini_max_retries
        while True:
            self.limiter.acquire(timeout=self.settings.gemini_timeout_seconds)
            try:
                text, usage = self._invoke(prompt, user, schema, stream)
                self.breaker.success()
                self.last_success = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return text, usage, retries
            except DeadlineExceeded as e:  # the caller's time budget, not a provider fault: no retry, circuit untouched
                raise LLMUnavailable(f"{self.label}: {e}") from e
            except Exception as e:  # noqa: BLE001 - classified below
                code = getattr(e, "code", None)
                msg = f"{type(e).__name__} {code or ''}: {str(e)[:300]}"
                permanent = any(h in str(e) for h in PERMANENT_HINTS) or code in (400, 401, 403, 404)
                retryable = (code in RETRYABLE_CODES or isinstance(e, (TimeoutError, ConnectionError))
                             or "timed out" in str(e).lower()) and not permanent
                if not retryable or retries >= max_retries:
                    self.breaker.failure(msg, permanent=permanent)
                    e.retries = retries  # type: ignore[attr-defined]
                    e.rate_limited = code == 429  # type: ignore[attr-defined]
                    raise
                delay = retry_after_seconds(e) or backoff_delay(retries)
                retries += 1
                log.warning("%s retry %s after %.1fs: %s", self.label, retries, delay, msg)
                self._sleep(min(delay, self.settings.gemini_timeout_seconds))
            finally:
                self.limiter.release()

    def _record(self, prompt: PromptVersion, request_id, purpose, usage: Usage, latency, retries, cache_hit, status, error=None, rate_limited=False):
        get_telemetry().record_llm_call(
            request_id=request_id, purpose=purpose, prompt_id=prompt.id, prompt_version=prompt.version, model=self.model,
            input_tokens=usage.input_tokens if usage.reported else None, output_tokens=usage.output_tokens if usage.reported else None,
            total_tokens=usage.total_tokens if usage.reported else None, latency_ms=round(latency, 1),
            retries=retries, cache_hit=cache_hit, status=status, error=error, rate_limited=rate_limited,
            estimated_cost_usd=estimate_cost(usage, *self.costs),
        )

    def generate_json(self, prompt: PromptVersion, user: str, schema: type[T], request_id: str | None = None, purpose: str = "") -> LLMResult:
        key = cache_key(self.model, prompt.id, prompt.version, prompt.system, user, schema.__name__, prompt.model_config)
        cached = self.cache.get(key)
        if cached is not None:
            try:
                parsed = schema.model_validate_json(cached)
                self._record(prompt, request_id, purpose, Usage(), 0.0, 0, True, "ok")
                return LLMResult(cached, parsed, self.model, cache_hit=True)
            except ValidationError:
                pass  # stale or corrupt entry: fall through and regenerate
        start = time.perf_counter()
        total = Usage()
        retries = 0
        attempt_user = user
        for repair in range(2):  # one bounded repair attempt on schema failure
            try:
                text, usage, r = self._call(prompt, attempt_user, schema)
            except LLMUnavailable:
                raise
            except Exception as e:  # noqa: BLE001
                self._record(prompt, request_id, purpose, total.add(Usage(reported=False)), (time.perf_counter() - start) * 1000, getattr(e, "retries", retries),
                             False, "error", str(e)[:300], getattr(e, "rate_limited", False))
                raise LLMUnavailable(f"{self.label} call failed: {str(e)[:200]}") from e
            total = total.add(usage)
            retries += r
            try:
                parsed = schema.model_validate_json(text)
            except ValidationError as ve:
                attempt_user = (f"{user}\n\nYour previous output did not match the required JSON schema: "
                                f"{str(ve)[:500]}\nReturn only valid JSON for the schema.")
                continue
            latency = (time.perf_counter() - start) * 1000
            self.cache.put(key, self.model, f"{prompt.id}@{prompt.version}", text)
            self._record(prompt, request_id, purpose, total, latency, retries, False, "ok")
            return LLMResult(text, parsed, self.model, total, latency, retries, False, repaired=repair > 0)
        latency = (time.perf_counter() - start) * 1000
        self._record(prompt, request_id, purpose, total, latency, retries, False, "invalid_output", "schema validation failed after repair")
        raise LLMUnavailable(f"{self.label} output failed schema validation after one repair attempt")

    def generate_text(self, prompt: PromptVersion, user: str, request_id: str | None = None, purpose: str = "") -> LLMResult:
        start = time.perf_counter()
        try:
            text, usage, retries = self._call(prompt, user, None, stream=True)
        except LLMUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            self._record(prompt, request_id, purpose, Usage(reported=False), (time.perf_counter() - start) * 1000, getattr(e, "retries", 0),
                         False, "error", str(e)[:300], getattr(e, "rate_limited", False))
            raise LLMUnavailable(f"{self.label} call failed: {str(e)[:200]}") from e
        latency = (time.perf_counter() - start) * 1000
        self._record(prompt, request_id, purpose, usage, latency, retries, False, "ok")
        return LLMResult(text, None, self.model, usage, latency, retries)


_override: LLMClient | None = None


def set_llm(client: LLMClient | None) -> None:
    """Test hook / runtime override."""
    global _override
    _override = client
    get_llm.cache_clear()


@lru_cache
def get_llm() -> LLMClient:
    if _override is not None:
        return _override
    s = get_settings()
    if not s.llm_enabled:
        return DisabledLLM("Model calls disabled (LLM_ENABLED=false)", s.local_model_file.removesuffix(".gguf"))
    provider = s.resolved_llm_provider
    if provider is None:
        reason = "LLM_PROVIDER=none" if s.llm_provider == "none" else "No LLM configured (run `make llm-download` for the local model, or set GEMINI_API_KEY)"
        return DisabledLLM(reason, s.local_model_file.removesuffix(".gguf"))
    try:
        if provider == "local":
            import importlib.util

            from app.llm.local_client import LocalLlamaClient

            # Say exactly what is missing, so "deterministic mode" is never a mystery: the model file and the
            # llama.cpp binding are installed separately.
            if importlib.util.find_spec("llama_cpp") is None:
                return DisabledLLM("Local model selected, but llama-cpp-python is not installed. In backend/, run: "
                                   "uv sync --extra transformers --extra local-llm", s.local_model_file.removesuffix(".gguf"))

            return LocalLlamaClient(s)
        if not s.gemini_api_key:
            return DisabledLLM("GEMINI_API_KEY is not set", s.gemini_model)
        return GeminiClient(s)
    except Exception as e:  # noqa: BLE001
        return DisabledLLM(f"{provider} client could not be created: {e}", s.local_model_file.removesuffix(".gguf"))
