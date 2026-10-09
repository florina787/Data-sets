"""Enforceable guardrails for agentic workflows.

These are working primitives (used by ArchAI's own LangGraph workflow for its
challenger loop, and recommended for any agent ArchAI proposes):

* iteration limits, token budgets and wall-clock timeouts (:class:`AgentBudget`)
* tool allow-listing, parameter schema validation and approval gates
  (:func:`validate_tool_call`)
* indirect prompt-injection screening of retrieved content
  (:func:`screen_retrieved_content`)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError


class GuardrailViolation(RuntimeError):
    """Base class for guardrail breaches."""


class IterationLimitExceeded(GuardrailViolation):
    pass


class TokenBudgetExceeded(GuardrailViolation):
    pass


class AgentTimeout(GuardrailViolation):
    pass


@dataclass(frozen=True)
class GuardrailConfig:
    max_iterations: int = 8
    max_total_tokens: int = 60_000
    timeout_seconds: float = 120.0
    tool_allowlist: frozenset[str] = frozenset()
    approval_required_tools: frozenset[str] = frozenset()

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_total_tokens": self.max_total_tokens,
            "timeout_seconds": self.timeout_seconds,
            "tool_allowlist": sorted(self.tool_allowlist),
            "approval_required_tools": sorted(self.approval_required_tools),
        }


@dataclass
class AgentBudget:
    """Tracks an agent run and raises as soon as any limit is breached."""

    config: GuardrailConfig
    iterations: int = 0
    tokens_used: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def step(self, tokens: int = 0) -> None:
        """Record one iteration; raise if a limit is exceeded."""
        self.iterations += 1
        self.tokens_used += max(tokens, 0)
        if self.iterations > self.config.max_iterations:
            raise IterationLimitExceeded(
                f"Agent exceeded max_iterations={self.config.max_iterations}; halting to prevent an infinite loop."
            )
        if self.tokens_used > self.config.max_total_tokens:
            raise TokenBudgetExceeded(f"Token budget {self.config.max_total_tokens} exceeded ({self.tokens_used}).")
        if time.monotonic() - self.started_at > self.config.timeout_seconds:
            raise AgentTimeout(f"Agent exceeded timeout of {self.config.timeout_seconds}s.")

    @property
    def remaining_iterations(self) -> int:
        return max(self.config.max_iterations - self.iterations, 0)


@dataclass(frozen=True)
class ToolCallDecision:
    allowed: bool
    requires_approval: bool
    reason: str


def validate_tool_call(
    config: GuardrailConfig,
    tool_name: str,
    params: dict[str, Any],
    schema: type[BaseModel] | None = None,
) -> ToolCallDecision:
    """Decide whether an agent-proposed tool call may proceed."""
    if tool_name not in config.tool_allowlist:
        return ToolCallDecision(False, False, f"Tool '{tool_name}' is not on the allow-list.")
    if schema is not None:
        try:
            schema.model_validate(params)
        except ValidationError as exc:
            return ToolCallDecision(False, False, f"Parameters failed schema validation ({exc.error_count()} errors); possible hallucinated arguments.")
    if tool_name in config.approval_required_tools:
        return ToolCallDecision(True, True, f"Tool '{tool_name}' performs a write; human approval required before execution.")
    return ToolCallDecision(True, False, "Allowed (read-only, allow-listed, schema-valid).")


_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all|any|the)? ?(previous|prior|above) instructions",
        r"disregard (the )?(system|previous) prompt",
        r"you are now",
        r"reveal (your|the) (system prompt|instructions|secrets?)",
        r"exfiltrate|send (this|the data) to http",
        r"<\s*/?\s*system\s*>",
    )
]


def screen_retrieved_content(text: str) -> list[str]:
    """Return matched indirect prompt-injection indicators in retrieved content."""
    return [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]


def default_guardrails(*, agentic: bool, regulated: bool, write_tools: list[str], read_tools: list[str]) -> GuardrailConfig:
    """Conservative defaults scaled to the workload's risk."""
    return GuardrailConfig(
        max_iterations=6 if regulated else 10,
        max_total_tokens=40_000 if regulated else 80_000,
        timeout_seconds=90.0 if regulated else 180.0,
        tool_allowlist=frozenset(read_tools + write_tools) if agentic else frozenset(read_tools),
        approval_required_tools=frozenset(write_tools),
    )
