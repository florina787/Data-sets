"""Local open-source LLM via llama.cpp (no API key, runs on CPU).

Default model: Qwen2.5-1.5B-Instruct, GGUF Q4_K_M (~1.1 GB), downloaded once from
Hugging Face into data/models/. Structured outputs use llama.cpp's JSON-schema
grammar, so every response is syntactically valid JSON for the schema; it is still
validated with Pydantic before use. Shares the cache, repair, rate limiting,
circuit breaker and telemetry of the other providers (cost is always $0).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings
from app.llm.cache import ResponseCache
from app.llm.gemini_client import GeminiClient
from app.llm.resilience import CircuitBreaker, RateLimiter
from app.llm.usage import Usage, usage_from_openai
from app.prompts.registry import PromptVersion

_load_lock = threading.Lock()
_models: dict[str, object] = {}


def model_path(settings: Settings) -> Path:
    return settings.local_model_dir / settings.local_model_file


def download_model(settings: Settings) -> Path:
    from huggingface_hub import hf_hub_download

    settings.local_model_dir.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(settings.local_model_repo, settings.local_model_file, local_dir=str(settings.local_model_dir)))


def _load(path: Path, n_ctx: int, threads: int):
    with _load_lock:
        key = f"{path}:{n_ctx}"
        if key not in _models:
            from llama_cpp import Llama

            _models[key] = Llama(model_path=str(path), n_ctx=n_ctx, n_threads=threads, verbose=False)
        return _models[key]


class LocalLlamaClient(GeminiClient):
    name = "local"

    def __init__(self, settings: Settings, llama=None, sleep=time.sleep):
        self.settings = settings
        self.model = settings.local_model_file.removesuffix(".gguf")
        path = model_path(settings)
        if llama is None and not path.exists():
            raise FileNotFoundError(f"Local model not found at {path}. Run `make llm-download`.")
        self._llama = llama
        self._path = path
        self._sleep = sleep
        # One generation at a time: llama.cpp contexts are not thread-safe and CPU is the bottleneck.
        self.limiter = RateLimiter(10_000, 1, sleep=sleep)
        self.breaker = CircuitBreaker(settings.gemini_circuit_threshold, settings.gemini_circuit_cooldown_seconds)
        self.cache = ResponseCache(settings.llm_cache_path)
        self.last_success: str | None = None
        self.provider = "local"
        self.label = "Local LLM"
        self.costs = (0.0, 0.0)

    @property
    def llama(self):
        if self._llama is None:
            self._llama = _load(self._path, self.settings.local_n_ctx, self.settings.local_threads)
        return self._llama

    def _invoke(self, prompt: PromptVersion, user: str, schema: type[BaseModel] | None, stream: bool) -> tuple[str, Usage]:
        mc = prompt.model_config
        kwargs: dict = {
            "messages": [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}],
            "temperature": mc.get("temperature", self.settings.gemini_temperature),
            "max_tokens": min(mc.get("max_output_tokens", 1024), self.settings.local_max_output_tokens),
        }
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object", "schema": schema.model_json_schema()}
        r = self.llama.create_chat_completion(**kwargs)
        usage = usage_from_openai(r.get("usage"))
        return r["choices"][0]["message"].get("content") or "", usage

    def status(self) -> dict:
        st = super().status()
        st["note"] = "Runs on this machine's CPU; slower than hosted models."
        return st
