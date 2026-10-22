"""Tool registry and the secure tool gateway.

The gateway is the only path from an agent to data or side effects. For every invocation it enforces, in order:
unknown/prohibited tool -> agent allowlist -> argument schema -> policy decision for the *human principal*
(RBAC/ABAC/tenant) -> approval obligations (approval-gated actions can never execute through a tool) ->
rate limit -> budget/cancellation -> circuit breaker + timeout -> output size limit. Every decision is audited.
It rejects unauthorized invocations even when an agent (or a compromised model plan) attempts them."""
from __future__ import annotations

import concurrent.futures as cf
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from governance import audit
from governance.policy import Resource
from harness.errors import (ApprovalRequired, CircuitOpen, HarnessError, InvalidToolArguments, PolicyDenied, ToolNotAllowed,
                            ToolTimeout, UpstreamUnavailable)
from harness.resilience import RateLimiter, breaker
from observability.telemetry import POLICY_DECISIONS, TOOL_CALLS

MAX_OUTPUT_BYTES = 2_000_000
_pool = cf.ThreadPoolExecutor(max_workers=64, thread_name_prefix="flo-tool")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: str
    input_model: type[BaseModel]
    handler: Callable  # (ctx, args_model) -> dict
    resource: Callable | None = None  # (ctx, args_model) -> Resource | None
    upstream: str = "internal"
    timeout_s: float = 8.0
    rate_per_min: int = 600
    side_effect: bool = False
    data_classification: str = "internal"


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> ToolSpec:
        self.tools[spec.name] = spec
        return spec

    def catalog(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "permission": t.permission, "upstream": t.upstream,
                 "side_effect": t.side_effect, "data_classification": t.data_classification,
                 "input_schema": t.input_model.model_json_schema()} for t in self.tools.values()]


TOOLS = ToolRegistry()


class ToolGateway:
    def __init__(self, registry: ToolRegistry = TOOLS):
        self.registry = registry
        self.limiters: dict[str, RateLimiter] = {}

    def _deny(self, ctx, name: str, rule: str, message: str, exc: type[HarnessError], args: dict, reasons: list | None = None):
        entry = {"tool": name, "agent": getattr(ctx.agent, "name", "?"), "decision": "deny", "rule": rule, "message": message}
        ctx.tool_log.append(entry)
        ctx.policy_log.append({"action": f"tool:{name}", "allowed": False, "rule": rule})
        TOOL_CALLS.labels(name, "deny").inc()
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action=f"tool.invoke:{name}", resource_type="tool",
                     resource_id=name, decision="deny", reasons=reasons or [{"rule": rule, "effect": "deny", "message": message}],
                     policy_version=ctx.engine.version, details={"agent": entry["agent"], "workflow_id": ctx.workflow_id,
                                                                 "args": json.dumps(args, default=str)[:500]})
        raise exc(f"{rule}: {message}", code=rule)

    def invoke(self, ctx, name: str, args: dict) -> dict:
        ctx.check_cancel()
        agent = ctx.agent
        spec = self.registry.tools.get(name)
        if spec is None:
            self._deny(ctx, name, "TOOL-UNKNOWN", "tool is not registered", ToolNotAllowed, args)
        if spec.permission in ctx.engine.bundle.rbac.get("prohibited", []):
            self._deny(ctx, name, "PROHIBITED-ACTION", f"{spec.permission} is prohibited", PolicyDenied, args)
        if agent is None or name not in agent.allowed_tools:
            self._deny(ctx, name, "TOOL-NOT-ALLOWLISTED", f"agent {getattr(agent, 'name', '?')} may not call {name}", ToolNotAllowed, args)
        try:
            parsed = spec.input_model.model_validate(args)
        except ValidationError as e:
            self._deny(ctx, name, "INVALID-ARGUMENTS", str(e.errors()[:3]), InvalidToolArguments, args)
        resource: Resource | None = spec.resource(ctx, parsed) if spec.resource else None
        d = ctx.engine.authorize(ctx.principal, spec.permission, resource, {"purpose": ctx.purpose})
        POLICY_DECISIONS.labels(spec.permission, str(d.allowed)).inc()
        if not d.allowed:
            self._deny(ctx, name, ",".join(d.denial_codes), f"policy denied {spec.permission}", PolicyDenied, args, d.reasons)
        if "approval_required" in d.obligations:
            self._deny(ctx, name, "APPROVAL-REQUIRED", f"{spec.permission} requires an approved human review; use request_approval",
                       ApprovalRequired, args)
        lim = self.limiters.setdefault(name, RateLimiter(spec.rate_per_min))
        if not lim.allow(ctx.principal.user_id):
            self._deny(ctx, name, "RATE-LIMITED", "tool rate limit exceeded", PolicyDenied, args)
        ctx.budget.charge_iteration()
        br = breaker(spec.upstream)
        br.before()
        t0 = time.monotonic()
        fut = _pool.submit(spec.handler, ctx, parsed)
        try:
            out = fut.result(timeout=spec.timeout_s)
            br.success()
        except cf.TimeoutError:
            br.failure()
            ctx.tool_log.append({"tool": name, "agent": agent.name, "decision": "allow", "status": "timeout"})
            raise ToolTimeout(f"tool {name} exceeded {spec.timeout_s}s")
        except CircuitOpen:
            raise
        except HarnessError:
            br.failure()
            raise
        except Exception as e:  # upstream failure
            br.failure()
            ctx.tool_log.append({"tool": name, "agent": agent.name, "decision": "allow", "status": "error", "error": e.__class__.__name__})
            raise UpstreamUnavailable(f"{name}: {e.__class__.__name__}: {e}") from e
        size = len(json.dumps(out, default=str))
        if size > MAX_OUTPUT_BYTES:
            raise UpstreamUnavailable(f"tool {name} output too large ({size} bytes)")
        ms = int((time.monotonic() - t0) * 1000)
        ctx.tool_log.append({"tool": name, "agent": agent.name, "decision": "allow", "status": "ok", "latency_ms": ms,
                             "policy_version": d.policy_version, "resource": resource.id if resource else None})
        ctx.policy_log.append({"action": spec.permission, "allowed": True, "resource": resource.id if resource else None})
        TOOL_CALLS.labels(name, "allow").inc()
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action=f"tool.invoke:{name}", resource_type="tool",
                     resource_id=name, decision="allow", reasons=d.reasons[-2:], policy_version=d.policy_version,
                     details={"agent": agent.name, "workflow_id": ctx.workflow_id, "resource": resource.id if resource else None,
                              "latency_ms": ms})
        return out
