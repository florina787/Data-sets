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
from app.llm.budget import DeadlineExceeded, remaining, report_text
from app.llm.cache import ResponseCache
from app.llm.gemini_client import GeminiClient
from app.llm.resilience import CircuitBreaker, RateLimiter
from app.llm.usage import Usage, usage_from_openai
from app.prompts.registry import PromptVersion

_load_lock = threading.Lock()
_models: dict[str, object] = {}
LOAD_STATS: dict[str, object] = {}  # load time and GPU offload of the warm instance, shown in model status and traces
FALLBACK_PROMPT_TOKENS_PER_S = 60.0  # used for the pre-call budget check until a real prompt-evaluation rate is measured
FALLBACK_GEN_TOKENS_PER_S = 12.0  # likewise for generation speed
EXPECTED_OUTPUT_TOKENS = 120  # a short structured answer; measured answers were 130-190 tokens


def model_path(settings: Settings) -> Path:
    return settings.local_model_dir / settings.local_model_file


def download_model(settings: Settings) -> Path:
    from huggingface_hub import hf_hub_download

    settings.local_model_dir.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(settings.local_model_repo, settings.local_model_file, local_dir=str(settings.local_model_dir)))


def _load(path: Path, n_ctx: int, threads: int, gpu_layers: int = 0):
    """One warm instance per process: loaded once, reused by every request (llama.cpp also reuses the KV cache of a
    shared prompt prefix between calls)."""
    with _load_lock:
        key = f"{path}:{n_ctx}"
        if key not in _models:
            import llama_cpp
            from llama_cpp import Llama

            gpu = gpu_layers if llama_cpp.llama_supports_gpu_offload() else 0
            t0 = time.perf_counter()
            _models[key] = Llama(model_path=str(path), n_ctx=n_ctx, n_threads=threads, n_gpu_layers=gpu, verbose=False)
            LOAD_STATS.update(load_ms=round((time.perf_counter() - t0) * 1000, 1), gpu_offload_supported=bool(llama_cpp.llama_supports_gpu_offload()),
                              n_gpu_layers=gpu, n_threads=threads)
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
        self.prompt_tokens_per_s: float | None = None  # measured on this machine, moving average
        self.gen_tokens_per_s: float | None = None
        self.last_perf: dict = {}

    @property
    def llama(self):
        if self._llama is None:
            self._llama = _load(self._path, self.settings.local_n_ctx, self.settings.local_threads, self.settings.local_n_gpu_layers)
        return self._llama

    def _perf(self) -> dict:
        try:
            import llama_cpp

            p = llama_cpp.llama_perf_context(self.llama._ctx.ctx)
            return {"prompt_tokens": p.n_p_eval, "reused_prompt_tokens": p.n_reused, "prompt_eval_ms": round(p.t_p_eval_ms, 1),
                    "generated_tokens": p.n_eval, "generation_ms": round(p.t_eval_ms, 1)}
        except Exception:  # noqa: BLE001 - a fake model in tests has no counters
            return {}

    def _reset_perf(self) -> None:
        try:
            import llama_cpp

            llama_cpp.llama_perf_context_reset(self.llama._ctx.ctx)
        except Exception:  # noqa: BLE001
            pass

    def _invoke(self, prompt: PromptVersion, user: str, schema: type[BaseModel] | None, stream: bool) -> tuple[str, Usage]:
        mc = prompt.model_config
        kwargs: dict = {
            "messages": [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}],
            "temperature": mc.get("temperature", self.settings.gemini_temperature),
            "max_tokens": min(mc.get("max_output_tokens", 1024), self.settings.local_max_output_tokens),
        }
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object", "schema": schema.model_json_schema()}
        left = remaining()
        if left is not None:
            # Skip a call whose prompt alone would overrun the budget at this machine's measured reading speed.
            try:
                n_prompt = len(self.llama.tokenize((prompt.system + "\n" + user).encode(), add_bos=False))
            except AttributeError:  # a test double without a tokenizer
                n_prompt = len((prompt.system + user).split())
            # Skip a call that cannot finish: reading the prompt plus writing a short answer, at this machine's measured speeds.
            # Starting it anyway would spend the whole budget and still end in the deterministic fallback.
            rate = self.prompt_tokens_per_s or FALLBACK_PROMPT_TOKENS_PER_S
            gen = self.gen_tokens_per_s or FALLBACK_GEN_TOKENS_PER_S
            need = n_prompt / rate + min(EXPECTED_OUTPUT_TOKENS, kwargs["max_tokens"]) / gen
            if need > left:
                raise DeadlineExceeded(f"~{n_prompt} prompt tokens at {rate:.0f} tok/s plus a ~{EXPECTED_OUTPUT_TOKENS}-token answer at {gen:.0f} tok/s "
                                       f"needs ~{need:.1f}s; budget left {left:.1f}s")
        self._reset_perf()
        t0 = time.perf_counter()
        first: float | None = None
        parts: list[str] = []
        usage_block = None
        try:
            stream = self.llama.create_chat_completion(stream=True, **kwargs)  # streamed so the budget is checked between tokens
            if isinstance(stream, dict):  # a backend (or test double) that answers in one piece
                msg = stream["choices"][0]["message"]
                stream = [{"choices": [{"delta": {"content": msg.get("content") or ""}}], "usage": stream.get("usage")}]
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {}).get("content") or ""
                usage_block = chunk.get("usage") or usage_block
                if delta:
                    if first is None:
                        first = time.perf_counter() - t0
                    parts.append(delta)
                    report_text("".join(parts))
                left = remaining()
                if left is not None and left <= 0:
                    raise DeadlineExceeded(f"stopped after {len(parts)} tokens; time budget reached")
        finally:
            perf = self._perf()
            perf.update(wall_ms=round((time.perf_counter() - t0) * 1000, 1), first_token_ms=round(first * 1000, 1) if first else None, **LOAD_STATS)
            if perf.get("prompt_eval_ms"):
                perf["prompt_tokens_per_s"] = round(perf["prompt_tokens"] / (perf["prompt_eval_ms"] / 1000), 1)
                rate = perf["prompt_tokens_per_s"]
                self.prompt_tokens_per_s = rate if self.prompt_tokens_per_s is None else round(0.7 * self.prompt_tokens_per_s + 0.3 * rate, 1)
            if perf.get("generation_ms"):
                perf["generated_tokens_per_s"] = round(perf["generated_tokens"] / (perf["generation_ms"] / 1000), 1)
                g = perf["generated_tokens_per_s"]
                self.gen_tokens_per_s = g if self.gen_tokens_per_s is None else round(0.7 * self.gen_tokens_per_s + 0.3 * g, 1)
            self.last_perf = perf
        if perf.get("prompt_tokens") is not None:
            p_in, p_out = perf["prompt_tokens"] + perf.get("reused_prompt_tokens", 0), perf["generated_tokens"]
            usage = Usage(p_in, p_out, p_in + p_out)
        else:
            usage = usage_from_openai(usage_block)
        return "".join(parts), usage

    def status(self) -> dict:
        st = super().status()
        st["note"] = "Runs on this machine; slower than hosted models."
        st["load"] = dict(LOAD_STATS)
        st["prompt_tokens_per_s"] = self.prompt_tokens_per_s
        st["generated_tokens_per_s"] = self.gen_tokens_per_s
        return st
