"""Copilot service: runs the LangGraph workflow for a question and records the trace.

This is the single entry point used by the API; it contains no agent logic.
"""

from __future__ import annotations

import logging
import time
import uuid

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.graph.state import CopilotState
from app.models.api import ChatResponse, TokenUsageOut
from app.models.domain import AGENT_LABELS, AgentName, GuardrailReport, Intent, TokenUsage
from app.observability.tracing import RequestTrace, ToolCallTrace, TraceStore

logger = logging.getLogger(__name__)


class CopilotError(RuntimeError):
    """Raised when the workflow fails unrecoverably; carries the request ID."""

    def __init__(self, message: str, request_id: str) -> None:
        super().__init__(message)
        self.request_id = request_id


def build_route(execution_path: list[str]) -> list[str]:
    """Human-friendly route, e.g. Supervisor → RAG → Analysis → Response → Guardrail."""
    route: list[str] = []
    for node in execution_path:
        label = AGENT_LABELS.get(node, node)
        if node == AgentName.SUPERVISOR.value and route:
            continue  # the supervisor is revisited between specialists; show it once
        route.append(label)
    return route


class CopilotService:
    """Application service wrapping the compiled graph."""

    def __init__(self, graph: CompiledStateGraph, traces: TraceStore, mode: str) -> None:
        self._graph = graph
        self._traces = traces
        self._mode = mode

    def ask(self, question: str, top_k: int | None = None) -> ChatResponse:
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        initial: CopilotState = {
            "request_id": request_id,
            "user_query": question,
            "messages": [HumanMessage(content=question)],
            "retrieved_documents": [],
            "tool_results": [],
            "analysis": None,
            "citations": [],
        }
        if top_k:
            initial["top_k"] = top_k
        config = {
            "run_name": "enterprise_copilot_request",
            "tags": ["enterprise-copilot", self._mode],
            "metadata": {"request_id": request_id, "mode": self._mode},
            "recursion_limit": 20,
        }
        trace = RequestTrace(request_id=request_id, mode=self._mode, question_preview=question[:120])
        try:
            state: CopilotState = self._graph.invoke(initial, config=config)
        except Exception as exc:
            trace.latency_ms = round((time.perf_counter() - start) * 1000, 1)
            trace.status = "error"
            trace.errors.append(f"graph: {type(exc).__name__}: {exc}")
            self._traces.record(trace)
            logger.exception("Workflow failed (request_id=%s)", request_id)
            raise CopilotError("The copilot workflow failed.", request_id) from exc

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        usage: TokenUsage = state.get("token_usage") or TokenUsage()
        steps = state.get("agent_steps", [])
        path = state.get("execution_path", [])
        intent: Intent = state.get("intent", Intent.GENERAL_QA)
        errors = list(state.get("errors", []))
        answer = state.get("final_answer") or state.get("draft_answer") or (
            "The copilot could not produce an answer. More information is required."
        )

        node_latency: dict[str, float] = {}
        for step in steps:
            node_latency[step.agent] = round(node_latency.get(step.agent, 0.0) + step.duration_ms, 2)
        tool_results = state.get("tool_results", [])
        trace.intent = intent.value
        trace.agents_invoked = sorted(set(path), key=path.index)
        trace.execution_path = path
        trace.node_latency_ms = node_latency
        trace.tool_calls = [
            ToolCallTrace(tool_name=r.tool_name, success=r.success, duration_ms=r.duration_ms, error=r.error)
            for r in tool_results
        ]
        trace.retrieval_count = len(state.get("retrieved_documents", []))
        trace.latency_ms = latency_ms
        trace.input_tokens, trace.output_tokens = usage.input_tokens, usage.output_tokens
        trace.llm_calls, trace.tokens_estimated = usage.llm_calls, usage.estimated
        trace.confidence = state.get("confidence")
        trace.errors = errors
        trace.status = "ok" if "final_answer" in state else "degraded"
        self._traces.record(trace)

        return ChatResponse(
            request_id=request_id,
            mode=self._mode,
            answer=answer,
            intent=intent.value,
            intent_reasoning=state.get("intent_reasoning", ""),
            route=build_route(path),
            execution_path=path,
            agent_steps=steps,
            citations=state.get("citations", []),
            retrieved_chunks=state.get("retrieved_documents", []),
            tool_calls=tool_results,
            analysis=state.get("analysis"),
            guardrail=state.get("guardrail") or GuardrailReport(passed=False, issues=["Guardrail did not run."]),
            confidence=float(state.get("confidence", 0.0)),
            latency_ms=latency_ms,
            token_usage=TokenUsageOut(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                llm_calls=usage.llm_calls,
                estimated=usage.estimated and usage.llm_calls == 0,
            ),
            errors=errors,
        )
