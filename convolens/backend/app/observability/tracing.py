"""LangSmith integration. Off unless LANGSMITH_TRACING=true and LANGSMITH_API_KEY are set.

Payloads are scrubbed with the same redactor used at ingestion before they leave the process
(stored text is already redacted; this is defence in depth). Raw text is never available to send.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings
from app.security.redaction import scrub_for_trace

log = logging.getLogger(__name__)


def status() -> dict:
    s = get_settings()
    if not s.langsmith_configured:
        missing = [n for n, ok in (("LANGSMITH_TRACING=true", s.langsmith_tracing),
                                   ("LANGSMITH_API_KEY", bool(s.langsmith_api_key))) if not ok]
        return {"configured": False, "label": "LangSmith not configured", "missing": missing, "project": None}
    return {"configured": True, "label": "LangSmith tracing enabled", "project": s.langsmith_project,
            "redaction": "scrub_for_trace on inputs and outputs" + ("" if not s.langsmith_send_raw else " (raw sending flag set, but raw text is never stored)")}


@lru_cache(maxsize=1)
def client():
    s = get_settings()
    if not s.langsmith_configured:
        return None
    from langsmith import Client
    hide = None if s.langsmith_send_raw else scrub_for_trace
    return Client(api_key=s.langsmith_api_key.get_secret_value(), api_url=s.langsmith_endpoint,
                  hide_inputs=hide or (lambda x: x), hide_outputs=hide or (lambda x: x))


def tracer():
    c = client()
    if c is None:
        return None
    from langchain_core.tracers import LangChainTracer
    return LangChainTracer(project_name=get_settings().langsmith_project, client=c)


def trace_url(run_id: str) -> str | None:
    c = client()
    if c is None:
        return None
    try:
        run = c.read_run(run_id)
        return c.get_run_url(run=run, project_name=get_settings().langsmith_project)
    except Exception as exc:  # run may not be flushed yet
        log.info("Trace link unavailable: %s", exc)
        return None


def send_feedback(run_id: str, score: int, comment: str | None) -> bool:
    c = client()
    if c is None:
        return False
    try:
        c.create_feedback(run_id=run_id, key="user_helpfulness", score=score, comment=scrub_for_trace(comment) if comment else None)
        return True
    except Exception as exc:
        log.warning("LangSmith feedback failed: %s", exc)
        return False


def flush() -> None:
    c = client()
    if c is not None:
        try:
            c.flush()
        except Exception:
            pass
