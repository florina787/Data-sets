"""Qwen inference client (open-weight models only).

Ollama and llama.cpp's ``llama-server`` both expose an OpenAI-compatible
``/v1/chat/completions`` endpoint, so one client serves both runtimes. The model name is checked
at start-up: anything that is not a Qwen model is refused, so a misconfiguration can never route
user data to another model family or a hosted API.

A single in-process semaphore queues requests to the single model instance (CPU inference cannot
usefully run many generations in parallel); time spent waiting is recorded as ``queue_ms``.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import get_settings
from ..db import SessionLocal
from ..models import InferenceMetric

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class LLMUnavailable(RuntimeError):
    pass


def assert_qwen(model: str) -> None:
    if "qwen" not in model.lower():
        raise ValueError(f"LLM_MODEL must be a Qwen open-weight model, got '{model}'")


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    ttft_ms: int | None = None
    total_ms: int = 0
    queue_ms: int = 0
    model: str = ""
    provider: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_per_second(self) -> float | None:
        gen_ms = self.total_ms - (self.ttft_ms or 0)
        if self.completion_tokens and gen_ms > 0:
            return round(self.completion_tokens / (gen_ms / 1000), 2)
        return None

    def json(self) -> Any:
        return parse_json_block(self.text)


def parse_json_block(text: str) -> Any:
    text = THINK_RE.sub("", text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON found in model output")
    depth, end, opener = 0, -1, text[start]
    closer = "}" if opener == "{" else "]"
    in_str = esc = False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(text[start:end + 1])


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class QwenClient:
    def __init__(self) -> None:
        s = get_settings()
        self.provider = s.llm_provider
        self.model = s.llm_model
        self.base_url = s.llm_base_url.rstrip("/")
        self.timeout = s.llm_timeout_seconds
        self.max_tokens = s.llm_max_tokens
        self._sem = asyncio.Semaphore(max(1, s.llm_max_concurrency))
        self.queue_depth = 0
        if self.provider in ("ollama", "llamacpp"):
            assert_qwen(self.model)

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled"

    # ------------------------------------------------------------------ public API
    async def complete(self, messages: list[dict[str, str]], *, purpose: str, user_id: uuid.UUID | None = None,
                       max_tokens: int | None = None, temperature: float = 0.3, json_mode: bool = False) -> LLMResult:
        chunks: list[str] = []
        result = LLMResult(text="")
        async for piece in self._stream(messages, purpose=purpose, user_id=user_id, max_tokens=max_tokens,
                                        temperature=temperature, json_mode=json_mode, sink=result):
            chunks.append(piece)
        result.text = THINK_RE.sub("", "".join(chunks)).strip()
        return result

    async def stream(self, messages: list[dict[str, str]], *, purpose: str, user_id: uuid.UUID | None = None,
                     max_tokens: int | None = None, temperature: float = 0.4, sink: LLMResult | None = None
                     ) -> AsyncIterator[str]:
        in_think = False
        buf = ""
        async for piece in self._stream(messages, purpose=purpose, user_id=user_id, max_tokens=max_tokens,
                                        temperature=temperature, json_mode=False, sink=sink or LLMResult(text="")):
            buf += piece
            # Hide Qwen3 <think> blocks from the user-facing stream.
            while True:
                if in_think:
                    idx = buf.find("</think>")
                    if idx < 0:
                        buf = buf[-10:]
                        break
                    buf, in_think = buf[idx + len("</think>"):].lstrip(), False
                else:
                    idx = buf.find("<think>")
                    if idx < 0:
                        safe = len(buf) - 7 if len(buf) > 7 else 0
                        if safe:
                            yield buf[:safe]
                            buf = buf[safe:]
                        break
                    if idx:
                        yield buf[:idx]
                    buf, in_think = buf[idx + len("<think>"):], True
        if buf and not in_think:
            yield buf

    async def health(self) -> dict[str, Any]:
        if self.provider in ("scripted", "disabled"):
            return {"provider": self.provider, "model": self.model, "ok": self.provider == "scripted"}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/v1/models")
                r.raise_for_status()
                models = [m.get("id") for m in r.json().get("data", [])]
            return {"provider": self.provider, "model": self.model, "ok": True, "available_models": models,
                    "model_loaded": any(self.model.split(":")[0] in (m or "") for m in models)}
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.provider, "model": self.model, "ok": False, "error": str(exc)[:200]}

    # ------------------------------------------------------------------ internals
    async def _stream(self, messages, *, purpose, user_id, max_tokens, temperature, json_mode, sink: LLMResult
                      ) -> AsyncIterator[str]:
        if self.provider == "disabled":
            raise LLMUnavailable("LLM disabled")
        t_queue = time.perf_counter()
        self.queue_depth += 1
        try:
            async with self._sem:
                self.queue_depth -= 1
                queued = int((time.perf_counter() - t_queue) * 1000)
                t0 = time.perf_counter()
                sink.queue_ms, sink.model, sink.provider = queued, self.model, self.provider
                error: str | None = None
                try:
                    if self.provider == "scripted":
                        gen = self._scripted(messages, json_mode)
                    else:
                        gen = self._openai_compatible(messages, max_tokens or self.max_tokens, temperature, json_mode,
                                                      sink)
                    async for piece in gen:
                        if sink.ttft_ms is None:
                            sink.ttft_ms = int((time.perf_counter() - t0) * 1000)
                        yield piece
                except LLMUnavailable as exc:
                    error = str(exc)
                    raise
                except (httpx.HTTPError, OSError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    raise LLMUnavailable(error) from exc
                finally:
                    sink.total_ms = int((time.perf_counter() - t0) * 1000)
                    if not sink.prompt_tokens:
                        sink.prompt_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
                    self._record(sink, purpose, user_id, error)
        finally:
            self.queue_depth = max(0, self.queue_depth)

    def build_body(self, messages, max_tokens, temperature, json_mode) -> dict[str, Any]:
        msgs = [dict(m) for m in messages]
        # Qwen3 soft switch: skip the long reasoning trace for latency on CPU.
        if msgs and msgs[0]["role"] == "system" and "/no_think" not in msgs[0]["content"]:
            msgs[0]["content"] += "\n/no_think"
        body: dict[str, Any] = {"model": self.model, "messages": msgs, "stream": True, "max_tokens": max_tokens,
                                "temperature": temperature, "stream_options": {"include_usage": True}}
        # Disable Qwen3's reasoning trace: on CPU it costs most of the token budget, and Ollama returns it
        # in a separate "reasoning" field, leaving "content" empty when max_tokens is reached.
        if self.provider == "ollama":
            body["reasoning_effort"] = "none"
        else:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def _openai_compatible(self, messages, max_tokens, temperature, json_mode, sink: LLMResult
                                 ) -> AsyncIterator[str]:
        body = self.build_body(messages, max_tokens, temperature, json_mode)
        timeout = httpx.Timeout(self.timeout, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=body) as resp:
                if resp.status_code >= 400:
                    detail = (await resp.aread()).decode(errors="replace")[:300]
                    raise LLMUnavailable(f"inference server returned {resp.status_code}: {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("usage"):
                        sink.prompt_tokens = obj["usage"].get("prompt_tokens", 0) or sink.prompt_tokens
                        sink.completion_tokens = obj["usage"].get("completion_tokens", 0) or sink.completion_tokens
                    for choice in obj.get("choices") or []:
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            if not obj.get("usage"):
                                sink.extra["chunks"] = sink.extra.get("chunks", 0) + 1
                            yield delta
        if not sink.completion_tokens:
            sink.completion_tokens = sink.extra.get("chunks", 0)

    async def _scripted(self, messages, json_mode) -> AsyncIterator[str]:
        """Deterministic stand-in used by tests (LLM_PROVIDER=scripted)."""
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        text = "{}" if json_mode else f"[scripted-qwen] {last[:160]}"
        for i in range(0, len(text), 16):
            await asyncio.sleep(0)
            yield text[i:i + 16]

    def _record(self, r: LLMResult, purpose: str, user_id, error: str | None) -> None:
        if r.provider == "scripted" and not r.completion_tokens:
            r.completion_tokens = sum(1 for _ in range(r.extra.get("chunks", 2)))
        try:
            with SessionLocal() as db:
                db.add(InferenceMetric(user_id=user_id, provider=r.provider, model=r.model, purpose=purpose[:60],
                                       prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens,
                                       ttft_ms=r.ttft_ms, total_ms=r.total_ms, tokens_per_second=r.tokens_per_second,
                                       queue_ms=r.queue_ms, ok=error is None, error=(error or None) and error[:500]))
                db.commit()
        except Exception:  # noqa: BLE001 - metrics must never break a request
            pass


_client: QwenClient | None = None


def get_llm() -> QwenClient:
    global _client
    if _client is None:
        _client = QwenClient()
    return _client


def reset_llm() -> None:
    global _client
    _client = None
