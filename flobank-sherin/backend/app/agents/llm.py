"""Optional local Qwen via Ollama. Every call returns *measured* token counts and latency from Ollama's response.

If Ollama is unreachable the caller gets None and continues with deterministic tools; nothing is fabricated.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import get_settings

log = logging.getLogger("sherin.llm")
_status_cache: dict = {"t": 0.0, "ok": False, "models": []}


def status(force: bool = False) -> dict:
    s = get_settings()
    if not s.llm_enabled:
        return {"available": False, "reason": "LLM disabled by configuration", "model": s.ollama_model, "url": s.ollama_url}
    if force or time.time() - _status_cache["t"] > 30:
        try:
            r = httpx.get(f"{s.ollama_url}/api/tags", timeout=1.5)
            r.raise_for_status()
            _status_cache.update(ok=True, models=[m.get("name") for m in r.json().get("models", [])])
        except Exception as e:  # noqa: BLE001
            _status_cache.update(ok=False, models=[], err=str(e)[:120])
        _status_cache["t"] = time.time()
    ok = _status_cache["ok"] and any(m.startswith(s.ollama_model.split(":")[0]) for m in _status_cache["models"])
    return {"available": ok, "model": s.ollama_model, "url": s.ollama_url,
            "reason": None if ok else ("model not pulled" if _status_cache["ok"] else "Ollama not reachable")}


def generate(prompt: str, system: str = "", max_tokens: int = 600) -> dict | None:
    s = get_settings()
    if not status()["available"]:
        return None
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{s.ollama_url}/api/generate", timeout=s.ollama_timeout_s,
                       json={"model": s.ollama_model, "prompt": prompt, "system": system, "stream": False,
                             "options": {"num_predict": max_tokens, "temperature": 0.2}})
        r.raise_for_status()
        j = r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("ollama call failed: %s", e)
        return None
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return {"text": j.get("response", ""), "input_tokens": int(j.get("prompt_eval_count") or 0), "output_tokens": int(j.get("eval_count") or 0),
            "latency_ms": latency_ms, "model": s.ollama_model}
