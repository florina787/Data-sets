"""Groq adapter (OpenAI-compatible chat completions API).

Reuses everything provider-neutral from GeminiClient — response cache, one bounded
schema repair, rate limiter, retries with jitter / Retry-After, circuit breaker,
token and cost accounting — and replaces only the HTTP call. Structured output uses
JSON mode with the Pydantic JSON Schema in the system message; the result is still
validated against the schema before anything uses it.
"""

from __future__ import annotations

import json
import time

import httpx
from pydantic import BaseModel

from app.config import Settings
from app.llm.gemini_client import GeminiClient
from app.llm.cache import ResponseCache
from app.llm.resilience import CircuitBreaker, RateLimiter
from app.llm.usage import Usage
from app.prompts.registry import PromptVersion


class GroqAPIError(Exception):
    """HTTP error with the status code and response, so the shared retry logic can classify it."""

    def __init__(self, code: int, message: str, response: httpx.Response | None = None):
        super().__init__(f"{code} {message}")
        self.code = code
        self.response = response


class GroqClient(GeminiClient):
    name = "groq"

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None, sleep=time.sleep):
        # Deliberately not calling GeminiClient.__init__: no Google SDK is created.
        self.settings = settings
        self.model = settings.groq_model
        self._http = http_client or httpx.Client(base_url=settings.groq_base_url, timeout=settings.gemini_timeout_seconds,
                                                 headers={"Authorization": f"Bearer {settings.groq_api_key}"})
        self._sleep = sleep
        self.limiter = RateLimiter(settings.gemini_requests_per_minute, settings.gemini_max_concurrency, sleep=sleep)
        self.breaker = CircuitBreaker(settings.gemini_circuit_threshold, settings.gemini_circuit_cooldown_seconds)
        self.cache = ResponseCache(settings.llm_cache_path)
        self.last_success: str | None = None
        self.provider = "groq"
        self.label = "Groq"
        self.costs = (settings.groq_input_cost_per_mtok, settings.groq_output_cost_per_mtok)

    def _invoke(self, prompt: PromptVersion, user: str, schema: type[BaseModel] | None, stream: bool) -> tuple[str, Usage]:
        """One chat-completions request; `stream` is ignored (responses are short and returned whole)."""
        mc = prompt.model_config
        system = prompt.system
        body: dict = {
            "model": self.model,
            "temperature": mc.get("temperature", self.settings.gemini_temperature),
            "max_completion_tokens": mc.get("max_output_tokens", self.settings.gemini_max_output_tokens),
        }
        if schema is not None:
            system += ("\n\nReturn only a JSON object that conforms to this JSON Schema (no prose, no code fences):\n"
                       + json.dumps(schema.model_json_schema(), separators=(",", ":")))
            body["response_format"] = {"type": "json_object"}
        body["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            resp = self._http.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Groq request timed out: {e}") from e
        except httpx.TransportError as e:
            raise ConnectionError(f"Groq connection failed: {e}") from e
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                detail = resp.text
            raise GroqAPIError(resp.status_code, str(detail)[:300], resp)
        data = resp.json()
        u = data.get("usage") or {}
        usage = Usage(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), int(u.get("total_tokens", 0)))
        return data["choices"][0]["message"].get("content") or "", usage
