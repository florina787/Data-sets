"""Typed workflow state shared by every node in the MuseFlow graph."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer: later node outputs are merged (by node name) into earlier ones."""
    return {**(left or {}), **(right or {})}


class TraceEvent(TypedDict, total=False):
    seq: int
    run_id: str
    node: str
    agent: str
    kind: str  # "agent" | "route"
    status: str  # "completed" | "retrying" | "failed"
    started_at: str
    duration_ms: float
    message: str
    input: dict[str, Any]
    output: dict[str, Any]
    tool_calls: list[dict[str, Any]]


class MuseState(TypedDict, total=False):
    run_id: str
    session_id: str
    scenario_id: str
    request: str
    params: dict[str, Any]
    queue: list[str]
    outputs: Annotated[dict[str, Any], merge_dicts]
    trace: Annotated[list[TraceEvent], operator.add]
    errors: Annotated[list[str], operator.add]
    action: dict[str, Any] | None
    governance: dict[str, Any] | None
    approval: dict[str, Any] | None
    action_result: dict[str, Any] | None
    retries: dict[str, int]
    status: str
    current_node: str
    final_response: str


TERMINAL_STATUSES = {"completed", "rejected", "cancelled", "error", "denied", "unsupported"}
