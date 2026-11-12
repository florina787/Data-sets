"""Status, hardware, models, settings and metrics."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..llm.ollama import LLMUnavailable
from ..models import hardware
from ..models.benchmark import run_benchmark
from ..models.profiles import MODEL_CATALOG, PROFILES, recommend_profile
from ..runtime.ollama_runtime import RuntimeError_
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
    return {"hardware": hw, "recommendation": recommend_profile(hw), "profiles": PROFILES, "catalog": MODEL_CATALOG}


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
    return {"ollama_running": running, "installed": installed, "profiles": PROFILES, "catalog": MODEL_CATALOG}


# ---------------- local AI runtime ----------------


class WarmReqOptional(BaseModel):
    model: str | None = None


@router.get("/runtime")
async def runtime_status(st: AppState = Depends(get_state)):
    return await st.runtime.status()


@router.post("/runtime/start")
async def runtime_start(st: AppState = Depends(get_state)):
    try:
        out = await st.runtime.ensure_running()
    except RuntimeError_ as e:
        raise HTTPException(409, str(e)) from e
    st.catalog.invalidate()
    return out


@router.post("/runtime/install")
async def runtime_install(st: AppState = Depends(get_state)):
    """Downloads the pinned runtime after the user agreed in Setup. Streams NDJSON progress."""

    async def gen():
        try:
            async for ev in st.runtime.install():
                yield json.dumps(ev) + "\n"
            yield json.dumps({"status": "starting"}) + "\n"
            await st.runtime.ensure_running()
            st.catalog.invalidate()
            yield json.dumps({"status": "ready", "done": True}) + "\n"
        except RuntimeError_ as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/runtime/stop")
async def runtime_stop(st: AppState = Depends(get_state)):
    """Stops the runtime only if VEENA started it; a user's own Ollama keeps running."""
    was_ours = st.runtime.proc is not None
    st.runtime.stop()
    return {"stopped": was_ours}


@router.post("/runtime/cancel")
async def runtime_cancel(st: AppState = Depends(get_state)):
    st.runtime.cancel()
    return {"cancelled": True}


@router.post("/system/healthcheck")
async def healthcheck(body: WarmReqOptional | None = None, st: AppState = Depends(get_state)):
    """A real inference request. Setup only says "VEENA is ready" when this succeeds."""
    model = (body.model if body else None) or st.store.get_settings().get("text_model")
    if not model:
        raise HTTPException(400, "No text model selected yet.")
    t0 = time.perf_counter()
    try:
        answer = await st.llm.chat(
            model, [{"role": "user", "content": "Reply with exactly one word: ready"}], options={"num_predict": 8, "temperature": 0}
        )
    except LLMUnavailable as e:
        return {"ok": False, "model": model, "error": str(e)}
    ms = (time.perf_counter() - t0) * 1000
    ok = bool(answer.strip())
    if ok:
        st.metrics.record("setup.healthcheck_ms", ms, meta={"model": model})
    return {"ok": ok, "model": model, "answer": answer.strip()[:80], "ms": round(ms, 1)}


class PullReq(BaseModel):
    model: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._\-/]{0,80}(:[a-zA-Z0-9._\-]{1,40})?$")


@router.post("/models/pull")
async def pull_model(body: PullReq, st: AppState = Depends(get_state)):
    # Refuse up front when the disk cannot hold the model, rather than failing midway.
    size = MODEL_CATALOG.get(body.model, {}).get("bytes")
    if size:
        free = shutil.disk_usage(st.settings.data_dir).free
        if free < size + 1_000_000_000:
            raise HTTPException(
                507,
                f"Not enough free disk space for {body.model}: it needs about {(size + 1e9) / 1e9:.1f} GB and {free / 1e9:.1f} GB is free.",
            )

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
    if "retrieval_min_score" in patch:
        v = patch["retrieval_min_score"]
        if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or not 0.0 <= v <= 0.9):
            raise HTTPException(400, "retrieval_min_score must be null (automatic) or a number between 0 and 0.9")
    if {"share_usage_stats", "telemetry_id"} & set(patch):
        raise HTTPException(400, "use /api/telemetry to change anonymous statistics consent")
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


class TelemetryReq(BaseModel):
    enabled: bool


@router.get("/telemetry")
async def telemetry_status(st: AppState = Depends(get_state)):
    """Consent state and exactly what is queued to be sent (nothing unless opted in)."""
    return st.telemetry.status()


@router.post("/telemetry")
async def telemetry_consent(body: TelemetryReq, st: AppState = Depends(get_state)):
    if body.enabled:
        if not st.telemetry.available:
            raise HTTPException(409, "anonymous statistics are not available in this build")
        out = st.telemetry.opt_in()
    else:
        out = st.telemetry.opt_out()
    asyncio.get_running_loop().create_task(st.telemetry.flush())  # background; never delays the reply
    return out


@router.post("/telemetry/send-now")
async def telemetry_send_now(st: AppState = Depends(get_state)):
    """Sends anything queued immediately (only if the user opted in). Shown in Settings and used by tests."""
    return {"result": await st.telemetry.flush(), **st.telemetry.status()}
