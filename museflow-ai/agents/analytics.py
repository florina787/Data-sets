"""Analytics role (Stella 🔮): weighted matrices, critical path and run metrics."""
from __future__ import annotations

from typing import Any

from agents.base import AgentResult, agent_node, prior
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState


def weighted_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    weights = sum(c["weight"] for c in matrix["criteria"])
    totals = []
    for index, option in enumerate(matrix["options"]):
        score = sum(c["weight"] * c["scores"][index] for c in matrix["criteria"]) / weights
        totals.append({"option": option, "score": round(score, 3), "percent": round(score / 5 * 100, 1)})
    return sorted(totals, key=lambda t: -t["score"])


def critical_path(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Classic CPM over task hours (ignores single-worker capacity; that's the planner's job)."""
    order = [t["id"] for t in tasks]  # planner output is already topologically ordered
    by_id = {t["id"]: t for t in tasks}
    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    for tid in order:
        es[tid] = max((ef[d] for d in by_id[tid]["depends_on"]), default=0.0)
        ef[tid] = es[tid] + float(by_id[tid]["hours"])
    project_end = max(ef.values(), default=0.0)
    successors: dict[str, list[str]] = {tid: [] for tid in order}
    for tid in order:
        for dep in by_id[tid]["depends_on"]:
            successors[dep].append(tid)
    ls: dict[str, float] = {}
    lf: dict[str, float] = {}
    for tid in reversed(order):
        lf[tid] = min((ls[s] for s in successors[tid]), default=project_end)
        ls[tid] = lf[tid] - float(by_id[tid]["hours"])
    rows = [{"id": tid, "title": by_id[tid]["title"], "es": es[tid], "ef": ef[tid], "slack": round(ls[tid] - es[tid], 3)} for tid in order]
    path = [r["id"] for r in rows if abs(r["slack"]) < 1e-9]
    return {"rows": rows, "critical_path": path, "duration_hours": project_end}


def run_metrics(state: MuseState) -> dict[str, Any]:
    events = [e for e in state.get("trace", []) if e.get("kind") == "agent"]
    return {
        "agent_steps": len(events),
        "tool_calls": sum(len(e.get("tool_calls", [])) for e in events),
        "measured_ms": round(sum(e.get("duration_ms", 0.0) for e in events), 3),
        "agents": sorted({e["agent"] for e in events}),
    }


@agent_node("analytics", "analytics")
def analytics(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    scenario = state.get("scenario_id")
    research = prior(state, "research")
    plan = prior(state, "planning")
    output: dict[str, Any] = {"kind": "analytics", "run_metrics": run_metrics(state)}
    heads = []
    if research.get("matrix"):
        ranking = weighted_matrix(research["matrix"])
        output["ranking"] = ranking
        output["illustrative"] = True
        heads.append(f"Weighted matrix favours {ranking[0]['option']} ({ranking[0]['percent']}%, illustrative scores)")
    if plan.get("tasks"):
        cpm = critical_path(plan["tasks"])
        output["cpm"] = cpm
        heads.append(f"Critical path {' → '.join(cpm['critical_path'])} ({cpm['duration_hours']:g} h)")
    if scenario == "dream_team" or not heads:
        m = output["run_metrics"]
        heads.append(f"So far: {m['agent_steps']} agent steps, {m['tool_calls']} tool calls, {m['measured_ms']:.1f} ms measured")
    output["headline"] = "; ".join(heads) + "."
    return AgentResult(output=output, message=output["headline"])
