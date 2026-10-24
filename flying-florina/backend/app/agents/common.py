"""Shared helpers for agents: agent identities, policy-gated tool calls, workspace blocks."""

from __future__ import annotations

from typing import Any

from app.core.security import Actor
from app.integrations.mcp.registry import ToolDenied, ToolFailed
from app.services.tools import registry
from app.workflows.engine import CaseState, StepContext


def agent(name: str) -> Actor:
    slug = name.lower().replace(" & ", "_").replace(" ", "_").replace("agent", "").strip("_")
    return Actor(id=f"agent.{slug}", display_name=name, role="agent", org="FF-Demo-MRO", is_agent=True)


def call_tool(state: CaseState, ctx: StepContext, agent_name: str, tool: str, args: dict[str, Any],
              instruction_source: str = "user") -> tuple[Any | None, dict[str, Any]]:
    """Invoke a tool through the gateway. Denials and failures are recorded, never raised to the user."""
    fault = None
    if ctx.options.get("inject_tool_timeout") == tool:
        fault = "timeout"
    record: dict[str, Any] = {"agent": agent_name, "tool": tool, "args": args, "instruction_source": instruction_source}
    try:
        result, decision = registry().invoke(agent(agent_name), ctx.human, tool, args, run_id=state.run_id,
                                             instruction_source=instruction_source, fault=fault)
        record.update(status="ok", decision=decision.as_dict())
    except ToolDenied as denied:
        result = None
        record.update(status="denied", decision=denied.decision.as_dict())
        with ctx.lock:
            state.warnings.append(f"{tool} withheld: {denied.decision.reason} ({denied.decision.policy_id})")
    except ToolFailed as failed:
        result = None
        record.update(status="failed", error=str(failed))
        with ctx.lock:
            state.warnings.append(f"{tool} failed: {failed}")
    with ctx.lock:
        state.tool_calls.append({k: v for k, v in record.items() if k != "args"} | {"args": args})
        if "decision" in record:
            state.policy_decisions.append(record["decision"])
    return result, record


# ---- workspace block builders (the frontend renders these generically)

def md(text: str) -> dict[str, Any]:
    return {"type": "answer", "markdown": text}


def kpis(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "kpis", "items": items}


def chart(cid: str, title: str, kind: str, x: list[Any], series: list[dict[str, Any]], caption: str = "",
          source: str = "", mark_line: dict[str, Any] | None = None, y_label: str = "") -> dict[str, Any]:
    return {"type": "chart", "id": cid, "title": title, "caption": caption, "source": source,
            "chart": {"kind": kind, "x": x, "series": series, "markLine": mark_line, "yLabel": y_label}}


def table(title: str, columns: list[tuple[str, str]], rows: list[dict[str, Any]], caption: str = "") -> dict[str, Any]:
    return {"type": "table", "title": title, "columns": [{"key": k, "label": label} for k, label in columns],
            "rows": rows, "caption": caption}


def citations(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "citations", "items": items}


def warnings(items: list[str]) -> dict[str, Any]:
    return {"type": "warnings", "items": items}


def assumptions(items: list[str]) -> dict[str, Any]:
    return {"type": "assumptions", "items": items}


def actions(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "actions", "items": items}
