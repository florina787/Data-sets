"""Allow-listed tool registry for agents (least privilege, budgets, audit).

* Every tool declares which agents may call it (allowlist).
* Consequential tools (deploy, reprocess, modify production) require an explicit human
  approval token and are NOT allow-listed for any agent.
* Calls are counted against MAX_TOOL_CALLS per agent run and audited.
* Optional Pydantic input models validate parameters (no hallucinated arguments).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from app.observability.audit import AuditLog


class ToolError(RuntimeError):
    pass


class ToolNotAllowedError(ToolError):
    pass


class ToolBudgetExceededError(ToolError):
    pass


class ApprovalRequiredError(ToolError):
    pass


class AgentTimeoutError(ToolError):
    pass


@dataclass
class ToolSpec:
    name: str
    func: Callable[..., Any]
    allowed_agents: frozenset[str]
    description: str
    consequential: bool = False
    input_model: type[BaseModel] | None = None


@dataclass
class ToolBudget:
    """Per agent-run budget: tool calls and wall-clock timeout."""

    max_calls: int
    timeout_s: float
    calls: int = 0
    started: float = field(default_factory=time.monotonic)
    log: list[dict] = field(default_factory=list)

    def check_time(self) -> None:
        if time.monotonic() - self.started > self.timeout_s:
            raise AgentTimeoutError(f"agent exceeded timeout of {self.timeout_s}s")


class ToolRegistry:
    def __init__(self, audit: AuditLog) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.audit = audit

    def register(self, spec: ToolSpec) -> None:
        if spec.consequential and spec.allowed_agents:
            raise ValueError("consequential tools may not be allow-listed for agents")
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict]:
        return [{"name": t.name, "allowed_agents": sorted(t.allowed_agents), "consequential": t.consequential,
                 "description": t.description} for t in sorted(self._tools.values(), key=lambda t: t.name)]

    def call(self, agent: str, name: str, budget: ToolBudget, *, request_id: str | None = None,
             approval_token: str | None = None, **kwargs) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolNotAllowedError(f"unknown tool '{name}'")
        if spec.consequential and not approval_token:
            self.audit.record(agent, "tool_denied_requires_approval", request_id, tool=name)
            raise ApprovalRequiredError(f"tool '{name}' is consequential and requires human approval")
        if not spec.consequential and agent not in spec.allowed_agents:
            self.audit.record(agent, "tool_denied_not_allowlisted", request_id, tool=name)
            raise ToolNotAllowedError(f"agent '{agent}' is not allowed to call '{name}'")
        if budget.calls >= budget.max_calls:
            raise ToolBudgetExceededError(f"MAX_TOOL_CALLS={budget.max_calls} exceeded by {agent}")
        budget.check_time()
        if spec.input_model is not None:
            try:
                validated = spec.input_model(**{k: v for k, v in kwargs.items() if k in spec.input_model.model_fields})
            except ValidationError as exc:
                raise ToolError(f"invalid parameters for '{name}': {exc.errors()[:2]}") from exc
            kwargs.update(validated.model_dump())
        budget.calls += 1
        t0 = time.perf_counter()
        out = spec.func(**kwargs)
        ms = round((time.perf_counter() - t0) * 1000, 2)
        budget.log.append({"tool": name, "latency_ms": ms})
        self.audit.record(agent, "tool_call", request_id, tool=name, latency_ms=ms)
        return out
