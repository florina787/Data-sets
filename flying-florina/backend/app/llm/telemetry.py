"""Measured inference telemetry for the local Qwen gateway (nothing here is estimated or invented).

Each call is kept in an in-memory ring buffer and persisted to the `llm_calls` table so the
monitoring dashboard survives restarts. System figures come from the OS (load average, process
resident memory); GPU utilisation is reported only when a tool on the machine can measure it.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Any

from app.core import db
from app.core.util import now_iso

_buf: deque = deque(maxlen=2000)
_lock = threading.Lock()
_load: dict[str, Any] = {}


def note_load(ms: float) -> None:
    _load["model_load_ms"] = ms
    _load["loaded_at"] = now_iso()


def _persist(row: dict[str, Any]) -> None:
    try:
        with db.session(write=True) as conn:
            conn.execute(
                "INSERT INTO llm_calls (ts, agent, task, model, runtime, ok, cached, prompt_tokens, completion_tokens, latency_ms, "
                "first_token_ms, tokens_per_s, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["ts"], row["agent"], row["task"], row["model"], row["runtime"], int(row["ok"]), int(row["cached"]), row["prompt_tokens"],
                 row["completion_tokens"], row["latency_ms"], row["first_token_ms"], row["tokens_per_s"], row["error"]))
    except Exception:  # noqa: BLE001, S110 - telemetry must never break inference
        pass


def record(res: Any, ok: bool = True) -> None:
    row = {"ts": now_iso(), "agent": res.agent, "task": res.task, "model": res.model, "runtime": res.runtime, "ok": ok, "cached": res.cached,
           "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens, "latency_ms": res.latency_ms,
           "first_token_ms": res.first_token_ms, "tokens_per_s": res.tokens_per_s, "error": None}
    with _lock:
        _buf.append(row)
    _persist(row)


def record_error(agent: str, task: str, model: str, runtime: str, error: str, latency_ms: float = 0.0) -> None:
    row = {"ts": now_iso(), "agent": agent, "task": task, "model": model, "runtime": runtime, "ok": False, "cached": False, "prompt_tokens": 0,
           "completion_tokens": 0, "latency_ms": latency_ms, "first_token_ms": None, "tokens_per_s": None, "error": error[:300]}
    with _lock:
        _buf.append(row)
    _persist(row)


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = min(len(v) - 1, max(0, round(p * (len(v) - 1))))
    return round(v[k], 1)


def system_stats() -> dict[str, Any]:
    out: dict[str, Any] = {"platform": platform.platform(), "cpu_count": os.cpu_count(), "python": platform.python_version()}
    try:
        out["load_avg_1m"] = round(os.getloadavg()[0], 2)
        out["cpu_load_pct"] = round(100 * os.getloadavg()[0] / (os.cpu_count() or 1), 1)
    except OSError:
        pass
    rss = None
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
    except OSError:
        try:
            import resource

            r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss = r if platform.system() == "Darwin" else r * 1024
        except Exception:  # noqa: BLE001
            rss = None
    out["process_rss_mb"] = round(rss / 1e6, 1) if rss else None
    try:
        with open("/proc/meminfo") as fh:
            info = {line.split(":")[0]: int(line.split()[1]) for line in fh}
        out["system_mem_total_mb"] = round(info["MemTotal"] / 1024)
        out["system_mem_available_mb"] = round(info["MemAvailable"] / 1024)
    except (OSError, KeyError):
        pass
    out["gpu"] = _gpu()
    return out


def _gpu() -> dict[str, Any]:
    if shutil.which("nvidia-smi"):
        try:
            cmd = ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)  # noqa: S607 - fixed read-only query of a local tool
            name, util, used, total = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
            return {"available": True, "name": name, "utilization_pct": float(util), "memory_used_mb": float(used), "memory_total_mb": float(total)}
        except Exception:  # noqa: BLE001
            return {"available": None, "detail": "nvidia-smi present but unreadable"}
    if platform.system() == "Darwin":
        return {"available": None, "detail": "Apple GPU (Metal) utilisation is not exposed without sudo; see llama.cpp gpu_layers_used."}
    return {"available": False, "detail": "No GPU tool found; inference runs on CPU."}


def metrics(window: int = 500) -> dict[str, Any]:
    rows = db.query("SELECT * FROM llm_calls ORDER BY id DESC LIMIT ?", (window,))
    rows.reverse()
    live = [r for r in rows if r["ok"] and not r["cached"]]
    lat = [r["latency_ms"] for r in live if r["latency_ms"]]
    ttft = [r["first_token_ms"] for r in live if r["first_token_ms"]]
    tps = [r["tokens_per_s"] for r in live if r["tokens_per_s"]]
    total = len(rows)
    cached = sum(r["cached"] for r in rows)
    errors = [r for r in rows if not r["ok"]]
    per_agent: dict[str, dict[str, Any]] = {}
    for r in rows:
        a = per_agent.setdefault(r["agent"], {"agent": r["agent"], "calls": 0, "cached": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": []})
        a["calls"] += 1
        a["cached"] += r["cached"]
        a["errors"] += 0 if r["ok"] else 1
        a["prompt_tokens"] += r["prompt_tokens"] or 0
        a["completion_tokens"] += r["completion_tokens"] or 0
        if r["ok"] and not r["cached"] and r["latency_ms"]:
            a["latency_ms"].append(r["latency_ms"])
    agents = []
    for a in per_agent.values():
        a["p50_ms"] = _pct(a.pop("latency_ms"), 0.5) if a.get("latency_ms") is not None else None
        agents.append(a)
    return {
        "calls": total, "live_calls": len(live), "cached_calls": cached, "errors": len(errors),
        "cache_hit_rate": round(cached / total, 3) if total else None,
        "latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95), "max": max(lat) if lat else None},
        "first_token_ms": {"p50": _pct(ttft, 0.5), "p95": _pct(ttft, 0.95)},
        "tokens_per_s": {"p50": _pct(tps, 0.5), "mean": round(sum(tps) / len(tps), 1) if tps else None},
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows), "completion_tokens": sum(r["completion_tokens"] or 0 for r in rows),
        "by_agent": sorted(agents, key=lambda x: -x["calls"]),
        "recent": rows[-40:], "recent_errors": errors[-10:], "load": dict(_load), "system": system_stats(),
        "measured_at": time.time(),
    }
