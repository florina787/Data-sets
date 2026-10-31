"""Local Qwen status, health check, live test, benchmark and measured telemetry."""

from __future__ import annotations

import statistics
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope
from app.core import audit
from app.core.security import Actor, current_actor
from app.llm import telemetry
from app.llm.gateway import LLMError, LLMUnavailable, gateway

router = APIRouter()

BENCH_PROMPTS = [
    ("Summarise in one sentence: AC-204 vibration index 7-day mean 1.265 vs baseline 0.476; 17 days rising.", 60),
    ("List two checks an engineer should review when vibration and EGT rise together. Reply in under 40 words.", 60),
    ("Explain in two sentences why a read-only API facade reduces risk when modernizing a legacy MRO database.", 80),
]


@router.get("/api/llm/status")
def llm_status(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, gateway().status())


@router.post("/api/llm/refresh")
def llm_refresh(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    d = gateway().refresh()
    audit.append(actor.id, "llm.discovery", f"Qwen discovery: {'found ' + str(d.model) if d.found else 'not found'}", {"runtime": d.runtime, "reason": d.reason})
    return envelope(request, gateway().status())


@router.get("/api/llm/metrics")
def llm_metrics(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, {**telemetry.metrics(), "status": gateway().status()})


class TestBody(BaseModel):
    prompt: str = Field(default="In one short sentence, say which aircraft subsystem a vibration index usually monitors.", max_length=500)


@router.post("/api/llm/test")
def llm_test(request: Request, body: TestBody | None = None, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """One real inference against the user's Qwen model (no cache)."""
    prompt = (body or TestBody()).prompt
    try:
        r = gateway().generate(agent="Health Check", task="health_check", system="You are a concise assistant. Answer in one sentence.",
                               user=prompt, max_tokens=60, use_cache=False)
    except LLMUnavailable as err:
        raise ApiError(503, "qwen_unavailable", str(err)) from err
    except LLMError as err:
        raise ApiError(502, "qwen_error", str(err)) from err
    return envelope(request, r.as_dict())


class BenchBody(BaseModel):
    repeats: int = Field(default=2, ge=1, le=10)


@router.post("/api/llm/benchmark")
def llm_benchmark(request: Request, body: BenchBody | None = None, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Measured, uncached benchmark on this machine: p50/p95 latency, time to first token, tokens/s."""
    g = gateway()
    if not g.available():
        raise ApiError(503, "qwen_unavailable", g.discovery.reason)
    runs = []
    t0 = time.perf_counter()
    for _ in range((body or BenchBody()).repeats):
        for prompt, n in BENCH_PROMPTS:
            try:
                r = g.generate(agent="Benchmark", task="benchmark", system="Answer briefly and factually.", user=prompt, max_tokens=n, use_cache=False)
                runs.append(r.as_dict())
            except (LLMError, LLMUnavailable) as err:
                runs.append({"error": str(err)})
    ok = [r for r in runs if "error" not in r]
    lat = sorted(r["latency_ms"] for r in ok)

    def pct(v: list[float], p: float) -> float | None:
        return round(v[min(len(v) - 1, round(p * (len(v) - 1)))], 1) if v else None

    return envelope(request, {
        "model": g.discovery.model, "runtime": g.discovery.runtime, "quantization": g.discovery.quantization, "runs": len(runs), "ok": len(ok),
        "latency_ms": {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95)},
        "first_token_ms": {"p50": pct(sorted(r["first_token_ms"] for r in ok if r["first_token_ms"]), 0.5)},
        "tokens_per_s": {"mean": round(statistics.mean([r["tokens_per_s"] for r in ok if r["tokens_per_s"]]), 1) if ok else None},
        "total_s": round(time.perf_counter() - t0, 2), "details": runs, "system": telemetry.system_stats(),
    })
