"""Node instrumentation: timing, execution path and error capture for every graph node."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.graph.state import CopilotState
from app.models.domain import AgentStep

logger = logging.getLogger(__name__)

NodeFn = Callable[[CopilotState], dict[str, Any]]


def instrument(name: str, fn: NodeFn) -> NodeFn:
    """Wrap a node so it records an :class:`AgentStep` and never crashes the graph.

    A failing specialist degrades the answer (and lowers confidence via the
    guardrail) instead of failing the whole request; the error is surfaced in
    the response and the trace.
    """

    def wrapped(state: CopilotState) -> dict[str, Any]:
        start = time.perf_counter()
        error: str | None = None
        try:
            update = dict(fn(state))
        except Exception as exc:  # deliberate catch-all at the node boundary
            logger.exception("Node %s failed (request_id=%s)", name, state.get("request_id"))
            error = f"{name}: {type(exc).__name__}: {exc}"
            update = {"errors": [error]}
            if name == "supervisor":  # keep the graph moving: go straight to the response
                update.update(next_agent="response_agent", plan=[])
        detail = str(update.pop("_detail", ""))
        duration = round((time.perf_counter() - start) * 1000, 2)
        update["execution_path"] = [name]
        update["agent_steps"] = [AgentStep(agent=name, duration_ms=duration, detail=detail, error=error)]
        logger.debug("node=%s duration_ms=%.1f %s", name, duration, detail)
        return update

    wrapped.__name__ = f"{name}_node"
    return wrapped
