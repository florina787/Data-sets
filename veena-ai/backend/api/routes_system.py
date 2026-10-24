"""Status, hardware, models, settings and metrics."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..llm.ollama import LLMUnavailable
from ..models import hardware
from ..models.benchmark import run_benchmark
from ..models.profiles import PROFILES, recommend_profile
from ..vision.ocr import tesseract_available
from .state import AppState, get_state

router = APIRouter(prefix="/api")


@router.get("/status")
async def status(st: AppState = Depends(get_state)):
    version = await st.llm.version()
    models: list[dict] = []
    if version:
        try:
            models = [m.to_dict() for m in await st.catalog.installed(refresh=True)]
        except LLMUnavailable:
            pass
    s = st.store.get_settings()
    return {
        "ollama": {"running": version is not None, "version": version, "url": st.settings.ollama_url},
        "models": models,
        "tesseract": tesseract_available(),
        "asr": st.asr_status(),
        "embedder": {"model": st.kb.embedder.model_name, "loaded": st.kb.embedder._model is not None},
        "onboarded": s["onboarded"],
        "profile": s["profile"],
        "data_dir": str(st.settings.data_dir),
    }


@router.get("/system/hardware")
async def system_hardware(st: AppState = Depends(get_state)):
    hw = await asyncio.to_thread(hardware.detect, st.settings.data_dir)
    return {"hardware": hw, "recommendation": recommend_profile(hw), "profiles": PROFILES}


class BenchmarkReq(BaseModel):
    text_model: str | None = None
    asr_model: str = "base"


@router.post("/system/benchmark")
async def system_benchmark(body: BenchmarkReq, st: AppState = Depends(get_state)):
    result = await run_benchmark(st.llm, body.text_model, body.asr_model, lambda size: st.asr(size, None))
    if result["llm"].get("ok"):
        st.metrics.record("bench.tokens_per_s", result["llm"]["tokens_per_second"] or 0, unit="tok/s", meta={"model": body.text_model})
    if result["asr"].get("ok"):
        st.metrics.record("bench.asr_rtf", result["asr"]["real_time_factor"], unit="ratio", meta={"model": body.asr_model})
    return result


@router.get("/models")
async def models(st: AppState = Depends(get_state)):
    try:
        installed = [m.to_dict() for m in await st.catalog.installed(refresh=True)]
        running = True
    except LLMUnavailable:
        installed, running = [], False
    return {"ollama_running": running, "installed": installed, "profiles": PROFILES}


class PullReq(BaseModel):
    model: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._\-/]{0,80}(:[a-zA-Z0-9._\-]{1,40})?$")


@router.post("/models/pull")
async def pull_model(body: PullReq, st: AppState = Depends(get_state)):
    async def gen():
        try:
            async for ev in st.llm.pull(body.model):
                yield json.dumps(ev) + "\n"
            st.catalog.invalidate()
            yield json.dumps({"status": "success", "done": True}) + "\n"
        except Exception as e:  # noqa: BLE001
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


class WarmReq(BaseModel):
    model: str


@router.post("/models/warm")
async def warm(body: WarmReq, st: AppState = Depends(get_state)):
    await st.llm.warm(body.model)
    return {"ok": True}


@router.get("/settings")
async def get_settings(st: AppState = Depends(get_state)):
    return st.store.get_settings()


@router.patch("/settings")
async def patch_settings(patch: dict[str, Any], st: AppState = Depends(get_state)):
    try:
        out = st.store.update_settings(patch)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    if "retention_days" in patch:
        st.store.purge_expired(int(out["retention_days"] or 0))
    return out


@router.get("/metrics")
async def metrics(days: int = 30, st: AppState = Depends(get_state)):
    return {
        "live": st.metrics.live(),
        "history": st.metrics.history(days),
        "resources": st.metrics.resources(),
        "counts": st.store.counts(),
        "practice": st.coach.all_scores(),
        "embedding_cache_hits": st.kb.embedder.cache_hits,
    }
