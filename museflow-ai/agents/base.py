"""Shared node wrapper: timing, tool-call recording, retries, error handling and tracing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from langgraph.errors import GraphBubbleUp
from langgraph.runtime import Runtime

from services.tool_registry import ToolEnv, ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState

MAX_RETRIES = 2


class TransientSimulatedError(RuntimeError):
    """A deliberately simulated, recoverable failure (e.g. a fake page-load timeout)."""


@dataclass
class AgentResult:
    output: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    updates: dict[str, Any] = field(default_factory=dict)
    queue_insert: list[str] = field(default_factory=list)
    queue_replace: list[str] | None = None


AgentFn = Callable[[MuseState, MuseContext, ToolRecorder], AgentResult]


def compact(value: Any, depth: int = 0) -> Any:
    """Bounded copy of a value for display in the node inspector."""
    if depth > 4:
        return "…"
    if isinstance(value, str):
        return value if len(value) <= 240 else value[:239] + "…"
    if isinstance(value, dict):
        return {str(k): compact(v, depth + 1) for k, v in list(value.items())[:20]}
    if isinstance(value, (list, tuple)):
        items = [compact(v, depth + 1) for v in list(value)[:10]]
        if len(value) > 10:
            items.append(f"… {len(value) - 10} more")
        return items
    return value


def _input_summary(state: MuseState) -> dict[str, Any]:
    return {
        "scenario_id": state.get("scenario_id"),
        "params": compact(state.get("params", {})),
        "queue_before": list(state.get("queue", [])),
        "available_outputs": sorted((state.get("outputs") or {}).keys()),
        "has_action": bool(state.get("action")),
    }


def agent_node(node_name: str, agent_key: str, kind: str = "agent") -> Callable[[AgentFn], Callable[..., dict[str, Any]]]:
    """Turn a deterministic agent function into a LangGraph node with full tracing."""

    def decorator(fn: AgentFn) -> Callable[..., dict[str, Any]]:
        def node(state: MuseState, runtime: Runtime[MuseContext]) -> dict[str, Any]:
            ctx = runtime.context
            recorder = ToolRecorder(ctx.tools, ToolEnv(ctx.stores, ctx.today))
            started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            t0 = perf_counter()
            queue = list(state.get("queue", []))
            if queue and queue[0] == node_name:
                queue = queue[1:]
            event: dict[str, Any] = {
                "seq": len(state.get("trace", [])) + 1,
                "run_id": state.get("run_id", ""),
                "node": node_name,
                "agent": agent_key,
                "kind": kind,
                "started_at": started,
                "input": _input_summary(state),
            }
            try:
                result = fn(state, ctx, recorder)
            except GraphBubbleUp:
                raise  # LangGraph interrupts must propagate untouched.
            except TransientSimulatedError as exc:
                retries = dict(state.get("retries") or {})
                retries[node_name] = retries.get(node_name, 0) + 1
                event.update(duration_ms=round((perf_counter() - t0) * 1000, 3), tool_calls=recorder.calls, output={})
                if retries[node_name] <= MAX_RETRIES:
                    event.update(status="retrying", message=f"{exc} — retry {retries[node_name]}/{MAX_RETRIES} scheduled.")
                    return {"trace": [event], "retries": retries, "queue": [node_name, *queue], "current_node": node_name}
                event.update(status="failed", message=f"{exc} — retries exhausted.")
                return _failure(event, queue, node_name, retries=retries)
            except Exception as exc:  # noqa: BLE001 - every failure is traced, never swallowed silently
                event.update(
                    duration_ms=round((perf_counter() - t0) * 1000, 3), tool_calls=recorder.calls, output={},
                    status="failed", message=f"{type(exc).__name__}: {exc}",
                )
                return _failure(event, queue, node_name)

            new_queue = result.queue_replace if result.queue_replace is not None else [*result.queue_insert, *queue]
            event.update(
                status="completed",
                duration_ms=round((perf_counter() - t0) * 1000, 3),
                message=result.message,
                output=compact(result.output),
                tool_calls=recorder.calls,
            )
            update: dict[str, Any] = {"trace": [event], "queue": new_queue, "current_node": node_name, **result.updates}
            if result.output:
                update["outputs"] = {node_name: result.output}
            return update

        # No functools.wraps: LangGraph inspects this signature to inject ``runtime``.
        node.__name__ = f"{node_name}_node"
        node.__doc__ = fn.__doc__
        node.node_name = node_name  # type: ignore[attr-defined]
        node.agent_key = agent_key  # type: ignore[attr-defined]
        return node

    return decorator


def _failure(event: dict[str, Any], queue: list[str], node_name: str, retries: dict[str, int] | None = None) -> dict[str, Any]:
    update: dict[str, Any] = {
        "trace": [event],
        "errors": [f"{node_name}: {event['message']}"],
        "status": "error",
        # Audit still runs so failures are always recorded.
        "queue": ["audit"] if node_name != "audit" else [],
        "current_node": node_name,
    }
    if retries is not None:
        update["retries"] = retries
    return update


def prior(state: MuseState, node: str) -> dict[str, Any]:
    return (state.get("outputs") or {}).get(node) or {}
