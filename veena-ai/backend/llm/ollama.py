"""Async client for a local Ollama server (the only inference backend)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx


class LLMUnavailable(RuntimeError):
    """Ollama is not running, or the requested model is not installed."""


@dataclass
class ModelInfo:
    name: str
    size_bytes: int
    family: str | None
    parameter_size: str | None
    quantization: str | None
    capabilities: list[str] = field(default_factory=list)

    @property
    def vision(self) -> bool:
        return "vision" in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
            "capabilities": self.capabilities,
            "vision": self.vision,
        }


@dataclass
class GenerationStats:
    model: str
    first_token_ms: float | None = None
    total_ms: float = 0.0
    eval_tokens: int = 0
    prompt_tokens: int = 0
    tokens_per_second: float | None = None
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=3.0),
            # Inference is local; never route it through a system HTTP proxy.
            trust_env=False,
        )
        self._caps_cache: dict[str, list[str]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def version(self) -> str | None:
        try:
            r = await self._client.get("/api/version", timeout=3.0)
            r.raise_for_status()
            return r.json().get("version")
        except httpx.HTTPError:
            return None

    async def list_models(self) -> list[ModelInfo]:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}") from e
        out = []
        for m in r.json().get("models", []):
            d = m.get("details", {}) or {}
            out.append(
                ModelInfo(
                    name=m["name"],
                    size_bytes=m.get("size", 0),
                    family=d.get("family"),
                    parameter_size=d.get("parameter_size"),
                    quantization=d.get("quantization_level"),
                    capabilities=await self.capabilities(m["name"]),
                )
            )
        return out

    async def capabilities(self, model: str) -> list[str]:
        if model in self._caps_cache:
            return self._caps_cache[model]
        try:
            r = await self._client.post("/api/show", json={"model": model}, timeout=10.0)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError:
            return []
        caps = list(data.get("capabilities") or [])
        if not caps:
            # Older Ollama builds have no capabilities field; a projector in
            # the model info is the reliable sign of a vision model there.
            caps = ["completion"]
            if any("vision" in k or "projector" in k for k in (data.get("model_info") or {})) or data.get("projector_info"):
                caps.append("vision")
        self._caps_cache[model] = caps
        return caps

    async def pull(self, model: str) -> AsyncIterator[dict[str, Any]]:
        async with self._client.stream("POST", "/api/pull", json={"model": model, "stream": True}, timeout=None) as r:
            if r.status_code != 200:
                raise LLMUnavailable(f"pull failed: HTTP {r.status_code}")
            async for line in r.aiter_lines():
                if line.strip():
                    yield json.loads(line)
        self._caps_cache.pop(model, None)

    async def warm(self, model: str) -> None:
        """Load a model into memory so the first real request is not a cold start."""
        try:
            await self._client.post("/api/generate", json={"model": model, "prompt": "", "keep_alive": "30m"}, timeout=120.0)
        except httpx.HTTPError:
            pass

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        options: dict[str, Any] | None = None,
        fmt: str | None = None,
        stats: GenerationStats | None = None,
    ) -> AsyncIterator[str]:
        """Yield content deltas. Closing the iterator aborts the HTTP stream,
        which makes Ollama stop generating (cancellable inference)."""
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True, "keep_alive": "30m"}
        if options:
            payload["options"] = options
        if fmt:
            payload["format"] = fmt
        stats = stats if stats is not None else GenerationStats(model=model)
        t0 = time.perf_counter()
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as r:
                if r.status_code == 404:
                    raise LLMUnavailable(f"model {model!r} is not installed in Ollama")
                if r.status_code != 200:
                    body = (await r.aread()).decode(errors="replace")[:300]
                    raise LLMUnavailable(f"Ollama error HTTP {r.status_code}: {body}")
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise LLMUnavailable(chunk["error"])
                    delta = (chunk.get("message") or {}).get("content", "")
                    if delta:
                        if stats.first_token_ms is None:
                            stats.first_token_ms = (time.perf_counter() - t0) * 1000
                        yield delta
                    if chunk.get("done"):
                        stats.eval_tokens = chunk.get("eval_count", 0)
                        stats.prompt_tokens = chunk.get("prompt_eval_count", 0)
                        ns = chunk.get("eval_duration") or 0
                        if ns and stats.eval_tokens:
                            stats.tokens_per_second = stats.eval_tokens / (ns / 1e9)
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}. Start Ollama and retry.") from e
        except GeneratorExit:
            stats.cancelled = True
            raise
        finally:
            stats.total_ms = (time.perf_counter() - t0) * 1000

    async def chat(self, model: str, messages: list[dict[str, Any]], **kw: Any) -> str:
        parts = [d async for d in self.chat_stream(model, messages, **kw)]
        return "".join(parts)
