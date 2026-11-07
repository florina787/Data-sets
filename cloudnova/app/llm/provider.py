"""Local LLM adapter. Extends FloPilot's `LLMProvider.complete()` protocol (backend/app/llm/providers.py)
with a Qwen provider over the OpenAI-compatible chat API that Ollama, llama.cpp server, vLLM and LM Studio
all expose. No API key, no cloud. No silent fallback (ConvoLens rule): if the model is down, callers get
`llm_unavailable` and must not invent an answer.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..config import get_settings
from ..errors import AppError


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    notes: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, system: str, messages: list[dict], max_tokens: int | None = None,
                 temperature: float = 0.0) -> LLMResponse: ...


class QwenProvider:
    name = "qwen"

    def __init__(self, client: httpx.Client | None = None) -> None:
        s = get_settings()
        self.model, self.base_url, self.max_tokens = s.llm_model, s.llm_base_url, s.llm_max_tokens
        self.client = client or httpx.Client(timeout=s.llm_timeout_s, trust_env=False)  # local endpoint: bypass proxies

    def complete(self, system: str, messages: list[dict], max_tokens: int | None = None,
                 temperature: float = 0.0) -> LLMResponse:
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, *messages],
                "max_tokens": max_tokens or self.max_tokens, "temperature": temperature, "stream": False}
        t0 = time.perf_counter()
        try:
            r = self.client.post(f"{self.base_url}/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise AppError("llm_timeout", "The local Qwen model did not answer in time.", 504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AppError("llm_unavailable", f"The local Qwen model is not reachable at {self.base_url}. "
                           "Start it (see README › Local Qwen) or ask a data question, which does not need the model.",
                           503, retryable=True) from exc
        if r.status_code != 200:
            raise AppError("llm_error", f"The local Qwen server returned HTTP {r.status_code}.", 502)
        data = r.json()
        usage = data.get("usage") or {}
        return LLMResponse(text=(data["choices"][0]["message"].get("content") or "").strip(),
                           model=data.get("model", self.model), input_tokens=usage.get("prompt_tokens", 0),
                           output_tokens=usage.get("completion_tokens", 0),
                           latency_ms=round((time.perf_counter() - t0) * 1000, 1))

    def ping(self) -> dict:
        try:
            r = self.client.get(f"{self.base_url}/models", timeout=3.0)
            ids = [m.get("id") for m in r.json().get("data", [])] if r.status_code == 200 else []
            return {"reachable": r.status_code == 200, "models": ids}
        except (httpx.HTTPError, ValueError):
            return {"reachable": False, "models": []}


_override: LLMProvider | None = None


def set_provider_override(p: LLMProvider | None) -> None:
    """Test hook (pattern from FloPilot/ConvoLens): inject a fake or failing provider."""
    global _override
    _override = p


def get_provider() -> LLMProvider | None:
    if _override is not None:
        return _override
    return QwenProvider() if get_settings().llm_provider == "qwen" else None


def provider_status() -> dict:
    s = get_settings()
    p = get_provider()
    if p is None:
        return {"provider": "none", "model": None, "reachable": False, "mode": "deterministic-only",
                "label": "No LLM configured — analytics run on the deterministic semantic planner"}
    ping = p.ping() if hasattr(p, "ping") else {"reachable": True, "models": [p.model]}
    return {"provider": p.name, "model": p.model, "base_url": s.llm_base_url if p.name == "qwen" else None,
            "reachable": ping["reachable"], "served_models": ping["models"], "mode": "qwen+semantic" if ping["reachable"] else "deterministic-only",
            "label": f"Local {p.model}" + ("" if ping["reachable"] else " (offline)")}
