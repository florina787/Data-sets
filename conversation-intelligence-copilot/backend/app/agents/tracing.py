"""Node instrumentation: real start/finish events, timing, failure capture.

Every graph node is wrapped so that (a) a `node_start` event is emitted to the
stream before it runs and a `node_end` event after, which is what the UI
animates; (b) its duration, sanitised input/output summaries and errors are
appended to `execution_trace`; (c) an exception in a non-critical node becomes a
recorded failure instead of crashing the request.
"""

from __future__ import annotations

import functools
import logging
import time
import traceback
from datetime import UTC, datetime
from typing import Callable

from langgraph.config import get_stream_writer

log = logging.getLogger(__name__)

NODE_INFO: dict[str, dict] = {
    "input_validation": {"label": "Input validation", "role": "Sanitise the question, enforce limits, flag injection attempts."},
    "session_context": {"label": "Session memory", "role": "Load prior turns and references for follow-up resolution."},
    "intent": {"label": "Intent agent", "role": "Interpret the question into a typed intent (Gemini, or rules fallback)."},
    "supervisor": {"label": "Supervisor / planner", "role": "Resolve references and date window; choose registered operations and agents."},
    "topic_agent": {"label": "Topic agent", "role": "Topic frequency, negative-topic ranking and topic comparisons."},
    "sentiment_agent": {"label": "Sentiment agent", "role": "Sentiment distribution, trends and conversation trajectories."},
    "coaching_agent": {"label": "Coaching agent", "role": "Agent communication signals with sample-size safeguards."},
    "leadership_agent": {"label": "Leadership agent", "role": "Transparent prioritisation of recurring concerns and recommendations."},
    "analytics_agent": {"label": "Analytics agent", "role": "Dataset coverage, conversation detail and re-running prior analyses."},
    "retrieval": {"label": "Retrieval agent", "role": "Semantic search over the FAISS index with metadata filters."},
    "evidence": {"label": "Evidence assembly", "role": "Resolve cited IDs to source messages and validate them."},
    "explanation": {"label": "Explanation agent", "role": "Grounded narrative (Gemini with numeric check, or deterministic)."},
    "visualization": {"label": "Visualization planner", "role": "Choose charts and build validated specs from results."},
    "qa": {"label": "QA agent", "role": "Check filters, denominators, rankings, charts, citations and grounding."},
    "governance": {"label": "Governance agent", "role": "PII, coaching safeguards, dataset authorisation, audit."},
    "response": {"label": "Response assembly", "role": "Build the unified, versioned response contract."},
    "memory_telemetry": {"label": "Memory + telemetry", "role": "Persist session references and execution telemetry."},
}


def _emit(event: dict) -> None:
    try:
        get_stream_writer()(event)
    except Exception:  # noqa: BLE001 - not running under a stream (e.g. invoke) is fine
        pass


def traced(name: str, critical: bool = False, summarize_input: Callable[[dict], dict] | None = None,
           summarize_output: Callable[[dict], dict] | None = None):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            started = datetime.now(UTC).isoformat()
            _emit({"type": "node_start", "node": name, "label": NODE_INFO[name]["label"], "at": started})
            t0 = time.perf_counter()
            in_summary = summarize_input(state) if summarize_input else {}
            try:
                update = fn(state) or {}
                status = update.pop("_status", "completed")
                meta = update.pop("_meta", {})
                error = None
            except Exception as e:  # noqa: BLE001
                log.exception("Node %s failed", name)
                if critical:
                    _emit({"type": "node_end", "node": name, "status": "failed", "error": str(e)[:300],
                           "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})
                    raise
                update, status, meta, error = {}, "failed", {"traceback": traceback.format_exc(limit=3)[-600:]}, f"{type(e).__name__}: {str(e)[:300]}"
            duration = round((time.perf_counter() - t0) * 1000, 1)
            out_summary = summarize_output(update) if (summarize_output and status != "failed") else {}
            ev = {"node": name, "label": NODE_INFO[name]["label"], "status": status, "started_at": started,
                  "finished_at": datetime.now(UTC).isoformat(), "duration_ms": duration, "retries": meta.pop("retries", 0) if isinstance(meta, dict) else 0,
                  "input_summary": in_summary, "output_summary": out_summary, "error": error, "meta": meta}
            _emit({"type": "node_end", **{k: ev[k] for k in ("node", "label", "status", "duration_ms", "error", "output_summary", "meta")}})
            update["execution_trace"] = [ev]
            if error:
                update["errors"] = [{"node": name, "error": error}]
            return update

        return wrapper

    return deco
