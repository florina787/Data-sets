"""Privacy-safe LLM/agent observability.

LocalTelemetry (always on) persists one AgentTrace row per agent execution and updates Prometheus metrics.
LangSmithTelemetry additionally sends a run to LangSmith when LANGSMITH_API_KEY is configured. Inputs/outputs are
passed through privacy redaction BEFORE leaving the process; only ids, metrics and redacted text are transmitted.
Without credentials FLO reports `mode = "local-fallback"` (no external calls)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram

from backend.config import get_settings
from backend.db import models as m
from backend.db.session import session_scope
from privacy.detect import redact_structure

log = logging.getLogger("flo.telemetry")

AGENT_RUNS = Counter("flo_agent_runs_total", "Agent executions", ["agent", "status", "failure_class"])
AGENT_LATENCY = Histogram("flo_agent_latency_seconds", "Agent execution latency", ["agent"],
                          buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20))
TOOL_CALLS = Counter("flo_tool_calls_total", "Tool gateway invocations", ["tool", "decision"])
POLICY_DECISIONS = Counter("flo_policy_decisions_total", "Policy decisions", ["action", "allowed"])
TOKENS = Counter("flo_llm_tokens_total", "Estimated LLM tokens", ["direction", "model"])
COST = Counter("flo_llm_cost_usd_total", "Estimated LLM cost (USD)", ["model"])
ACTIVE_WORKFLOWS = Gauge("flo_active_workflows", "Workflows currently executing")
QUEUE_DEPTH = Gauge("flo_job_queue_depth", "Pending background jobs")
HTTP_LATENCY = Histogram("flo_http_request_seconds", "HTTP latency", ["route", "method", "status"],
                         buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5))


class LocalTelemetry:
    mode = "local-fallback"

    def record_agent(self, *, ctx, agent: str, version: str, model: str, started: datetime, latency_ms: int, tokens_in: int,
                     tokens_out: int, cost: float, status: str, failure_class: str | None, retries: int, tool_calls: list,
                     eval_score: float | None, approval_status: str | None, policy_outcome: str, cache_hit: bool,
                     inputs: dict | None = None, outputs: dict | None = None) -> str:
        tid = f"TR-{uuid.uuid4().hex[:16]}"
        with session_scope() as s:
            s.add(m.AgentTrace(id=tid, tenant_id=ctx.principal.tenant_id, user_id=ctx.principal.user_id, workflow_id=ctx.workflow_id,
                               workflow_type=ctx.workflow_type, agent_id=agent, agent_version=version, model=model,
                               started_at=started.replace(tzinfo=None), latency_ms=latency_ms, tokens_in=tokens_in, tokens_out=tokens_out,
                               cost_usd=round(cost, 6), status=status, failure_class=failure_class, retry_count=retries,
                               eval_score=eval_score, tool_calls=redact_structure(tool_calls), approval_status=approval_status,
                               policy_outcome=policy_outcome, cache_hit=cache_hit, synthetic=False))
        AGENT_RUNS.labels(agent, status, failure_class or "none").inc()
        AGENT_LATENCY.labels(agent).observe(latency_ms / 1000)
        TOKENS.labels("in", model).inc(tokens_in)
        TOKENS.labels("out", model).inc(tokens_out)
        COST.labels(model).inc(cost)
        return tid


class LangSmithTelemetry(LocalTelemetry):
    mode = "langsmith"

    def __init__(self):
        from langsmith import Client
        s = get_settings()
        self.client = Client(api_key=s.langsmith_api_key)
        self.project = s.langsmith_project

    def record_agent(self, **kw) -> str:
        tid = super().record_agent(**kw)
        try:
            ctx = kw["ctx"]
            self.client.create_run(
                name=kw["agent"], run_type="chain", project_name=self.project, id=uuid.uuid4(),
                inputs=redact_structure(kw.get("inputs") or {}), outputs=redact_structure(kw.get("outputs") or {}),
                start_time=kw["started"], end_time=datetime.now(timezone.utc), error=kw["failure_class"],
                extra={"metadata": {"workflow_id": ctx.workflow_id, "agent_version": kw["version"], "model": kw["model"],
                                    "tokens_in": kw["tokens_in"], "tokens_out": kw["tokens_out"], "cost_usd": kw["cost"],
                                    "retries": kw["retries"], "policy_outcome": kw["policy_outcome"], "trace_id": tid,
                                    "tenant": ctx.principal.tenant_id}})  # user ids/names are not sent
        except Exception as e:  # noqa: BLE001 - telemetry must never break a workflow
            log.warning("langsmith export failed: %s", e.__class__.__name__)
        return tid


_tel = None


def get_telemetry() -> LocalTelemetry:
    global _tel
    if _tel is None:
        _tel = LangSmithTelemetry() if get_settings().langsmith_api_key else LocalTelemetry()
    return _tel
