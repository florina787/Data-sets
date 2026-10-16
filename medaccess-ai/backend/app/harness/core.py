"""Agent execution harness.

Provides agent and tool registration, permission enforcement (tool allowlists +
role permissions), budgets (graph steps, tool calls, wall-clock, tokens), bounded
retries with exponential backoff, per-tool circuit breakers, typed input/output
validation, untrusted-output sanitisation, approval enforcement for side-effecting
tools, telemetry, trace correlation and persisted execution records.

New agents/tools are added by registering an ``AgentSpec`` / ``ToolSpec``; the
orchestration graphs do not need to change.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config.settings import get_settings
from app.security.guards import redact, sanitize_untrusted
from app.telemetry import metrics as tm

HARNESS_VERSION = "1.2.0"


# ----------------------------------------------------------------------------- errors
class HarnessError(Exception):
    code = "HARNESS_ERROR"


class BudgetExceeded(HarnessError):
    code = "BUDGET_EXCEEDED"


class ToolNotAllowed(HarnessError):
    code = "TOOL_NOT_ALLOWED"


class ApprovalRequired(HarnessError):
    code = "APPROVAL_REQUIRED"


class CircuitOpen(HarnessError):
    code = "CIRCUIT_OPEN"


class ToolContractError(HarnessError):
    code = "TOOL_CONTRACT_VIOLATION"


class TransientToolError(Exception):
    """Retryable failure (timeouts, rate limits, provider outages)."""


class ProviderUnavailableError(TransientToolError):
    pass


class RateLimitedError(TransientToolError):
    pass


# ----------------------------------------------------------------------------- registries
@dataclass
class AgentSpec:
    name: str
    title: str
    description: str
    workflow: str  # patient | sdlc
    allowed_tools: set[str] = field(default_factory=set)
    uses_llm: bool = False
    version: str = "1.0.0"
    prompt_version: str | None = None
    max_retries: int | None = None
    timeout_s: float = 5.0


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., BaseModel]
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    permission: str | None = None  # role permission required
    side_effect: bool = False  # requires an approval reference
    untrusted_output: bool = False  # external data -> sanitise
    timeout_s: float = 3.0
    mcp_server: str | None = None
    version: str = "1.0.0"


AGENTS: dict[str, AgentSpec] = {}
TOOLS: dict[str, ToolSpec] = {}


def register_agent(spec: AgentSpec) -> AgentSpec:
    AGENTS[spec.name] = spec
    return spec


def register_tool(spec: ToolSpec) -> ToolSpec:
    TOOLS[spec.name] = spec
    return spec


# ----------------------------------------------------------------------------- circuit breaker
class CircuitBreaker:
    def __init__(self, threshold: int, reset_s: float) -> None:
        self.threshold, self.reset_s = threshold, reset_s
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if time.monotonic() - self.opened_at >= self.reset_s else "open"

    def allow(self) -> bool:
        return self.state != "open"

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold or self.state == "half_open":
            self.opened_at = time.monotonic()


_BREAKERS: dict[str, CircuitBreaker] = {}


def breaker(key: str) -> CircuitBreaker:
    s = get_settings()
    if key not in _BREAKERS:
        _BREAKERS[key] = CircuitBreaker(s.circuit_failure_threshold, s.circuit_reset_seconds)
    return _BREAKERS[key]


def breaker_states() -> dict[str, dict]:
    return {k: {"state": b.state, "failures": b.failures} for k, b in _BREAKERS.items()}


def reset_breakers() -> None:
    _BREAKERS.clear()


# ----------------------------------------------------------------------------- run context
@dataclass
class RunContext:
    workflow_id: str
    workflow_type: str = "patient"
    user_id: str | None = None
    role: str = "patient"
    permissions: set[str] = field(default_factory=set)
    scenario: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tool_calls: int = 0
    tokens: int = 0
    approvals: set[str] = field(default_factory=set)  # approved approval ids usable by side-effect tools
    tool_log: list[dict] = field(default_factory=list)
    security_events: list[dict] = field(default_factory=list)
    persist: bool = True
    now: Any = None  # fixed clock for reproducible runs (datetime, UTC)
    dataset: Any = None  # SyntheticDataset snapshot used by synthetic adapters
    build_version: str = "1.4.0"
    status_mapping: str = "correct"
    free_text: str | None = None  # transient patient text for safety screening (never checkpointed)

    def __post_init__(self) -> None:
        s = get_settings()
        self.max_steps = s.max_graph_steps
        self.max_seconds = s.max_workflow_seconds
        self.max_tool_calls = s.max_tool_calls
        self.max_tokens = s.llm_max_tokens_per_workflow

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def step(self, agent: str) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise BudgetExceeded(f"max graph steps ({self.max_steps}) exceeded at {agent}")
        if self.elapsed() > self.max_seconds:
            raise BudgetExceeded(f"max workflow duration ({self.max_seconds}s) exceeded at {agent}")

    def charge_tokens(self, n: int) -> None:
        if self.tokens + n > self.max_tokens:
            raise BudgetExceeded(f"token budget ({self.max_tokens}) exceeded")
        self.tokens += n


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ----------------------------------------------------------------------------- tool invocation
def call_tool(ctx: RunContext, agent: str, tool_name: str, payload: dict[str, Any] | BaseModel,
              approval_id: str | None = None, retry_key: str | None = None) -> Any:
    """Invoke a registered tool on behalf of an agent with all harness controls applied."""
    spec_agent = AGENTS.get(agent)
    spec = TOOLS.get(tool_name)
    if spec is None:
        raise ToolNotAllowed(f"unknown tool {tool_name}")
    if spec_agent is None or tool_name not in spec_agent.allowed_tools:
        ctx.security_events.append({"type": "TOOL_NOT_ALLOWED", "agent": agent, "tool": tool_name})
        raise ToolNotAllowed(f"agent {agent} is not allowed to call {tool_name}")
    if spec.permission and spec.permission not in ctx.permissions:
        ctx.security_events.append({"type": "PERMISSION_DENIED", "agent": agent, "tool": tool_name})
        raise ToolNotAllowed(f"role {ctx.role} lacks permission {spec.permission} for {tool_name}")
    if spec.side_effect and (approval_id is None or approval_id not in ctx.approvals):
        ctx.security_events.append({"type": "APPROVAL_MISSING", "agent": agent, "tool": tool_name})
        raise ApprovalRequired(f"{tool_name} has side effects and requires an approved approval request")
    if ctx.tool_calls >= ctx.max_tool_calls:
        raise BudgetExceeded(f"max tool calls ({ctx.max_tool_calls}) exceeded")
    try:
        args = payload if isinstance(payload, spec.input_model) else spec.input_model.model_validate(
            payload.model_dump() if isinstance(payload, BaseModel) else payload)
    except ValidationError as e:
        raise ToolContractError(f"invalid input for {tool_name}: {e.errors()[:2]}") from e

    br = breaker(retry_key or tool_name)
    s = get_settings()
    max_retries = spec_agent.max_retries if spec_agent.max_retries is not None else s.max_retries
    attempt = 0
    while True:
        attempt += 1
        if not br.allow():
            _log(ctx, agent, tool_name, "circuit_open", 0.0, attempt, "circuit open")
            raise CircuitOpen(f"circuit open for {retry_key or tool_name}")
        ctx.tool_calls += 1
        t0 = time.perf_counter()
        try:
            out = spec.fn(args, ctx)
            dur = (time.perf_counter() - t0) * 1000
            if dur > spec.timeout_s * 1000:
                raise TransientToolError(f"{tool_name} exceeded timeout {spec.timeout_s}s")
            if not isinstance(out, spec.output_model):
                out = spec.output_model.model_validate(out)
            if spec.untrusted_output:
                clean, findings = sanitize_untrusted(out.model_dump(mode="json"))
                if findings:
                    ctx.security_events.append({"type": "PROMPT_INJECTION_IN_TOOL_OUTPUT", "tool": tool_name,
                                                "patterns": findings[:3]})
                    out = spec.output_model.model_validate(clean)
            br.success()
            _log(ctx, agent, tool_name, "ok", dur, attempt)
            return out
        except TransientToolError as e:
            dur = (time.perf_counter() - t0) * 1000
            br.failure()
            _log(ctx, agent, tool_name, "error", dur, attempt, str(e))
            if attempt > max_retries or not br.allow():
                raise
            tm.RETRIES.labels(component=tool_name).inc()
            tm.STORE.add("retries", 1, {"tool": tool_name})
            time.sleep(min(2.0, s.retry_base_delay_s * (2 ** (attempt - 1))))
        except ValidationError as e:
            _log(ctx, agent, tool_name, "contract_violation", (time.perf_counter() - t0) * 1000, attempt, str(e)[:200])
            raise ToolContractError(f"invalid output from {tool_name}") from e


def _log(ctx: RunContext, agent: str, tool: str, status: str, dur: float, attempt: int, err: str | None = None):
    tm.TOOL_CALLS.labels(tool=tool, status=status).inc()
    tm.STORE.add("tool_call", 1 if status == "ok" else 0, {"tool": tool, "status": status})
    ctx.tool_log.append({"agent": agent, "tool": tool, "status": status, "duration_ms": round(dur, 2),
                         "attempt": attempt, "error": redact(err) if err else None})


def registry_snapshot() -> dict:
    return {
        "harness_version": HARNESS_VERSION,
        "agents": [{"name": a.name, "title": a.title, "description": a.description, "workflow": a.workflow,
                    "allowed_tools": sorted(a.allowed_tools), "uses_llm": a.uses_llm, "version": a.version,
                    "prompt_version": a.prompt_version} for a in AGENTS.values()],
        "tools": [{"name": t.name, "description": t.description, "permission": t.permission,
                   "side_effect": t.side_effect, "untrusted_output": t.untrusted_output, "timeout_s": t.timeout_s,
                   "mcp_server": t.mcp_server, "version": t.version,
                   "input_schema": t.input_model.model_json_schema(),
                   "output_schema": t.output_model.model_json_schema()} for t in TOOLS.values()],
        "circuit_breakers": breaker_states(),
    }
