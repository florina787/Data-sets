"""Flying Florina 3.0 governed agent harness.

USER REQUEST -> authentication (API dependency) -> intent classification (hybrid router) -> policy engine (precheck step)
-> task planner (this module: template plan sized to the request, with an execution budget) -> supervisor (DAG engine)
-> specialist agents (registry below, each with its own tool allowlist) -> authorized tools (policy gateway: deny-by-default,
schema validation, timeouts, circuit breaker) -> evidence validation -> human approval when required (approval gate, existing)
-> response generation (deterministic composer, then local Qwen explanation + Evidence Challenger) -> audit logging.

Budgets are enforced, not advisory: a step that would exceed the tool-call or wall-clock budget halts the run with status
`budget_exceeded`. Agents only call tools on their own allowlist (least privilege) and every call still passes the policy engine.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from app.agents.common import call_tool
from app.core import db
from app.core.util import now_iso
from app.workflows.engine import CaseState, StepContext, StepHalt

SUPERVISOR = "Supervisor Agent"

AGENTS: dict[str, dict[str, Any]] = {
    "Aerospace Engineering Agent": {"reuses": "Diagnostic Evidence Agent (2.0)", "tools": ["docs.search", "telemetry.get_series", "visual.capabilities"],
                                    "role": "Engineering interpretation of evidence; civilian visual-analysis capability reporting"},
    "Component Prognostics Agent": {"reuses": None, "tools": ["forecast.components", "forecast.series", "twin.unit"],
                                    "role": "Demand, remaining-useful-life and failure-risk forecasts"},
    "Maintenance Intelligence Agent": {"reuses": "Maintenance Planner Agent (2.0)", "tools": ["maintenance.get_history", "roster.find_qualified", "hangar.find_slots"],
                                       "role": "Maintenance history, capacity and planning"},
    "Supply Chain Forecast Agent": {"reuses": "Parts Agent (2.0)", "tools": ["supply.delay_impact", "global.map_state", "parts.check_availability", "forecast.components"],
                                    "role": "Supplier lead-time risk, inventory depletion, delay impact"},
    "Digital Twin Agent": {"reuses": None, "tools": ["twin.unit"], "role": "Component-level twin: history, telemetry, flags, uncertainty"},
    "Geospatial Intelligence Agent": {"reuses": None, "tools": ["global.map_state"], "role": "Regional aggregation and map state"},
    "Operational Resilience Agent": {"reuses": "Scenario Simulator Agent (2.0)", "tools": ["resilience.simulate", "supply.delay_impact"],
                                     "role": "Baseline / disruption / recovery simulation"},
    "Compliance Evidence Agent": {"reuses": "Compliance Agent (2.0)", "tools": ["docs.search"], "role": "Document evidence and revision checks"},
    "Knowledge Retrieval Agent": {"reuses": "Document Retrieval Agent (2.0)", "tools": ["docs.search", "memory.recall"],
                                  "role": "Access-filtered retrieval and the user's own conversation memory"},
    "Forecast Evaluation Agent": {"reuses": None, "tools": ["forecast.evaluation"], "role": "Held-out metrics, baselines, calibration, backtests"},
    "Software Change Impact Agent": {"reuses": None, "tools": ["changeimpact.analyze"], "role": "Dependency, test and requirement impact of a change"},
    "Governance and Audit Agent": {"reuses": "Security & Governance Agent (2.0)", "tools": ["harness.trace"], "role": "Execution traces, policy outcomes, audit"},
}


@dataclass
class Budget:
    max_steps: int
    max_tool_calls: int
    max_wall_s: float
    max_model_calls: int = 1  # one Qwen explanation per answer

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _plan(state: CaseState) -> dict[str, Any]:
    p = state.inputs.get("_plan")
    if not p:
        raise StepHalt("failed", "Harness plan missing")
    return p


def htool(state: CaseState, ctx: StepContext, agent_name: str, tool: str, args: dict[str, Any]) -> Any:
    """Tool call through the harness: agent allowlist + budget, then the policy gateway (authoritative)."""
    plan = _plan(state)
    if tool not in AGENTS.get(agent_name, {}).get("tools", []):
        with ctx.lock:
            state.warnings.append(f"Harness blocked {agent_name} from calling {tool}: not on that agent's tool allowlist.")
            state.tool_calls.append({"agent": agent_name, "tool": tool, "status": "blocked_by_harness", "args": args})
        raise StepHalt("denied", f"{tool} is not on {agent_name}'s allowlist (least privilege).")
    limit = int(ctx.options.get("budget_tool_calls") or plan["budget"]["max_tool_calls"])
    with ctx.lock:  # atomic reservation: parallel specialist steps cannot both slip under the limit
        used = int(plan.get("reserved", 0))
        if used >= limit:
            raise StepHalt("budget_exceeded", f"Tool-call budget of {limit} reached before {tool}.")
        plan["reserved"] = used + 1
    wall = float(ctx.options.get("budget_wall_s") or plan["budget"]["max_wall_s"])
    if time.time() - plan["started"] > wall:
        raise StepHalt("budget_exceeded", f"Wall-clock budget of {wall}s exceeded before {tool}.")
    result, rec = call_tool(state, ctx, agent_name, tool, args)
    return result if rec["status"] == "ok" else None


def plan_step(intent: str, agents: list[str], tools: list[str], budget: Budget, rationale: Callable[[CaseState], str]):
    def step(state: CaseState, ctx: StepContext) -> dict[str, Any]:
        p = {"intent": intent, "agents": agents, "tools": tools, "budget": budget.as_dict(), "rationale": rationale(state), "started": time.time()}
        with ctx.lock:
            state.inputs["_plan"] = p
        db.execute("INSERT OR REPLACE INTO harness_plans VALUES (?,?,?,?,?,?,?,?,?)",
                   (state.run_id, now_iso(), ctx.human.id, intent, db.jdump(agents), db.jdump(tools), db.jdump(budget.as_dict()), db.jdump({}), "running"))
        return {"summary": f"Plan for '{intent}': {len(agents)} specialist agent(s), up to {budget.max_tool_calls} tool calls, "
                           f"{budget.max_wall_s:.0f}s budget. {p['rationale']}", "plan": {"agents": agents, "tools": tools, "budget": budget.as_dict()}}
    return step


def tool_step(agent_name: str, tool: str, key: str, args: Callable[[CaseState], dict[str, Any]], summary: Callable[[Any], str], required: bool = True):
    def step(state: CaseState, ctx: StepContext) -> dict[str, Any]:
        a = args(state)
        res = htool(state, ctx, agent_name, tool, a)
        with ctx.lock:
            state.inputs[key] = res
            if required and res is None:
                state.inputs.setdefault("_missing", []).append(key)
        return {"summary": summary(res) if res is not None else f"{tool} returned no result (see warnings).", "tools": [tool]}
    return step


def evidence_step(required: list[str]):
    """Evidence validation: every required tool result exists; record evidence references; close the plan with usage."""
    def step(state: CaseState, ctx: StepContext) -> dict[str, Any]:
        missing = [k for k in required if state.inputs.get(k) in (None, {}, [])]
        refs = []
        for k in required:
            v = state.inputs.get(k)
            if isinstance(v, dict):
                refs.append({"kind": k, "ref": (v.get("freshness") or {}).get("model_version") or k,
                             "detail": {kk: v.get(kk) for kk in ("horizon_days", "data_as_of", "method") if kk in v} | {"freshness": v.get("freshness")}})
        with db.session(write=True) as conn:
            for r in refs:
                conn.execute("INSERT INTO evidence_refs (run_id, kind, ref, detail_json, ts) VALUES (?,?,?,?,?)", (state.run_id, r["kind"], str(r["ref"]),
                                                                                                                db.jdump(r["detail"]), now_iso()))
        plan = state.inputs.get("_plan")
        usage = {"tool_calls": sum(1 for c in state.tool_calls if c.get("status") != "blocked_by_harness"),
                 "tool_denials": sum(1 for c in state.tool_calls if c.get("status") == "denied"),
                 "wall_s": round(time.time() - plan["started"], 3) if plan else None, "missing_evidence": missing}
        db.execute("UPDATE harness_plans SET usage_json = ?, outcome = ? WHERE run_id = ?", (db.jdump(usage), "missing_evidence" if missing else "validated", state.run_id))
        if missing:
            with ctx.lock:
                state.warnings.append(f"Missing evidence: {', '.join(missing)}. The answer below covers only what was retrieved.")
        return {"summary": f"Evidence validated: {len(required) - len(missing)}/{len(required)} required result(s) present; "
                           f"{len(refs)} evidence reference(s) recorded." + (f" Missing: {missing}." if missing else ""), "missing": missing}
    return step


def registry_view() -> dict[str, Any]:
    from app.services.tools import registry

    reg = registry()
    return {"agents": [{"name": n, **a} for n, a in AGENTS.items()],
            "tools": [reg.tools[t].describe() | {"agents": [n for n, a in AGENTS.items() if t in a["tools"]]} for t in sorted(reg.tools)]}
