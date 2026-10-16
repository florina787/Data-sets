"""OpenTelemetry + LangSmith wiring with privacy-first defaults.

* OpenTelemetry spans are created for HTTP requests and every agent node. Span
  attributes only carry identifiers and redacted summaries.
* LangSmith tracing is OFF unless LANGSMITH_TRACING=true and an API key is set.
  Even then, inputs/outputs pass through ``redact`` before export unless
  ``LANGSMITH_ALLOW_RAW_PAYLOADS`` is set (rejected in staging/production).
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import lru_cache
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from app.config.settings import get_settings
from app.security.guards import redact

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_configured = False


def setup_tracing() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    if s.otel_enabled:
        provider = TracerProvider(resource=Resource.create({"service.name": "medaccess-backend",
                                                            "deployment.environment": s.environment}))
        if s.otel_console_export:
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
    _configured = True


def tracer():
    return trace.get_tracer("medaccess")


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None


def _hide(payload: Any) -> Any:
    if get_settings().langsmith_allow_raw_payloads:
        return payload
    return redact(payload)


@lru_cache
def langsmith_client():
    """Return a LangSmith client configured with redaction hooks, or None if not configured."""
    s = get_settings()
    if not s.langsmith_configured:
        return None
    from langsmith import Client

    return Client(api_key=s.langsmith_api_key.get_secret_value(), hide_inputs=_hide, hide_outputs=_hide)


def langchain_callbacks(workflow_id: str) -> list:
    client = langsmith_client()
    if client is None:
        return []
    from langchain_core.tracers.langchain import LangChainTracer

    return [LangChainTracer(client=client, project_name=get_settings().langsmith_project,
                            tags=["medaccess", f"workflow:{workflow_id}"])]


def status() -> dict:
    s = get_settings()
    return {"opentelemetry": {"enabled": s.otel_enabled, "console_export": s.otel_console_export},
            "langsmith": {"configured": s.langsmith_configured, "project": s.langsmith_project,
                          "raw_payloads": s.langsmith_allow_raw_payloads,
                          "redaction": "enabled" if not s.langsmith_allow_raw_payloads else "DISABLED"}}
