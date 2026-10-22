"""Run context: identity propagation, budgets, cancellation and per-workflow bookkeeping."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from governance.identity import Principal
from governance.policy import PolicyEngine
from harness.errors import BudgetExceeded, Cancelled, ExecutionTimeout
from harness.models import ModelAdapter
from integrations.mock.adapters import Adapters


@dataclass
class Budget:
    max_iterations: int
    max_tokens: int
    max_cost_usd: float
    deadline: float
    iterations: int = 0
    tokens: int = 0
    cost_usd: float = 0.0

    def charge_iteration(self) -> None:
        self.iterations += 1
        if self.iterations > self.max_iterations:
            raise BudgetExceeded(f"iteration budget {self.max_iterations} exceeded")
        if time.monotonic() > self.deadline:
            raise ExecutionTimeout("execution deadline exceeded")

    def charge_tokens(self, tokens: int, cost: float) -> None:
        self.tokens += tokens
        self.cost_usd += cost
        if self.tokens > self.max_tokens:
            raise BudgetExceeded(f"token budget {self.max_tokens} exceeded")
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceeded(f"cost budget {self.max_cost_usd} USD exceeded")


@dataclass
class RunContext:
    principal: Principal
    adapters: Adapters
    engine: PolicyEngine
    model: ModelAdapter
    workflow_type: str = "ask"
    workflow_id: str = field(default_factory=lambda: f"WF-{uuid.uuid4().hex[:12]}")
    language: str = "en"
    purpose: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    budget: Budget | None = None
    agent: Any = None  # current AgentSpec
    tool_log: list[dict] = field(default_factory=list)
    policy_log: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)
    gateway: Any = None
    privacy_scope: str = ""

    def __post_init__(self):
        self.privacy_scope = self.privacy_scope or self.workflow_id

    def fork(self) -> "RunContext":
        """Child context for a parallel branch: shared logs/cancellation, independent agent and budget."""
        from dataclasses import replace
        return replace(self, agent=None, budget=None, privacy_scope=self.privacy_scope)

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled("workflow cancelled by request")

    def tool(self, name: str, **args) -> dict:
        """Agents call tools only through the gateway."""
        return self.gateway.invoke(self, name, args)

    @property
    def service_principal(self) -> Principal:
        p = self.principal
        return Principal(user_id="svc-flo-orchestrator", tenant_id=p.tenant_id, roles=("orchestrator",), clearance="restricted",
                         business_unit="technology", region=p.region)
