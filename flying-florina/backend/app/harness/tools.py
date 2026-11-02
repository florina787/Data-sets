"""Typed tool contracts for the Flying Florina 3.0 specialist agents.

Each tool is a pinned, schema-hashed entry in fixtures/policies/tool_allowlist.yaml and runs only through the policy gateway
(app.integrations.mcp.registry.Registry.invoke): deny-by-default authorisation, input validation, timeout, circuit breaker, redacted
log. Tools return compact, deterministic results; none of them calls a language model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.integrations.mcp.registry import ToolSpec

REGIONS = Literal["Europe", "North America", "Middle East", "Asia-Pacific", "Latin America", "Africa"]
CAT = r"^[a-z_]{3,40}$"


class ForecastArgs(BaseModel):
    horizon_days: int = Field(90, ge=7, le=90)
    category: str | None = Field(None, pattern=CAT)
    family: str | None = Field(None, max_length=30)
    region: REGIONS | None = None


class SeriesArgs(BaseModel):
    category: str = Field(pattern=CAT)
    region: REGIONS | None = None


class EvalArgs(BaseModel):
    task: Literal["all", "demand", "rul", "failure_risk_30d", "anomaly", "lead_time", "repair_turnaround"] = "all"


class MapArgs(BaseModel):
    horizon_days: int = Field(30, ge=0, le=90)
    category: str | None = Field(None, pattern=CAT)
    family: str | None = Field(None, max_length=30)
    region: REGIONS | None = None


class UnitArgs(BaseModel):
    unit_id: str | None = Field(None, pattern=r"^U-F\d{2}-C\d{2}-P\d-\d{1,2}$")
    category: str | None = Field(None, pattern=CAT)
    region: REGIONS | None = None


class DelayArgs(BaseModel):
    supplier_id: str = Field(pattern=r"^S[1-8]$")
    delay_days: float = Field(ge=0, le=120)
    horizon_days: int = Field(60, ge=7, le=90)


class ResilienceArgs(BaseModel):
    scenario: Literal["facility_outage", "logistics_interruption", "supplier_delay", "severe_weather", "workforce_shortage", "demand_surge",
                      "repair_tat_extension", "software_outage"]
    facility_id: str | None = Field(None, pattern=r"^F\d{2}$")
    supplier_id: str | None = Field(None, pattern=r"^S[1-8]$")
    region: REGIONS | None = None
    added_days: float | None = Field(None, ge=0, le=120)
    capacity_cut: float | None = Field(None, ge=0, le=0.95)
    duration_weeks: int | None = Field(None, ge=1, le=12)


class RecallArgs(BaseModel):
    query: str = Field("", max_length=200)
    session_id: str | None = Field(None, max_length=40)
    limit: int = Field(5, ge=1, le=20)


class ChangeArgs(BaseModel):
    target: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9_./{}\-]+$")


class EmptyArgs(BaseModel):
    detail: Literal["summary"] = "summary"


class TraceArgs(BaseModel):
    run_id: str | None = Field(None, max_length=40)


def _forecast(horizon_days: int, category: str | None, family: str | None, region: str | None) -> dict[str, Any]:
    from app.api.routes_global import component_forecast

    r = component_forecast(horizon_days, category, region)
    if family:
        r["rows"] = [x for x in r["rows"] if x["family"].lower() == family.lower()]
    r["rows"] = r["rows"][:20]
    return r


def _series(category: str, region: str | None) -> dict[str, Any]:
    from app.api.routes_global import series

    s = series(category, None, region)
    s["history"] = s["history"][-26:]
    return s


def _evaluation(task: str) -> dict[str, Any]:
    from app.global_intel.forecast import engine

    e = engine()
    m = e.metrics if task == "all" else {task: e.metrics[task]}
    return {"metrics": m, "backtest": e.backtest, "freshness": e.freshness()}


def _map(horizon_days: int, category: str | None, family: str | None, region: str | None) -> dict[str, Any]:
    from app.api.routes_global import map_state
    from app.global_intel.forecast import engine

    st = map_state(horizon_days, category)
    cats = {c["id"]: c for c in st["categories"]}
    fam_ok = (lambda cid: cats[cid]["family"].lower() == family.lower()) if family else (lambda cid: True)
    short = []
    for f in st["facilities"]:
        if region and f["region"] != region:
            continue
        for s in f.get("shortages", []):
            if fam_ok(s["category_id"]):
                short.append({"facility": f["name"], "facility_id": f["id"], "city": f["city"], "region": f["region"], "category_id": s["category_id"],
                              "category": cats[s["category_id"]]["name"], "stockout_prob": s["stockout_prob"], "on_hand_p50": s["p50"]})
    short.sort(key=lambda x: -x["stockout_prob"])
    e = engine()
    return {"horizon_days": st["horizon_days"], "shortages": short[:25], "shortage_count": len(short),
            "regions": [r for r in st["regions"] if not region or r["region"] == region],
            "suppliers": sorted(({k: s[k] for k in ("id", "name", "region", "late_probability", "baseline_late_probability", "disruption_days_added", "open_orders")}
                                 for s in st["suppliers"] if not region or s["region"] == region), key=lambda s: -s["late_probability"]),
            "disruptions": [{k: d[k] for k in ("id", "title", "region", "phase", "severity", "recovery_progress", "days_to_restore")} for d in st["disruptions"]
                            if not region or d["region"] == region],
            "freshness": e.freshness(), "assumptions": st["assumptions"][-4:]}


def _unit(unit_id: str | None, category: str | None, region: str | None) -> dict[str, Any]:
    from app.api.routes_global import twin
    from app.global_intel.forecast import engine

    e = engine()
    if not unit_id:
        cands = [u for u in e.units.values() if u["status"] == "installed" and (not category or u["category_id"] == category)
                 and (not region or e.fac[u["facility_id"]]["region"] == region)]
        if not cands:
            raise ValueError("No installed unit matches.")
        unit_id = max(cands, key=lambda u: (u.get("risk_30d") or 0, -(u.get("last_health") or 1)))["id"]
    t = twin(unit_id)
    t["telemetry"] = t["telemetry"][-26:]
    t["events"] = t["events"][-8:]
    return t


def _delay(supplier_id: str, delay_days: float, horizon_days: int) -> dict[str, Any]:
    from app.global_intel import simulate
    from app.global_intel.forecast import engine

    r = simulate.delay_impact(engine(), supplier_id, delay_days, horizon_days)
    r["rows"] = r["rows"][:12]
    return r


def _resilience(scenario: str, facility_id: str | None, supplier_id: str | None, region: str | None, added_days: float | None,
                capacity_cut: float | None, duration_weeks: int | None) -> dict[str, Any]:
    from app.global_intel import simulate
    from app.global_intel.forecast import engine

    params = {k: v for k, v in {"facility_id": facility_id, "supplier_id": supplier_id, "region": region, "added_days": added_days,
                                "capacity_cut": capacity_cut, "duration_weeks": duration_weeks}.items() if v is not None}
    return simulate.resilience(engine(), scenario, params)


def _recall(query: str, session_id: str | None, limit: int, actor: Any) -> dict[str, Any]:
    from app.harness import memory

    return memory.recall(actor.id, query, session_id, limit)


def _change(target: str) -> dict[str, Any]:
    from app.engineering import change_impact

    r = change_impact.analyze(target)
    r["affected_modules"] = r.get("affected_modules", [])[:25]
    return r


def _visual_caps(detail: str) -> dict[str, Any]:
    from app.visual import lab

    caps = lab.capabilities()
    ev = lab.evaluate()
    return {"capabilities": caps, "evaluation": {k: ev[k] for k in ("method", "is_ai", "dataset", "precision", "recall", "f1", "tp", "fp", "fn", "tn", "n",
                                                                    "false_positive_rate", "false_negative_rate", "by_object")}}


def _trace(run_id: str | None, actor: Any) -> dict[str, Any]:
    from app.core import db
    from app.workflows.engine import events
    from app.workflows.graphs import GRAPHS

    if run_id:
        run = db.query_one("SELECT id, workflow, query, status, created FROM workflow_runs WHERE id = ? AND user_id = ?", (run_id, actor.id))
    else:  # the user's most recent investigation other than trace requests themselves
        run = db.query_one("SELECT id, workflow, query, status, created FROM workflow_runs WHERE user_id = ? AND workflow NOT IN "
                           "('agent_trace','greeting','clarify','unsupported','general_knowledge','policy_refusal') ORDER BY created DESC LIMIT 1", (actor.id,))
    if not run:
        return {"run": None, "events": [], "graph": None}
    evs = events(run["id"])
    plan = db.query_one("SELECT * FROM harness_plans WHERE run_id = ?", (run["id"],))
    return {"run": run, "graph": GRAPHS[run["workflow"]]().describe() if run["workflow"] in GRAPHS else None,
            "events": [{k: e[k] for k in ("step", "agent", "status", "attempt", "duration_ms", "ts")} for e in evs][-60:],
            "plan": {k: db.jload(plan[k], None) if k.endswith("_json") else plan[k] for k in plan} if plan else None}


def specs() -> list[ToolSpec]:
    slow = 120.0  # first call fits the forecasting models (about 10-45 s) unless the cache exists
    return [
        ToolSpec("forecast.components", "1.0.0", "Component demand forecast (P10/P50/P90), inventory risk, cost by category.", "read", "INTERNAL",
                 ForecastArgs, _forecast, timeout_s=slow),
        ToolSpec("forecast.series", "1.0.0", "Weekly removal history and cumulative forecast for one category.", "read", "INTERNAL", SeriesArgs, _series, timeout_s=slow),
        ToolSpec("forecast.evaluation", "1.0.0", "Held-out evaluation metrics, baselines, calibration and backtest.", "read", "INTERNAL", EvalArgs, _evaluation, timeout_s=slow),
        ToolSpec("global.map_state", "1.0.0", "Shortages, regions, supplier delay risk and disruptions at a horizon.", "read", "INTERNAL", MapArgs, _map, timeout_s=slow),
        ToolSpec("twin.unit", "1.0.0", "Digital twin of one tracked component (or the highest-risk match).", "read", "INTERNAL", UnitArgs, _unit, timeout_s=slow),
        ToolSpec("supply.delay_impact", "1.0.0", "Inventory and maintenance impact of a supplier delivery delay.", "simulate", "INTERNAL", DelayArgs, _delay, timeout_s=slow),
        ToolSpec("resilience.simulate", "1.0.0", "Baseline vs disruption vs recovery simulation.", "simulate", "INTERNAL", ResilienceArgs, _resilience, timeout_s=slow),
        ToolSpec("memory.recall", "1.0.0", "Search the requesting user's own saved conversations.", "read", "INTERNAL", RecallArgs, _recall, needs_actor=True),
        ToolSpec("changeimpact.analyze", "1.0.0", "Static change-impact analysis of this repository.", "read", "INTERNAL", ChangeArgs, _change, timeout_s=30),
        ToolSpec("visual.capabilities", "1.0.0", "Visual-analysis capabilities and labelled-set evaluation.", "read", "INTERNAL", EmptyArgs, _visual_caps, timeout_s=60),
        ToolSpec("harness.trace", "1.0.0", "Execution trace of the user's own workflow run.", "read", "INTERNAL", TraceArgs, _trace, needs_actor=True),
    ]
