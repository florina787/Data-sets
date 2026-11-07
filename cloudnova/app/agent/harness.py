"""Tool registry + run context. Adapted from FloPilot backend/app/harness/runtime.py:
typed tool inputs, permission classes, per-tool timeout, step budget, and a step trace for every call.
Dropped from the original: workbook versions, auth principals, cost budgets, cancellation via DB
(CloudNova tools are read-only and short-lived).
"""
from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..errors import AppError

log = logging.getLogger("cloudnova.harness")
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="cloudnova-tool")
MODEL_INVOCABLE = {"read"}
MAX_STEPS = 6


@dataclass
class ToolSpec:
    name: str
    description: str
    permission: str          # read | admin
    agent: str               # logical agent that owns the tool
    handler: Callable[..., dict]
    timeout_s: float = 30.0


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

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())


registry = ToolRegistry()


def tool(name: str, description: str, agent: str, permission: str = "read", timeout_s: float = 30.0):
    def deco(fn):
        registry.register(ToolSpec(name, description, permission, agent, fn, timeout_s))
        return fn
    return deco


@dataclass
class RunContext:
    run_id: str
    session_id: str
    caller: str = "supervisor"   # supervisor | model
    steps: int = 0
    trace: list[dict] = field(default_factory=list)
    t0: float = field(default_factory=time.perf_counter)

    def note(self, step: str, detail: str = "", ms: float = 0.0, status: str = "ok", **extra: Any) -> None:
        self.trace.append({"step": step, "status": status, "ms": round(ms, 1), "detail": detail, **extra})

    def call(self, name: str, **kwargs: Any) -> dict:
        spec = registry.get(name)
        if self.steps >= MAX_STEPS:
            raise AppError("budget_exceeded", "This request reached its step budget and was stopped.", 429)
        if self.caller == "model" and spec.permission not in MODEL_INVOCABLE:
            self.note("tool_denied", f"{name}: model may only call read tools", status="denied", tool=name, agent=spec.agent)
            raise AppError("tool_not_allowed", f"'{name}' cannot be called by the model.", 403)
        self.steps += 1
        started = time.perf_counter()
        future = _executor.submit(spec.handler, **kwargs)
        try:
            out = future.result(timeout=spec.timeout_s)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            self.note("tool", f"{name} timed out", (time.perf_counter() - started) * 1000, "error", tool=name, agent=spec.agent)
            raise AppError("tool_timeout", f"'{name}' took longer than {spec.timeout_s:.0f}s.", 504, retryable=True) from exc
        except AppError as exc:
            self.note("tool", f"{name}: {exc.code} — {exc.message}", (time.perf_counter() - started) * 1000, "error",
                      tool=name, agent=spec.agent, code=exc.code)
            raise
        except Exception as exc:  # unexpected: logged with stack, surfaced safely
            log.exception("tool %s failed", name)
            self.note("tool", f"{name} failed unexpectedly", (time.perf_counter() - started) * 1000, "error", tool=name, agent=spec.agent)
            raise AppError("tool_failed", f"'{name}' failed unexpectedly.", 500) from exc
        self.note("tool", out.get("_trace", name), (time.perf_counter() - started) * 1000, tool=name, agent=spec.agent)
        return out
