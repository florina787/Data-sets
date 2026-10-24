"""Measured benchmarks of the actual machine. Nothing here is estimated."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np

from ..llm.ollama import GenerationStats, LLMUnavailable, OllamaClient

BENCH_PROMPT = "List five uses of a hash map, one short line each."


async def benchmark_llm(client: OllamaClient, model: str, runs: int = 2) -> dict[str, Any]:
    results = []
    for i in range(runs):
        st = GenerationStats(model=model)
        try:
            async for _ in client.chat_stream(
                model, [{"role": "user", "content": BENCH_PROMPT}], options={"num_predict": 96, "temperature": 0}, stats=st
            ):
                pass
        except LLMUnavailable as e:
            return {"model": model, "ok": False, "error": str(e)}
        results.append({"run": i + 1, **st.to_dict()})
    warm = results[-1]
    return {
        "model": model,
        "ok": True,
        "runs": results,
        "cold_first_token_ms": results[0]["first_token_ms"],
        "warm_first_token_ms": warm["first_token_ms"],
        "tokens_per_second": warm["tokens_per_second"],
    }


def benchmark_asr(transcriber_factory, model_size: str, seconds: float = 8.0) -> dict[str, Any]:
    """Real-time factor of the local ASR on synthetic audio.

    The input is generated noise-modulated tones, so accuracy is not measured
    here, only how fast this machine processes audio. RTF < 1 means faster than
    real time.
    """
    sr = 16000
    t = np.arange(int(seconds * sr)) / sr
    rng = np.random.default_rng(0)
    audio = (0.1 * np.sin(2 * np.pi * 220 * t) * (1 + np.sin(2 * np.pi * 3 * t)) + 0.01 * rng.standard_normal(t.size)).astype(np.float32)
    try:
        asr = transcriber_factory(model_size)
        t_load = time.perf_counter()
        asr.load()
        load_ms = (time.perf_counter() - t_load) * 1000
        t0 = time.perf_counter()
        asr.transcribe(audio, use_vad=False)
        elapsed = time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001 - reported to the wizard
        return {"model": model_size, "ok": False, "error": str(e)}
    return {
        "model": model_size,
        "ok": True,
        "audio_seconds": seconds,
        "load_ms": load_ms,
        "process_ms": elapsed * 1000,
        "real_time_factor": elapsed / seconds,
        "note": "Synthetic audio: measures speed only, not accuracy.",
    }


async def run_benchmark(client: OllamaClient, text_model: str | None, asr_size: str, transcriber_factory) -> dict[str, Any]:
    out: dict[str, Any] = {"started_at": time.time()}
    out["llm"] = await benchmark_llm(client, text_model) if text_model else {"ok": False, "error": "no text model selected"}
    out["asr"] = await asyncio.to_thread(benchmark_asr, transcriber_factory, asr_size)
    out["finished_at"] = time.time()
    return out
