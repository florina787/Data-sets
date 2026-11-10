"""Prometheus metrics and token-usage reporting, with no extra dependency.

``/metrics`` serves the Prometheus text exposition format (version 0.0.4), so the app can be
scraped by an existing Prometheus / Grafana stack (or any agent that reads that format)
when it runs on Kubernetes. Labels never carry usernames, prompts or other personal data.
HTTP counters are in-process; database-derived figures are read at scrape time.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from app.memory.store import get_store

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
_lock = threading.Lock()
_requests: dict[tuple[str, str, str], int] = defaultdict(int)
_hist: dict[tuple[str, str], list[float]] = {}  # (method, route) -> [bucket counts..., sum, count]
_started = time.time()


def observe_request(method: str, route: str, status: int, seconds: float) -> None:
    with _lock:
        _requests[(method, route, str(status))] += 1
        h = _hist.setdefault((method, route), [0.0] * (len(BUCKETS) + 2))
        for i, b in enumerate(BUCKETS):
            if seconds <= b:
                h[i] += 1
        h[-2] += seconds
        h[-1] += 1


def _esc(v: object) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _line(name: str, value: float | int | None, labels: dict | None = None) -> str:
    lab = ",".join(f'{k}="{_esc(v)}"' for k, v in (labels or {}).items())
    return f"{name}{{{lab}}} {0 if value is None else value}" if lab else f"{name} {0 if value is None else value}"


def prometheus_text() -> str:
    from app import resources
    from app.llm import local as local_llm
    from app.vision import service as vision

    out: list[str] = []

    def metric(name: str, kind: str, help_text: str, samples: list[tuple[dict | None, float | int | None]]) -> None:
        out.append(f"# HELP {name} {help_text}")
        out.append(f"# TYPE {name} {kind}")
        out.extend(_line(name, v, lab) for lab, v in samples)

    r = resources.snapshot()
    metric("foodcare_up", "gauge", "1 while the backend is serving.", [(None, 1)])
    metric("foodcare_uptime_seconds", "gauge", "Seconds since the backend process started.",
           [(None, round(time.time() - _started, 1))])
    metric("foodcare_machine_cpu_percent", "gauge", "Machine CPU utilisation (psutil).", [(None, r["cpu_percent"])])
    metric("foodcare_machine_memory_percent", "gauge", "Machine RAM utilisation (psutil).", [(None, r["ram_percent"])])
    metric("foodcare_process_cpu_percent", "gauge", "Backend process CPU utilisation.",
           [(None, r["process"]["cpu_percent"])])
    metric("foodcare_process_resident_memory_bytes", "gauge", "Backend process resident memory.",
           [(None, int(r["process"]["rss_mb"] * 1e6))])
    with _lock:
        reqs = dict(_requests)
        hist = {k: list(v) for k, v in _hist.items()}
    metric("foodcare_http_requests_total", "counter", "HTTP requests by method, route template and status.",
           [({"method": m, "route": rt, "status": st}, n) for (m, rt, st), n in sorted(reqs.items())])
    out.append("# HELP foodcare_http_request_duration_seconds HTTP request latency by method and route template.")
    out.append("# TYPE foodcare_http_request_duration_seconds histogram")
    for (m, rt), h in sorted(hist.items()):
        name = "foodcare_http_request_duration_seconds_bucket"
        for i, b in enumerate(BUCKETS):
            out.append(_line(name, int(h[i]), {"method": m, "route": rt, "le": b}))
        out.append(_line(name, int(h[-1]), {"method": m, "route": rt, "le": "+Inf"}))
        out.append(_line("foodcare_http_request_duration_seconds_sum", round(h[-2], 6), {"method": m, "route": rt}))
        out.append(_line("foodcare_http_request_duration_seconds_count", int(h[-1]), {"method": m, "route": rt}))

    store = get_store()
    metric("foodcare_agent_runs_total", "counter", "Recorded agent runs by agent and status.",
           [({"agent": a["agent"], "status": a["status"]}, a["n"]) for a in store.query(
               "SELECT agent, status, COUNT(*) AS n FROM agent_runs GROUP BY agent, status")])
    metric("foodcare_tool_calls_total", "counter", "Recorded tool calls by tool and status.",
           [({"tool": t["tool"], "status": t["status"]}, t["n"]) for t in store.query(
               "SELECT tool, status, COUNT(*) AS n FROM tool_calls GROUP BY tool, status")])
    usage = store.query("SELECT model, purpose, status, COUNT(*) AS calls, SUM(cached) AS cached,"
                        " COALESCE(SUM(prompt_tokens), 0) AS prompt, COALESCE(SUM(completion_tokens), 0) AS completion,"
                        " SUM(CASE WHEN prompt_tokens IS NULL AND cached = 0 AND status = 'ok' THEN 1 ELSE 0 END)"
                        " AS unreported FROM llm_usage GROUP BY model, purpose, status")
    metric("foodcare_llm_requests_total", "counter", "Local-model calls by model, purpose and status.",
           [({"model": u["model"], "purpose": u["purpose"], "status": u["status"]}, u["calls"]) for u in usage])
    metric("foodcare_llm_cache_hits_total", "counter", "Local-model calls answered from the prompt cache.",
           [({"model": u["model"], "purpose": u["purpose"]}, u["cached"] or 0) for u in usage if u["status"] == "ok"])
    tok: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for u in usage:
        t = tok[(u["model"], u["purpose"])]
        t[0] += u["prompt"]
        t[1] += u["completion"]
        t[2] += u["unreported"] or 0
    metric("foodcare_llm_tokens_total", "counter", "Tokens reported by the local model server.",
           [({"model": m, "purpose": p, "type": "prompt"}, v[0]) for (m, p), v in tok.items()]
           + [({"model": m, "purpose": p, "type": "completion"}, v[1]) for (m, p), v in tok.items()])
    metric("foodcare_llm_calls_without_token_counts_total", "counter",
           "Successful calls where the server did not report token usage (never estimated).",
           [({"model": m, "purpose": p}, v[2]) for (m, p), v in tok.items()])
    llm = local_llm.status() if not local_llm._client else local_llm._client.status(probe=False)
    metric("foodcare_llm_configured", "gauge", "1 when a local model server is configured.",
           [(None, int(bool(llm.get("configured"))))])
    metric("foodcare_llm_queue_depth", "gauge", "Local-model requests waiting.", [(None, llm.get("queue_depth", 0))])
    metric("foodcare_llm_in_flight", "gauge", "Local-model requests running.", [(None, llm.get("in_flight", 0))])
    gate = vision.gate().status()
    metric("foodcare_vision_jobs_running", "gauge", "Image inspections running.", [(None, gate["running"])])
    metric("foodcare_vision_jobs_queued", "gauge", "Image inspections waiting.", [(None, gate["queued"])])
    metric("foodcare_vision_jobs_rejected_total", "counter", "Image inspections refused because the queue was full.",
           [(None, gate["rejected"])])
    stats = store.stats()
    metric("foodcare_memory_db_bytes", "gauge", "Size of the memory database files.", [(None, stats["bytes"])])
    metric("foodcare_conversations", "gauge", "Saved conversations.", [(None, stats["conversations"])])
    return "\n".join(out) + "\n"


def token_usage(days: int = 30, username: str | None = None) -> dict:
    """Token usage over the last ``days``; with ``username``, only that user's calls."""
    store = get_store()
    where, params = ["ts >= datetime('now', ?)"], [f"-{int(days)} days"]
    if username:
        where.append("username = ?")
        params.append(username)
    clause = " AND ".join(where)
    totals = store.query(
        f"SELECT COUNT(*) AS calls, SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,"
        f" SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS failed, SUM(cached) AS cached,"
        f" COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, COALESCE(SUM(completion_tokens), 0) AS completion_tokens,"
        f" SUM(CASE WHEN prompt_tokens IS NULL AND cached = 0 AND status = 'ok' THEN 1 ELSE 0 END) AS unreported,"
        f" COALESCE(SUM(prompt_chars), 0) AS prompt_chars FROM llm_usage WHERE {clause}", tuple(params))[0]
    by_day = store.query(
        f"SELECT substr(ts, 1, 10) AS day, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
        f" COALESCE(SUM(completion_tokens), 0) AS completion_tokens FROM llm_usage WHERE {clause}"
        f" GROUP BY day ORDER BY day", tuple(params))
    by_purpose = store.query(
        f"SELECT purpose, model, COUNT(*) AS calls, COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
        f" COALESCE(SUM(completion_tokens), 0) AS completion_tokens, AVG(latency_ms) AS avg_latency_ms"
        f" FROM llm_usage WHERE {clause} GROUP BY purpose, model ORDER BY calls DESC", tuple(params))
    lat = sorted(x["latency_ms"] for x in store.query(
        f"SELECT latency_ms FROM llm_usage WHERE {clause} AND latency_ms IS NOT NULL AND cached = 0", tuple(params)))
    calls = totals["calls"] or 0
    return {
        "days": days, "scope": "you" if username else "all users",
        "totals": {**{k: (totals[k] or 0) for k in totals}, "cache_hit_rate": round((totals["cached"] or 0) / calls, 3)
                   if calls else None},
        "latency_ms": {"p50": lat[len(lat) // 2] if lat else None,
                       "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None, "samples": len(lat)},
        "by_day": by_day, "by_purpose": by_purpose,
        "note": "Tokens are counted only when the local model server reports them; they are never estimated. "
                "A local model has no per-token charge.",
    }
