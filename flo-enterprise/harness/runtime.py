"""The agent harness: every agent execution goes through `Harness.run`.

Request admission (role check, input size, global concurrency with load shedding) -> idempotency cache ->
budgeted execution with deadline + cancellation -> retries with exponential backoff for retryable failures ->
output schema validation + numeric grounding -> telemetry + audit. Agents never receive raw adapters for side effects:
they act through `ctx.tool(...)` (the tool gateway) and `ctx.narrate(...)` (policy-checked model invocation)."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

from backend.config import get_settings
from governance import audit
from governance.policy import Resource
from harness.context import Budget, RunContext
from harness.errors import (AdmissionRejected, HarnessError, LoadShed, OutputValidationFailed, PolicyDenied, ProviderError,
                            classify)
from harness.models import Generation, MockModel
from harness.registry import REGISTRY, AgentRegistry
from harness.resilience import TTLCache, retry
from harness.validation import ungrounded_numbers
from observability.telemetry import ACTIVE_WORKFLOWS, get_telemetry


class Harness:
    def __init__(self, registry: AgentRegistry = REGISTRY, max_concurrent: int | None = None):
        self.registry = registry
        n = max_concurrent or get_settings().max_concurrent_workflows
        self.slots = threading.BoundedSemaphore(n)
        self.capacity = n
        self.active = 0
        self.lock = threading.Lock()
        self.cache = TTLCache(ttl_s=300)
        self.cancel_events: dict[str, threading.Event] = {}

    # ------------------------------------------------------------------ admission
    def admit(self, ctx: RunContext, wait_s: float = 2.0):
        if not self.slots.acquire(timeout=wait_s):
            raise LoadShed("harness at capacity; request shed (retry with backoff)")
        with self.lock:
            self.active += 1
            ACTIVE_WORKFLOWS.set(self.active)
        self.cancel_events[ctx.workflow_id] = ctx.cancel_event

    def release(self, ctx: RunContext):
        self.cancel_events.pop(ctx.workflow_id, None)
        with self.lock:
            self.active -= 1
            ACTIVE_WORKFLOWS.set(self.active)
        self.slots.release()

    def cancel(self, workflow_id: str) -> bool:
        ev = self.cancel_events.get(workflow_id)
        if ev:
            ev.set()
        return ev is not None

    # ------------------------------------------------------------------ model invocation (policy-checked)
    def narrate(self, ctx: RunContext, template_id: str, facts: dict, classification: str = "confidential") -> Generation:
        model = ctx.model
        prov = ctx.engine.provider(model.provider_key) or {}
        tenant_res = next((t["residency"] for t in ctx.adapters.store.tables["tenants"] if t["id"] == ctx.principal.tenant_id), None)
        res = Resource("model_provider", model.provider_key, ctx.principal.tenant_id,
                       {"region": prov.get("region"), "allowed_classifications": prov.get("allowed_classifications", []),
                        "classification": "public"})
        d = ctx.engine.authorize(ctx.service_principal, "model:invoke", res,
                                 {"allowed_regions": ctx.engine.allowed_regions(tenant_res), "data_classification": classification})
        ctx.policy_log.append({"action": "model:invoke", "allowed": d.allowed, "provider": model.provider_key, "rules": d.denial_codes})
        if not d.allowed:
            if isinstance(model, MockModel):
                raise PolicyDenied(f"model invocation denied: {d.denial_codes}")
            # fall back to the in-process deterministic model rather than sending data to a non-compliant provider
            audit.record(tenant_id=ctx.principal.tenant_id, actor="svc-flo-orchestrator", action="model:invoke", resource_type="model_provider",
                         resource_id=model.provider_key, decision="deny", reasons=d.reasons, policy_version=d.policy_version)
            model = MockModel()
        try:
            gen = model.narrate(template_id, facts)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"model provider error: {e.__class__.__name__}") from e
        bad = ungrounded_numbers(gen.text, facts)
        if bad and not isinstance(model, MockModel):
            gen = MockModel().narrate(template_id, facts)  # reject hallucinated numbers; use deterministic renderer
            bad = ungrounded_numbers(gen.text, facts)
        if bad:
            raise OutputValidationFailed(f"narrative contains ungrounded numbers: {bad[:5]}")
        ctx.budget.charge_tokens(gen.tokens_in + gen.tokens_out, gen.cost_usd)
        ctx._gen_stats = getattr(ctx, "_gen_stats", []) + [gen]
        return gen

    # ------------------------------------------------------------------ run
    def run(self, agent_name: str, ctx: RunContext, payload: dict | BaseModel) -> BaseModel:
        reg = self.registry.get(agent_name)
        spec = reg.spec
        started = datetime.now(timezone.utc)
        t0 = time.monotonic()
        status, fclass, retries, out, cache_hit = "failed", None, 0, None, False
        prev_agent, prev_budget = ctx.agent, ctx.budget
        ctx.agent = spec
        ctx._gen_stats = []
        try:
            if not set(ctx.principal.roles) & spec.allowed_roles:
                raise AdmissionRejected(f"roles {list(ctx.principal.roles)} may not use {spec.name}", code="AGENT-ROLE-DENIED")
            try:
                inp = payload if isinstance(payload, spec.input_model) else spec.input_model.model_validate(payload)
            except ValidationError as e:
                raise AdmissionRejected(f"invalid input: {e.errors()[:2]}", code="INVALID-INPUT") from e
            raw = inp.model_dump_json()
            if len(raw) > get_settings().max_input_chars * 4:
                raise AdmissionRejected("input exceeds size limit", code="INPUT-TOO-LARGE")
            key = hashlib.sha256(f"{ctx.principal.tenant_id}|{ctx.principal.user_id}|{','.join(sorted(ctx.principal.roles))}|"
                                 f"{spec.name}@{spec.version}|{ctx.language}|{raw}|{ctx.adapters.store.version}".encode()).hexdigest()
            cached = self.cache.get(key) if not spec.approval_actions else None
            if cached is not None:
                out, cache_hit, status = spec.output_model.model_validate(cached["out"]), True, "succeeded"
                ctx.citations.extend(cached.get("citations", []))
                return out

            def attempt():
                ctx.budget = Budget(spec.max_iterations, spec.max_tokens, spec.max_cost_usd, time.monotonic() + spec.timeout_s)
                ctx.check_cancel()
                return reg.run(ctx, inp)

            def on_retry(n, e):
                nonlocal retries
                retries = n

            result = retry(attempt, spec.max_retries, on_retry=on_retry)
            try:
                out = result if isinstance(result, spec.output_model) else spec.output_model.model_validate(result)
            except ValidationError as e:
                raise OutputValidationFailed(f"output schema violation: {e.errors()[:2]}") from e
            narrative = getattr(out, "narrative", None)
            if narrative and "numeric_grounding" in spec.eval_requirements:
                bad = ungrounded_numbers(narrative, json.loads(out.model_dump_json()))
                if bad:
                    raise OutputValidationFailed(f"ungrounded numbers {bad[:5]}")
            status = "succeeded"
            if not spec.approval_actions:
                self.cache.put(key, {"out": json.loads(out.model_dump_json()),
                                     "citations": [c for c in ctx.citations if c.get("agent") == spec.name]})
            return out
        except HarnessError as e:
            fclass = e.failure_class
            raise
        except Exception as e:
            fclass = classify(e)
            raise
        finally:
            gens = getattr(ctx, "_gen_stats", [])
            tid = get_telemetry().record_agent(
                ctx=ctx, agent=spec.name, version=spec.version, model=gens[-1].model if gens else ctx.model.name, started=started,
                latency_ms=int((time.monotonic() - t0) * 1000), tokens_in=sum(g.tokens_in for g in gens),
                tokens_out=sum(g.tokens_out for g in gens), cost=sum(g.cost_usd for g in gens), status=status,
                failure_class=fclass, retries=retries, tool_calls=[t for t in ctx.tool_log if t.get("agent") == spec.name],
                eval_score=1.0 if status == "succeeded" else None,
                approval_status=ctx.approvals[-1]["status"] if ctx.approvals else None,
                policy_outcome="deny" if any(not p["allowed"] for p in ctx.policy_log) else "allow", cache_hit=cache_hit,
                inputs={"agent": spec.name}, outputs={"status": status})
            ctx.trace_ids.append(tid)
            ctx.agent, ctx.budget = prev_agent, prev_budget


_harness: Harness | None = None


def get_harness() -> Harness:
    global _harness
    if _harness is None:
        _harness = Harness()
    return _harness
