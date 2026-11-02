"""Client for the local model server that is already running on this machine.

FoodCare does not download, load or start a model. It talks to one existing
OpenAI-compatible server (Ollama, LM Studio, llama.cpp ``llama-server`` or MLX;
GitHub Copilot's "local model" option uses the same servers), configured with
``FOODCARE_LLM_BASE_URL`` (including ``/v1``) and ``FOODCARE_LLM_MODEL``.

Resource protection, all in-process and dependency-free:

* one shared client per configuration, so one model instance serves everything;
* bounded concurrency (default 1) and a bounded wait queue: when full, callers
  get an immediate "busy" error instead of piling up;
* per-request timeout, and cancellation that closes the stream mid-generation;
* a prompt-size cap; the adapter never sets the server's context size;
* a small LRU cache of identical prompts;
* the status probe lists models (``GET /models``), which does not load weights,
  and runs only when asked, never in the background.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from collections import OrderedDict, deque
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.errors import LiveModeUnavailable, LocalModelBusy, PlatformError, RequestCancelled

T = TypeVar("T", bound=BaseModel)

THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def extract_json(text: str) -> dict:
    """Parse a JSON object from model text (tolerates reasoning blocks and code fences)."""
    text = FENCE.sub("", THINK.sub("", text).strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise PlatformError("Model reply contained no JSON object")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise PlatformError("Model reply was not valid JSON", error=str(exc)[:200]) from exc


class LocalLLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.live_available:
            raise LiveModeUnavailable(
                "LIVE mode needs FOODCARE_LLM_BASE_URL and FOODCARE_LLM_MODEL pointing at a local model server "
                "that is already running (for example Ollama at http://127.0.0.1:11434/v1). No scripted output is "
                "substituted; use DEMO mode instead.")
        self.settings = settings
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
        self.client = httpx.Client(base_url=self.base_url, headers=headers,
                                   timeout=httpx.Timeout(settings.llm_timeout_s, connect=5.0))
        self._slots = threading.BoundedSemaphore(max(1, settings.llm_concurrency))
        self._lock = threading.Lock()
        self._waiting = 0
        self._in_flight = 0
        self._cancel: dict[str, threading.Event] = {}
        self._cache: OrderedDict[str, tuple[dict, dict]] = OrderedDict()
        self._latencies: deque[float] = deque(maxlen=50)
        self._probe: tuple[float, dict] | None = None
        self.stats = {"calls": 0, "ok": 0, "errors": 0, "cache_hits": 0, "busy": 0, "timeouts": 0,
                      "cancelled": 0, "prompt_tokens": 0, "completion_tokens": 0}

    # --- public ----------------------------------------------------------------------

    def structured(self, system: str, prompt: str, schema: type[T],
                   request_id: str | None = None) -> tuple[T, dict]:
        if len(prompt) > self.settings.llm_max_prompt_chars:
            raise PlatformError("Prompt exceeds the configured context limit",
                                chars=len(prompt), limit=self.settings.llm_max_prompt_chars)
        key = hashlib.sha256(f"{self.model}\0{schema.__name__}\0{system}\0{prompt}".encode()).hexdigest()
        with self._lock:
            self.stats["calls"] += 1
            if key in self._cache:
                self._cache.move_to_end(key)
                self.stats["cache_hits"] += 1
                data, usage = self._cache[key]
                return schema.model_validate(data), {**usage, "cached": True, "latency_ms": 0.0}
        request_id = request_id or uuid.uuid4().hex
        cancel = self._register(request_id)
        try:
            self._acquire(cancel)
            try:
                data, usage = self._generate(system, prompt, schema, cancel)
            finally:
                with self._lock:
                    self._in_flight -= 1
                self._slots.release()
        except PlatformError:
            with self._lock:
                self.stats["errors"] += 1
            raise
        finally:
            with self._lock:
                self._cancel.pop(request_id, None)
        try:
            parsed = schema.model_validate(data)
        except ValidationError as exc:
            with self._lock:
                self.stats["errors"] += 1
            raise PlatformError("Model output failed schema validation", error=str(exc)[:300]) from exc
        with self._lock:
            self.stats["ok"] += 1
            self._latencies.append(usage["latency_ms"])
            if self.settings.llm_cache_entries > 0:
                self._cache[key] = (parsed.model_dump(), usage)
                while len(self._cache) > self.settings.llm_cache_entries:
                    self._cache.popitem(last=False)
        return parsed, {**usage, "cached": False, "request_id": request_id}

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(request_id)
        if event:
            event.set()
        return event is not None

    def status(self, probe: bool = True) -> dict:
        with self._lock:
            lat = sorted(self._latencies)
            info = {"configured": True, "base_url": self.base_url, "model": self.model,
                    "concurrency": self.settings.llm_concurrency, "queue_limit": self.settings.llm_queue_size,
                    "queue_depth": self._waiting, "in_flight": self._in_flight, "stats": dict(self.stats),
                    "latency_ms": {"last": self._latencies[-1] if lat else None,
                                   "p50": lat[len(lat) // 2] if lat else None,
                                   "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
                                   "samples": len(lat)},
                    "cache_entries": len(self._cache)}
        if probe:
            info.update(self._probe_server())
        return info

    # --- internals -------------------------------------------------------------------

    def _register(self, request_id: str) -> threading.Event:
        event = threading.Event()
        with self._lock:
            self._cancel[request_id] = event
        return event

    def _acquire(self, cancel: threading.Event) -> None:
        if self._slots.acquire(blocking=False):  # a free slot: no queueing
            with self._lock:
                self._in_flight += 1
            return
        with self._lock:
            if self._waiting >= self.settings.llm_queue_size:
                self.stats["busy"] += 1
                raise LocalModelBusy("The local model is busy (queue full). Try again shortly.",
                                     queue_limit=self.settings.llm_queue_size)
            self._waiting += 1
        deadline = time.monotonic() + self.settings.llm_queue_wait_s
        try:
            while True:
                if cancel.is_set():
                    with self._lock:
                        self.stats["cancelled"] += 1
                    raise RequestCancelled("Request cancelled before the model started")
                if self._slots.acquire(timeout=0.1):
                    break
                if time.monotonic() >= deadline:
                    with self._lock:
                        self.stats["busy"] += 1
                    raise LocalModelBusy("The local model is busy (waited too long in the queue).")
        finally:
            with self._lock:
                self._waiting -= 1
        with self._lock:
            self._in_flight += 1

    def _body(self, system: str, prompt: str, schema: type[BaseModel]) -> dict:
        body: dict = {"model": self.model, "stream": True, "temperature": 0.1,
                      "max_tokens": self.settings.llm_max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        fmt = self.settings.llm_response_format
        if fmt == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": schema.__name__, "schema": schema.model_json_schema(), "strict": True}}
        elif fmt == "json_object":
            body["response_format"] = {"type": "json_object"}
        return body

    def _generate(self, system: str, prompt: str, schema: type[BaseModel],
                  cancel: threading.Event) -> tuple[dict, dict]:
        started = time.perf_counter()
        deadline = time.monotonic() + self.settings.llm_timeout_s
        parts: list[str] = []
        finish, usage = None, {}
        try:
            with self.client.stream("POST", "/chat/completions", json=self._body(system, prompt, schema)) as resp:
                if resp.status_code >= 400:
                    detail = resp.read().decode("utf-8", "replace")[:300]
                    raise LiveModeUnavailable(f"Local model server returned HTTP {resp.status_code}", detail=detail)
                for line in resp.iter_lines():
                    if cancel.is_set():
                        with self._lock:
                            self.stats["cancelled"] += 1
                        raise RequestCancelled("Request cancelled during generation")
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("generation exceeded the timeout")
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    usage = chunk.get("usage") or usage
                    for choice in chunk.get("choices", []):
                        parts.append((choice.get("delta") or {}).get("content") or "")
                        finish = choice.get("finish_reason") or finish
        except httpx.TimeoutException as exc:
            with self._lock:
                self.stats["timeouts"] += 1
            raise LiveModeUnavailable(f"The local model did not finish within {self.settings.llm_timeout_s:g}s") \
                from exc
        except httpx.TransportError as exc:
            raise LiveModeUnavailable(f"Could not reach the local model server at {self.base_url}. Start it "
                                      "(e.g. Ollama or LM Studio) and check FOODCARE_LLM_BASE_URL.") from exc
        if finish == "length":
            raise PlatformError("Model output was truncated (max_tokens); not used")
        latency = round((time.perf_counter() - started) * 1000, 1)
        with self._lock:
            self.stats["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            self.stats["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        return extract_json("".join(parts)), {
            "model": self.model, "latency_ms": latency,
            "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")}

    def _probe_server(self) -> dict:
        now = time.monotonic()
        if self._probe and now - self._probe[0] < 30:
            return self._probe[1]
        try:
            resp = self.client.get("/models", timeout=3.0)
            resp.raise_for_status()
            ids = [m.get("id") for m in resp.json().get("data", [])]
            result = {"reachable": True, "model_listed": self.model in ids, "models": ids[:20], "error": None}
        except (httpx.HTTPError, ValueError) as exc:
            result = {"reachable": False, "model_listed": False, "models": [], "error": str(exc)[:200]}
        self._probe = (now, result)
        return result


_client: LocalLLM | None = None
_client_lock = threading.Lock()


def get_llm() -> LocalLLM:
    """The single shared client for the current configuration."""
    global _client
    settings = get_settings()
    with _client_lock:
        if _client is None or _client.settings is not settings:
            if _client is not None:
                _client.client.close()
            _client = LocalLLM(settings)
        return _client


def status() -> dict:
    settings = get_settings()
    if not settings.live_available:
        return {"configured": False, "reason": "FOODCARE_LLM_BASE_URL and FOODCARE_LLM_MODEL are not both set",
                "reachable": False}
    return get_llm().status()


def cancel(request_id: str) -> bool:
    return _client.cancel(request_id) if _client else False
