"""Local LLM Gateway: Flying_Florina -> Agent Orchestrator -> this gateway -> the user's existing Qwen model.

Every agent that wants language reasoning calls `gateway().generate(...)`. The gateway:
  * evaluates POL-008 (loopback model only, model calls enabled) before every call;
  * serves repeated prompts from a bounded cache (exact prompt + schema + budget);
  * runs one generation at a time by default (llama.cpp contexts are not thread-safe; CPU is the bottleneck);
  * trims the user context to fit the model's context window and caps output tokens;
  * enforces a wall-clock timeout (checked between streamed tokens);
  * validates structured output against a Pydantic schema and rejects invalid JSON;
  * records telemetry for every call (latency, time to first token, tokens, tokens/s, cache, errors, agent).

There is no external or paid fallback. If Qwen is unavailable the gateway raises `LLMUnavailable` and the caller
uses its deterministic, evidence-backed text, labelled as such. The model never authorizes anything: callers
treat its output as untrusted text that the Evidence Challenger and the policy engine must still pass.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.llm import telemetry
from app.llm.discovery import Discovery, discover, is_loopback


class LLMUnavailable(Exception):
    pass


class LLMError(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    data: dict[str, Any] | None
    model: str
    runtime: str
    agent: str
    task: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    first_token_ms: float | None
    tokens_per_s: float | None
    cached: bool = False
    truncated_context: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- runtimes

class Runtime:
    name = "base"

    def stream(self, messages: list[dict[str, str]], max_tokens: int, schema: dict | None, temperature: float) -> Iterator[tuple[str, dict | None]]:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def info(self) -> dict[str, Any]:
        return {}


class LlamaCppRuntime(Runtime):
    """In-process llama.cpp over the user's existing .gguf file. Loaded once per process."""

    name = "llama_cpp"
    _lock = threading.Lock()
    _instances: dict[str, Any] = {}

    def __init__(self, path: str, n_ctx: int, threads: int, gpu_layers: int):
        self.path, self.n_ctx, self.threads, self.gpu_layers = path, n_ctx, threads, gpu_layers
        self.load_ms: float | None = None
        self.gpu_layers_used: int | None = None

    @property
    def llama(self):
        key = f"{self.path}:{self.n_ctx}"
        with self._lock:
            if key not in self._instances:
                import llama_cpp
                from llama_cpp import Llama

                gpu = self.gpu_layers if llama_cpp.llama_supports_gpu_offload() else 0
                t0 = time.perf_counter()
                self._instances[key] = Llama(model_path=self.path, n_ctx=self.n_ctx, n_threads=self.threads, n_gpu_layers=gpu, verbose=False)
                self.load_ms = round((time.perf_counter() - t0) * 1000, 1)
                self.gpu_layers_used = gpu
                telemetry.note_load(self.load_ms)
            return self._instances[key]

    def loaded(self) -> bool:
        return f"{self.path}:{self.n_ctx}" in self._instances

    def count_tokens(self, text: str) -> int:
        try:
            return len(self.llama.tokenize(text.encode(), add_bos=False))
        except Exception:  # noqa: BLE001
            return super().count_tokens(text)

    def stream(self, messages, max_tokens, schema, temperature):
        kwargs: dict[str, Any] = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": True}
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object", "schema": schema}
        out = self.llama.create_chat_completion(**kwargs)
        if isinstance(out, dict):  # a backend that answers in one piece
            yield out["choices"][0]["message"].get("content") or "", out.get("usage")
            return
        for chunk in out:
            yield chunk["choices"][0].get("delta", {}).get("content") or "", chunk.get("usage")

    def info(self) -> dict[str, Any]:
        return {"n_ctx": self.n_ctx, "threads": self.threads, "gpu_layers_requested": self.gpu_layers,
                "gpu_layers_used": self.gpu_layers_used, "load_ms": self.load_ms, "loaded": self.loaded()}


class OllamaRuntime(Runtime):
    name = "ollama"

    def __init__(self, base_url: str, model: str, n_ctx: int, threads: int):
        self.base_url, self.model, self.n_ctx, self.threads = base_url.rstrip("/"), model, n_ctx, threads

    def stream(self, messages, max_tokens, schema, temperature):
        import httpx

        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True,
                                "options": {"num_predict": max_tokens, "temperature": temperature, "num_ctx": self.n_ctx}}
        if schema is not None:
            body["format"] = schema
        with httpx.stream("POST", f"{self.base_url}/api/chat", json=body, timeout=httpx.Timeout(10.0, read=120.0)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                msg = json.loads(line)
                usage = None
                if msg.get("done"):
                    usage = {"prompt_tokens": msg.get("prompt_eval_count"), "completion_tokens": msg.get("eval_count"),
                             "eval_duration_ns": msg.get("eval_duration"), "prompt_eval_duration_ns": msg.get("prompt_eval_duration")}
                yield (msg.get("message") or {}).get("content") or "", usage

    def info(self) -> dict[str, Any]:
        return {"base_url": self.base_url, "n_ctx": self.n_ctx}


class OpenAICompatRuntime(Runtime):
    name = "openai_compatible"

    def __init__(self, base_url: str, model: str):
        self.base_url, self.model = base_url.rstrip("/"), model

    def stream(self, messages, max_tokens, schema, temperature):
        import httpx

        body: dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                                "stream": True, "stream_options": {"include_usage": True}}
        if schema is not None:
            body["response_format"] = {"type": "json_object", "schema": schema}
        with httpx.stream("POST", f"{self.base_url}/v1/chat/completions", json=body, timeout=httpx.Timeout(10.0, read=120.0)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                choices = chunk.get("choices") or [{}]
                yield (choices[0].get("delta") or {}).get("content") or "", chunk.get("usage")

    def info(self) -> dict[str, Any]:
        return {"base_url": self.base_url}


# ---------------------------------------------------------------- gateway

JSON_OBJECT = re.compile(r"\{.*\}", re.S)


@dataclass
class _Cache:
    size: int = 256
    items: OrderedDict = field(default_factory=OrderedDict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, key: str):
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
        return None

    def put(self, key: str, value: Any) -> None:
        with self.lock:
            self.items[key] = value
            self.items.move_to_end(key)
            while len(self.items) > self.size:
                self.items.popitem(last=False)


class LocalLLMGateway:
    def __init__(self, runtime: Runtime | None = None, discovery: Discovery | None = None):
        self._runtime = runtime
        self._discovery = discovery
        self._lock = threading.Lock()
        s = get_settings()
        self._sem = threading.BoundedSemaphore(max(1, s.qwen_concurrency))
        self.cache = _Cache()
        self.last_error: str | None = None
        self.last_checked: float = 0.0

    # -- discovery / health
    def refresh(self) -> Discovery:
        with self._lock:
            self._discovery = discover()
            self._runtime = None
            self.last_checked = time.time()
            return self._discovery

    @property
    def discovery(self) -> Discovery:
        if self._discovery is None or (not self._discovery.found and self._runtime is None and time.time() - self.last_checked > 30):
            return self.refresh()
        return self._discovery

    def runtime(self) -> Runtime:
        if self._runtime is not None:
            return self._runtime
        d = self.discovery
        if not d.found:
            raise LLMUnavailable(d.reason)
        s = get_settings()
        with self._lock:
            if self._runtime is None:
                if d.runtime == "llama_cpp":
                    self._runtime = LlamaCppRuntime(d.path or "", s.qwen_n_ctx, s.qwen_threads, s.qwen_gpu_layers)
                elif d.runtime == "ollama":
                    self._runtime = OllamaRuntime(d.base_url or "", d.model or "", s.qwen_n_ctx, s.qwen_threads)
                else:
                    self._runtime = OpenAICompatRuntime(d.base_url or "", d.model or "")
        return self._runtime

    def available(self) -> bool:
        if get_settings().llm_mode == "off":
            return False
        if self._runtime is not None:
            return True
        return self.discovery.found

    def status(self) -> dict[str, Any]:
        d = self.discovery if get_settings().llm_mode != "off" else discover()
        rt = self._runtime
        return {
            "available": self.available(), "mode": get_settings().llm_mode, "discovery": d.as_dict(),
            "runtime_info": rt.info() if rt else {}, "last_error": self.last_error,
            "label": (f"Local Qwen · {d.model}" if d.found else "Local Qwen · not found"),
            "external_fallback": False,
        }

    # -- inference
    def generate(self, *, agent: str, task: str, system: str, user: str, schema: type[BaseModel] | None = None,
                 max_tokens: int | None = None, temperature: float = 0.1, timeout_s: float | None = None,
                 use_cache: bool = True) -> LLMResult:
        s = get_settings()
        if s.llm_mode == "off":
            raise LLMUnavailable("LLM_ENABLED=false")
        rt = self.runtime()
        d = self._discovery or Discovery(found=True, runtime=rt.name, model=getattr(rt, "model", "qwen"))
        target = getattr(rt, "base_url", None) or "http://127.0.0.1/in-process"
        if not is_loopback(target):
            raise LLMUnavailable(f"{target} is not loopback (POL-008)")
        max_tokens = min(max_tokens or s.qwen_max_output_tokens, s.qwen_max_output_tokens)
        timeout_s = timeout_s or s.qwen_timeout_s
        json_schema = schema.model_json_schema() if schema else None

        # Context-window management: keep the prompt within n_ctx minus the output budget.
        budget = max(256, s.qwen_n_ctx - max_tokens - 64)
        truncated = False
        n_sys = rt.count_tokens(system)
        if n_sys + rt.count_tokens(user) > budget:
            keep_chars = max(200, (budget - n_sys) * 4)
            user = user[:keep_chars] + "\n[context truncated to fit the model window]"
            truncated = True

        key = hashlib.sha256(json.dumps([d.model, system, user, json_schema, max_tokens, temperature], sort_keys=True).encode()).hexdigest()
        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                res = LLMResult(**{**hit.as_dict(), "cached": True, "agent": agent, "task": task, "latency_ms": 0.0, "first_token_ms": 0.0})
                telemetry.record(res, ok=True)
                return res

        if not self._sem.acquire(timeout=timeout_s):
            telemetry.record_error(agent, task, d.model or "", rt.name, "concurrency_timeout")
            raise LLMError("Local model busy (concurrency limit) past the timeout")
        t0 = time.perf_counter()
        first: float | None = None
        parts: list[str] = []
        usage: dict[str, Any] = {}
        try:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            for delta, u in rt.stream(messages, max_tokens, json_schema, temperature):
                if u:
                    usage.update({k: v for k, v in u.items() if v is not None})
                if delta:
                    if first is None:
                        first = time.perf_counter() - t0
                    parts.append(delta)
                if time.perf_counter() - t0 > timeout_s:
                    raise LLMError(f"timeout after {timeout_s:.0f}s ({len(parts)} chunks)")
        except LLMError as err:
            self.last_error = str(err)
            telemetry.record_error(agent, task, d.model or "", rt.name, str(err))
            raise
        except Exception as err:  # noqa: BLE001
            self.last_error = f"{type(err).__name__}: {err}"
            telemetry.record_error(agent, task, d.model or "", rt.name, self.last_error)
            raise LLMError(self.last_error) from err
        finally:
            self._sem.release()
        elapsed = time.perf_counter() - t0
        text = "".join(parts).strip()
        p_tok = int(usage.get("prompt_tokens") or rt.count_tokens(system + user))
        c_tok = int(usage.get("completion_tokens") or max(1, rt.count_tokens(text)))
        gen_s = (usage["eval_duration_ns"] / 1e9) if usage.get("eval_duration_ns") else max(1e-6, elapsed - (first or 0))
        data = None
        if schema is not None:
            data = _validate(text, schema)
            if data is None:
                self.last_error = "schema_invalid"
                telemetry.record_error(agent, task, d.model or "", rt.name, "schema_invalid", latency_ms=elapsed * 1000)
                raise LLMError("Model output failed JSON-schema validation")
        res = LLMResult(text, data, d.model or "qwen", rt.name, agent, task, p_tok, c_tok, round(elapsed * 1000, 1),
                        round(first * 1000, 1) if first else None, round(c_tok / gen_s, 1) if gen_s else None, False, truncated)
        self.last_error = None
        self.cache.put(key, res)
        telemetry.record(res, ok=True)
        return res


def _validate(text: str, schema: type[BaseModel]) -> dict[str, Any] | None:
    for candidate in (text, (JSON_OBJECT.search(text) or [None])[0] if JSON_OBJECT.search(text) else None):
        if not candidate:
            continue
        try:
            return schema.model_validate(json.loads(candidate)).model_dump()
        except (ValueError, ValidationError):
            continue
    return None


_gateway: LocalLLMGateway | None = None
_glock = threading.Lock()


def gateway() -> LocalLLMGateway:
    global _gateway
    with _glock:
        if _gateway is None:
            _gateway = LocalLLMGateway()
        return _gateway


def set_gateway(g: LocalLLMGateway | None) -> None:
    """Tests inject a gateway with a fake runtime."""
    global _gateway
    with _glock:
        _gateway = g
