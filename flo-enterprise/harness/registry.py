"""Agent registry (plugin-style). Every agent registers a complete contract before it can run."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel


@dataclass(frozen=True)
class AgentSpec:
    name: str
    version: str
    owner: str
    domain: str
    supervisor: str
    description: str
    allowed_roles: frozenset[str]
    allowed_tools: tuple[str, ...]
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    max_iterations: int = 8
    max_tokens: int = 20_000
    max_cost_usd: float = 0.50
    timeout_s: float = 15.0
    max_retries: int = 2
    data_classification: str = "internal"
    approval_actions: tuple[str, ...] = ()
    eval_requirements: tuple[str, ...] = ("numeric_grounding",)

    def contract(self) -> dict:
        return {"name": self.name, "version": self.version, "owner": self.owner, "domain": self.domain, "supervisor": self.supervisor,
                "description": self.description, "allowed_roles": sorted(self.allowed_roles), "allowed_tools": list(self.allowed_tools),
                "input_schema": self.input_model.model_json_schema(), "output_schema": self.output_model.model_json_schema(),
                "budget": {"max_iterations": self.max_iterations, "max_tokens": self.max_tokens, "max_cost_usd": self.max_cost_usd,
                           "timeout_s": self.timeout_s, "max_retries": self.max_retries},
                "data_classification": self.data_classification, "approval_requirements": list(self.approval_actions),
                "evaluation_requirements": list(self.eval_requirements)}


@dataclass
class RegisteredAgent:
    spec: AgentSpec
    run: Callable  # (ctx, input_model) -> output_model


@dataclass
class AgentRegistry:
    agents: dict[str, RegisteredAgent] = field(default_factory=dict)

    def register(self, spec: AgentSpec):
        def deco(fn):
            if spec.name in self.agents:
                raise ValueError(f"agent {spec.name} already registered")
            self.agents[spec.name] = RegisteredAgent(spec, fn)
            return fn
        return deco

    def get(self, name: str) -> RegisteredAgent:
        if name not in self.agents:
            raise KeyError(f"unknown agent {name}")
        return self.agents[name]

    def by_domain(self, domain: str) -> list[AgentSpec]:
        return [a.spec for a in self.agents.values() if a.spec.domain == domain]


REGISTRY = AgentRegistry()
