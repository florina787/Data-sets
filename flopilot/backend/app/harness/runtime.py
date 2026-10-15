"""Tool registry and run context: typed inputs, permissions, timeouts, retries, budgets, cancellation.

Tools are the only way the supervisor (deterministic or LLM-driven) touches a workbook. Each
tool declares a permission class:

* ``read``    - inspects data; never changes anything. Model-invocable.
* ``propose`` - prepares a change set and stores it as a PROPOSED operation. Model-invocable;
                nothing is applied until a person approves that exact change set.
* ``mutate`` / ``export`` / ``restore`` - user-only. The policy controller refuses model calls.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .. import audit, db
from ..auth import Principal
from ..common import AppError, now_iso
from ..config import get_settings
from .state import RunState, load_run, transition

log = logging.getLogger("flopilot.harness")
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="flopilot-tool")

MODEL_INVOCABLE = {"read", "propose"}


class Cancelled(Exception):
    pass


class BudgetExceeded(AppError):
    def __init__(self, what: str):
        super().__init__("budget_exceeded", f"This request reached its {what} budget and was stopped.", 429)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    permission: str
    handler: Callable[["RunContext", Any], dict]
    role: str
    timeout_s: float | None = None
    retries: int = 0  # only for idempotent tools
    idempotent: bool = True

    def json_schema(self) -> dict:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return schema


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise AppError("unknown_tool", f"Tool '{name}' is not registered.", 400)
        return self._tools[name]

    def model_tools(self) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.permission in MODEL_INVOCABLE]

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())


registry = ToolRegistry()


def tool(name: str, description: str, input_model: type[BaseModel], permission: str, role: str, **kwargs: Any):
    def decorator(fn: Callable[["RunContext", Any], dict]):
        registry.register(ToolSpec(name, description, input_model, permission, fn, role, **kwargs))
        return fn
    return decorator


@dataclass
class Usage:
    steps: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass
class RunContext:
    run_id: str
    correlation_id: str
    principal: Principal
    workbook_id: str
    version: int
    conversation_id: str
    context: dict
    caller: str = "supervisor"  # supervisor | model
    usage: Usage = field(default_factory=Usage)
    _last_cancel_check: float = 0.0

    # ---- cancellation -------------------------------------------------------------
    def check_cancel(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_cancel_check < 0.2:
            return
        self._last_cancel_check = now
        row = db.fetchone("SELECT cancel_requested FROM runs WHERE id = ?", (self.run_id,))
        if row and row["cancel_requested"]:
            raise Cancelled()

    # ---- state ----------------------------------------------------------------------
    def to(self, state: RunState, note: str | None = None) -> None:
        self.check_cancel(force=True)
        transition(self.run_id, state, note=note)

    def step(self, kind: str, **data: Any) -> None:
        run = load_run(self.run_id)
        steps = run["steps"]
        steps.append({"type": kind, "at": now_iso(), **data})
        db.execute("UPDATE runs SET steps = ?, tokens_in = ?, tokens_out = ?, cost_estimate_usd = ?, updated_at = ? WHERE id = ?",
                   (db.dumps(steps), self.usage.tokens_in, self.usage.tokens_out, round(self.usage.cost_usd, 6), now_iso(), self.run_id))

    # ---- budgets --------------------------------------------------------------------
    def charge_tokens(self, tokens_in: int, tokens_out: int) -> None:
        s = get_settings()
        self.usage.tokens_in += tokens_in
        self.usage.tokens_out += tokens_out
        self.usage.cost_usd += tokens_in / 1e6 * s.llm_input_cost_per_mtok + tokens_out / 1e6 * s.llm_output_cost_per_mtok
        if self.usage.tokens_in + self.usage.tokens_out > s.max_tokens_per_run:
            raise BudgetExceeded("token")
        if self.usage.cost_usd > s.max_cost_per_run_usd:
            raise BudgetExceeded("cost")

    # ---- tool execution --------------------------------------------------------------
    def call(self, name: str, raw_args: dict | None = None) -> dict:
        """Validate, authorise, execute (with timeout/retry) and log one tool call."""
        settings = get_settings()
        self.check_cancel(force=True)
        spec = registry.get(name)
        if self.usage.steps >= settings.max_steps:
            raise BudgetExceeded("step")
        # Policy controller ------------------------------------------------------------
        if self.caller == "model" and spec.permission not in MODEL_INVOCABLE:
            self.step("tool_denied", tool=name, reason="user-only tool")
            raise AppError("tool_not_allowed", f"'{name}' can only be triggered by a person (approval, export or restore).", 403)
        required = {"read": "read", "propose": "propose", "mutate": "approve", "export": "export", "restore": "restore"}[spec.permission]
        if not self.principal.can(required):
            self.step("tool_denied", tool=name, reason=f"role {self.principal.role} lacks {required}")
            raise AppError("forbidden", f"Your role ({self.principal.role}) cannot use '{name}'.", 403)
        try:
            args = spec.input_model.model_validate(raw_args or {})
        except ValidationError as exc:
            self.step("tool_rejected", tool=name, reason="invalid input", errors=len(exc.errors()))
            raise AppError("invalid_tool_input", f"Invalid input for {name}: " + "; ".join(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]), 422) from exc

        self.usage.steps += 1
        attempts = 1 + (spec.retries if spec.idempotent else 0)
        timeout = spec.timeout_s or settings.tool_timeout_s
        started = time.monotonic()
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            future = _executor.submit(spec.handler, self, args)
            try:
                result = future.result(timeout=timeout)
                duration = round((time.monotonic() - started) * 1000)
                bounded = bound_output(result, settings.max_tool_rows)
                self.step("tool_call", tool=name, role=spec.role, permission=spec.permission, status="ok",
                          duration_ms=duration, attempt=attempt, args=_summarize_args(args), output=_summarize_output(bounded))
                audit.record("tool_call", run_id=self.run_id, correlation_id=self.correlation_id, user_id=self.principal.user_id,
                             workspace_id=self.principal.workspace_id, workbook_id=self.workbook_id, workbook_version=self.version,
                             tool=name, status="ok", duration_ms=duration, caller=self.caller)
                return bounded
            except concurrent.futures.TimeoutError:
                future.cancel()
                last_exc = AppError("tool_timeout", f"'{name}' took longer than {timeout:.0f}s and was stopped.", 504, retryable=True)
            except Cancelled:
                raise
            except AppError as exc:
                last_exc = exc
                if not exc.retryable:
                    break
            except Exception:  # unexpected tool failure: logged, surfaced safely
                log.exception("tool %s failed", name)
                last_exc = AppError("tool_failed", f"'{name}' failed unexpectedly.", 500)
                break
            if attempt < attempts:
                time.sleep(0.2 * attempt)
        duration = round((time.monotonic() - started) * 1000)
        assert last_exc is not None
        code = getattr(last_exc, "code", "tool_failed")
        self.step("tool_call", tool=name, role=spec.role, permission=spec.permission, status="error", code=code,
                  duration_ms=duration, args=_summarize_args(args), message=getattr(last_exc, "message", ""))
        audit.record("tool_call", run_id=self.run_id, correlation_id=self.correlation_id, user_id=self.principal.user_id,
                     workspace_id=self.principal.workspace_id, workbook_id=self.workbook_id, workbook_version=self.version,
                     tool=name, status="error", code=code, duration_ms=duration, caller=self.caller)
        raise last_exc


def bound_output(result: Any, max_rows: int) -> Any:
    """Cap list sizes in tool output so neither the model nor the UI receives unbounded data."""
    if isinstance(result, dict):
        out = {}
        for k, v in result.items():
            if isinstance(v, list) and len(v) > max_rows and k in ("rows", "candidates", "groups", "points", "inconsistent", "cells", "issues"):
                out[k] = v[:max_rows]
                out[f"{k}_truncated"] = len(v)
            else:
                out[k] = bound_output(v, max_rows) if isinstance(v, dict) else v
        return out
    return result


def _summarize_args(args: BaseModel) -> dict:
    data = args.model_dump()
    # keep structure, drop free text that may contain workbook content
    return {k: (v if not isinstance(v, str) or len(v) <= 60 else v[:57] + "…") for k, v in data.items()}


def _summarize_output(result: Any) -> dict:
    if not isinstance(result, dict):
        return {"type": type(result).__name__}
    summary = {"kind": result.get("kind")}
    for key in ("rows", "candidates", "groups", "issues"):
        if isinstance(result.get(key), list):
            summary[f"{key}_count"] = len(result[key])
    if "operation" in result:
        summary["operation_id"] = result["operation"].get("id")
    return summary
