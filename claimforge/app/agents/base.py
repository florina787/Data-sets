"""Agent base class and shared context.

ClaimForge agents are *orchestrators and explainers*. In DEMO_MODE their reasoning
steps are deterministic planners/templates (labelled as such); in live mode an LLM may
enhance narratives only. Agents call deterministic engines through allow-listed tools.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.config.settings import Settings
from app.llm.client import LLMClient
from app.observability.audit import AuditLog, MetricsRegistry
from app.policies.knowledge_base import PolicyKnowledgeBase
from app.policies.retrieval import BM25Retriever
from app.tools.registry import ToolBudget, ToolRegistry
from app.traceability.graph import TraceabilityGraph


@dataclass
class AgentContext:
    settings: Settings
    llm: LLMClient
    tools: ToolRegistry
    audit: AuditLog
    metrics: MetricsRegistry
    kb: PolicyKnowledgeBase
    retriever: BM25Retriever
    trace_graph: TraceabilityGraph
    releases: dict
    requirements_catalog: list[dict]
    extras: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    name: str = "base"
    title: str = "Agent"
    implementation: str = "DETERMINISTIC planner + templates (DEMO); LLM-assisted narrative in live mode"

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx

    def budget(self) -> ToolBudget:
        s = self.ctx.settings
        return ToolBudget(max_calls=s.max_tool_calls, timeout_s=s.agent_timeout_seconds)

    def narrate(self, task: str, facts: str, fallback: str) -> dict:
        res = self.ctx.llm.narrate(task, facts, fallback)
        return {"text": res.text, "source": res.source}

    def invoke(self, state: dict) -> dict:
        """Run the agent with metrics + audit. Subclasses implement :meth:`run`."""
        t0 = time.perf_counter()
        self.ctx.audit.record(self.name, "agent_start", state.get("request_id"))
        out = self.run(state)
        ms = (time.perf_counter() - t0) * 1000
        self.ctx.metrics.inc(f"agent.{self.name}.invocations")
        self.ctx.metrics.observe(f"agent.{self.name}", ms)
        self.ctx.audit.record(self.name, "agent_end", state.get("request_id"), latency_ms=round(ms, 1))
        return out

    def run(self, state: dict) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError
