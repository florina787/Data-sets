"""AI Decision Replay: a sanitised, ordered account of how one answer was produced.

Built only from what was recorded while the request ran (node events, LLM call
records, the stored response). Nothing is re-executed. Before anything leaves the
server, the output is sanitised: secret-looking strings are redacted, secret-named
keys and tracebacks are dropped, and long text is truncated. Prompt bodies are never
included, only prompt IDs and versions.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tracing import NODE_INFO
from app.observability.store import TelemetryStore

SECRET_VALUE = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|sk-[0-9A-Za-z_\-]{20,}|hf_[0-9A-Za-z]{20,}|"
                          r"Bearer\s+[0-9A-Za-z._\-]{10,}|(?:api[_-]?key|token|secret|password)=[^&\s]+)", re.I)
SECRET_KEY = re.compile(r"api[_-]?key|authorization|secret|password|credential|traceback|^headers$", re.I)
MAX_TEXT = 300

ENGINE = {"router": "rules", "intent": "rules / LLM", "supervisor": "rules", "retrieval": "FAISS", "evidence": "DuckDB",
          "explanation": "deterministic / LLM", "visualization": "rules", "qa": "rules + DuckDB", "governance": "rules",
          "topic_agent": "DuckDB", "sentiment_agent": "DuckDB", "coaching_agent": "DuckDB", "leadership_agent": "DuckDB", "analytics_agent": "DuckDB"}


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        return {k: sanitize(v, depth + 1) for k, v in value.items() if not SECRET_KEY.search(str(k))}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, depth + 1) for v in list(value)[:40]]
    if isinstance(value, str):
        v = SECRET_VALUE.sub("[redacted]", value)
        return v if len(v) <= MAX_TEXT else v[:MAX_TEXT] + "…"
    return value


def build_replay(store: TelemetryStore, request_id: str) -> dict | None:
    trace = store.trace(request_id)
    if not trace:
        return None
    resp = store.response(request_id) or {}
    req = trace["request"]
    steps = []
    t0 = None
    for n in trace["nodes"]:
        if n["status"] in ("skipped", "cancelled") and not n.get("started_at"):
            continue
        meta = n.get("meta_json") or {}
        if t0 is None and n.get("started_at"):
            t0 = n["started_at"]
        steps.append({
            "node": n["node"], "label": NODE_INFO.get(n["node"], {}).get("label", n["node"]), "role": NODE_INFO.get(n["node"], {}).get("role", ""),
            "engine": ENGINE.get(n["node"], "—"), "status": n["status"], "started_at": n.get("started_at"), "duration_ms": n.get("duration_ms"),
            "output": n.get("output_summary") or {}, "meta": meta, "error": n.get("error"),
        })
    operations = [op for s in steps for op in (s["meta"].get("operations") or []) if isinstance(op, dict)]
    retrieval = [{"node": s["node"], **{k: s["meta"].get(k) for k in ("engine", "mode", "methods", "fusion", "k", "filters", "returned", "latency_ms")},
                  "query": s["output"].get("query")} for s in steps if s["node"] == "retrieval" and s["status"] == "completed"]
    llm = [{"purpose": c["purpose"], "prompt": f"{c['prompt_id']}@{c['prompt_version']}", "model": c["model"],
            "input_tokens": c["input_tokens"], "output_tokens": c["output_tokens"], "total_tokens": c["total_tokens"],
            "tokens_reported": c["total_tokens"] is not None or bool(c["cache_hit"]), "latency_ms": c["latency_ms"], "retries": c["retries"],
            "cache_hit": bool(c["cache_hit"]), "status": c["status"], "error": c["error"]} for c in trace["llm_calls"]]
    qa = resp.get("quality_status") or {}
    decisions = []
    if resp.get("routing"):
        r = resp["routing"]
        decisions.append({"at": "router", "decision": f"Route: {r.get('route')}", "why": r.get("reason")})
    intent = req.get("intent") or {}
    ir = (resp.get("model_metadata") or {}).get("intent_routing") or {}
    if intent:
        decisions.append({"at": "intent", "decision": f"Intent: {ir.get('label') or intent.get('category')} (via {ir.get('method', 'rules')})",
                          "why": ir.get("reason") or intent.get("reasoning") or "",
                          "stages": ir.get("stages"), "semantic": ir.get("semantic"), "llm": ir.get("llm")})
    plan = resp.get("plan") or {}
    if plan:
        decisions.append({"at": "supervisor", "decision": "Plan: " + (", ".join(s["op"] for s in plan.get("steps", [])) or "no operations"),
                          "why": "; ".join(plan.get("notes", [])) or f"Specialist: {plan.get('specialist')}; retrieval: {plan.get('retrieval', {}).get('mode')}"})
    mm = resp.get("model_metadata") or {}
    if mm:
        decisions.append({"at": "explanation", "decision": f"Explanation: {mm.get('explanation_source')}",
                          "why": next((s["meta"].get("reason") for s in steps if s["node"] == "explanation" and s["meta"].get("reason")), "")
                          or ("Model explanation passed the numeric grounding check." if mm.get("explanation_source") == "llm" else "")})
    ev = resp.get("evidence_review") or {}
    if ev:
        decisions.append({"at": "qa", "decision": f"Evidence review: {ev.get('verdict')}", "why": " ".join(ev.get("challenges", [])) or "No challenges raised."})
    return sanitize({
        "intent_routing": ir or None,
        "request_id": request_id, "question": req.get("question"), "created_at": req.get("created_at"), "status": req.get("status"),
        "latency_ms": req.get("latency_ms"), "routing": resp.get("routing"), "token_usage": resp.get("token_usage"),
        "decisions": decisions, "steps": steps, "operations": operations, "retrieval": retrieval, "llm_calls": llm,
        "qa": {"status": qa.get("status"), "passed": qa.get("passed"), "total": qa.get("total"), "checks": qa.get("checks", [])},
        "evidence_review": {k: ev.get(k) for k in ("verdict", "passed", "total", "challenges")} if ev else None,
        "counts": {"nodes": len(steps), "duckdb_operations": len(operations), "faiss_searches": len(retrieval),
                   "llm_calls": len(llm), "llm_calls_live": sum(not c["cache_hit"] for c in llm)},
        "started_at": t0,
        "sanitisation": "Secrets redacted, secret-named fields and tracebacks dropped, text truncated to 300 characters; prompt bodies are not included.",
    })
