"""Flying Florina 3.0 workflows: planned, budgeted graphs of specialist agents, and their deterministic answer composers.

Every number in a composed answer is copied from a tool result; the local Qwen explanation runs afterwards and is checked by the
Evidence Challenger against these same facts.
"""

from __future__ import annotations

from typing import Any, Callable

from app.agents.analytics import precheck
from app.agents.common import actions, chart, kpis, md, table
from app.harness.core import SUPERVISOR, Budget, evidence_step, plan_step, tool_step
from app.workflows.engine import CaseState, Graph, Step

SEC = "Security & Governance Agent"
GOV = "Governance and Audit Agent"


def _s(state: CaseState) -> dict[str, Any]:
    return state.intent.get("entities", {}) or {}


def _h(state: CaseState, default: int = 30) -> int:
    return int(_s(state).get("horizon_days") or default)


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def _scope(state: CaseState) -> str:
    s = _s(state)
    what = s.get("category", "").replace("_", " ") or (f"{s['family'].lower()} components" if s.get("family") else "all component categories")
    return f"{what}{' in ' + s['region'] if s.get('region') else ''}"


def _graph(name: str, intent: str, agents: list[str], tools: list[str], budget: Budget, steps: list[Step], required: list[str],
           rationale: Callable[[CaseState], str]) -> Graph:
    head = [Step("policy_precheck", SEC, precheck("query"), description="Identity and deny-by-default policy precheck"),
            Step("plan", SUPERVISOR, plan_step(intent, agents, tools, budget, rationale), ["policy_precheck"], retries=0,
                 description="Task planner: agents, tools and execution budget")]
    for s in steps:
        s.deps = s.deps or ["plan"]
    tail = [Step("evidence_validation", GOV, evidence_step(required), [s.name for s in steps], retries=0,
                 description="Evidence validation and evidence references")]
    return Graph(name, head + steps + tail)


# ---------------------------------------------------------------- graphs
def global_shortages_graph() -> Graph:
    return _graph("global_shortages", "global_shortages", ["Geospatial Intelligence Agent", "Supply Chain Forecast Agent"],
                  ["global.map_state", "forecast.components"], Budget(4, 4, 150),
                  [Step("map_state", "Geospatial Intelligence Agent", tool_step("Geospatial Intelligence Agent", "global.map_state", "map",
                        lambda st: {"horizon_days": _h(st), "category": _s(st).get("category"), "family": _s(st).get("family"), "region": _s(st).get("region")},
                        lambda r: f"{r['shortage_count']} projected shortage(s) at +{r['horizon_days']} days."), description="Shortages by site and region"),
                   Step("demand", "Supply Chain Forecast Agent", tool_step("Supply Chain Forecast Agent", "forecast.components", "forecast",
                        lambda st: {"horizon_days": max(7, _h(st)), "category": _s(st).get("category"), "family": _s(st).get("family"), "region": _s(st).get("region")},
                        lambda r: f"Demand forecast for {len(r['rows'])} categories."), description="Demand behind the shortages")],
                  ["map", "forecast"], lambda st: f"Scope: {_scope(st)}, +{_h(st)} days. Two specialists: map state and demand.")


def demand_graph() -> Graph:
    def build() -> Graph:
        return _graph("demand_forecast", "demand_forecast", ["Component Prognostics Agent", "Forecast Evaluation Agent"],
                      ["forecast.components", "forecast.series", "forecast.evaluation"], Budget(5, 4, 150),
                      [Step("forecast", "Component Prognostics Agent", tool_step("Component Prognostics Agent", "forecast.components", "forecast",
                            lambda st: {"horizon_days": max(7, _h(st, 90)), "category": _s(st).get("category"), "family": _s(st).get("family"), "region": _s(st).get("region")},
                            lambda r: f"{len(r['rows'])} categories forecast at +{r['horizon_days']} days."), description="Demand forecast P10/P50/P90"),
                       Step("series", "Component Prognostics Agent", tool_step("Component Prognostics Agent", "forecast.series", "series",
                            lambda st: {"category": _s(st).get("category") or "hydraulic_pump", "region": _s(st).get("region")},
                            lambda r: f"{len(r['history'])} weeks of history for {r['category']}.", required=False), description="History and forecast fan"),
                       Step("evaluation", "Forecast Evaluation Agent", tool_step("Forecast Evaluation Agent", "forecast.evaluation", "evaluation",
                            lambda st: {"task": "demand"}, lambda r: "Held-out demand metrics retrieved."), description="Held-out accuracy for this model")],
                      ["forecast", "evaluation"], lambda st: f"Scope: {_scope(st)}, +{_h(st, 90)} days. Forecast + its held-out accuracy.")
    return build()


def supplier_delays_graph() -> Graph:
    return _graph("supplier_delays", "supplier_delays", ["Geospatial Intelligence Agent"], ["global.map_state"], Budget(3, 2, 120),
                  [Step("map_state", "Geospatial Intelligence Agent", tool_step("Geospatial Intelligence Agent", "global.map_state", "map",
                        lambda st: {"horizon_days": _h(st, 30), "region": _s(st).get("region")},
                        lambda r: f"{len(r['suppliers'])} suppliers with late-delivery probabilities."), description="Supplier delay risk on the map")],
                  ["map"], lambda st: "Simple request: one specialist, one tool.")


def delay_impact_graph() -> Graph:
    return _graph("supply_delay_impact", "supply_delay_impact", ["Supply Chain Forecast Agent", "Operational Resilience Agent"],
                  ["supply.delay_impact", "resilience.simulate"], Budget(5, 4, 180),
                  [Step("delay_impact", "Supply Chain Forecast Agent", tool_step("Supply Chain Forecast Agent", "supply.delay_impact", "impact",
                        lambda st: {"supplier_id": _s(st).get("supplier_id") or "S1", "delay_days": float(_s(st).get("delay_days") or 14), "horizon_days": _h(st, 60)},
                        lambda r: f"{len(r['affected_categories'])} categories affected; {len(r['rows'])} site-category rows."), description="Inventory depletion and deferred work"),
                   Step("network", "Operational Resilience Agent", tool_step("Operational Resilience Agent", "resilience.simulate", "network",
                        lambda st: {"scenario": "supplier_delay", "supplier_id": _s(st).get("supplier_id") or "S1", "added_days": float(_s(st).get("delay_days") or 14)},
                        lambda r: f"Peak backlog {r['results']['disruption']['peak_backlog_hours']} h (disruption) vs {r['results']['baseline']['peak_backlog_hours']} h."),
                        description="Network-level backlog: baseline vs disruption vs recovery")],
                  ["impact", "network"], lambda st: "Complex request: supply specialist + resilience specialist; alternatives compared.")


def degradation_graph() -> Graph:
    return _graph("component_degradation", "component_degradation", ["Digital Twin Agent", "Component Prognostics Agent"], ["twin.unit", "forecast.components"],
                  Budget(4, 3, 150),
                  [Step("twin", "Digital Twin Agent", tool_step("Digital Twin Agent", "twin.unit", "twin",
                        lambda st: {"unit_id": _s(st).get("unit_id"), "category": _s(st).get("category"), "region": _s(st).get("region")},
                        lambda r: f"Twin of {r['unit']['id']} ({r['unit']['category']}), {len(r['flag_reasons'])} flag reason(s)."), description="Unit twin and flags"),
                   Step("context", "Component Prognostics Agent", tool_step("Component Prognostics Agent", "forecast.components", "forecast",
                        lambda st: {"horizon_days": 90, "category": _s(st).get("category"), "region": _s(st).get("region")},
                        lambda r: "Category demand context retrieved.", required=False), description="Category demand context")],
                  ["twin"], lambda st: "Twin first; category forecast for context.")


def resilience_graph() -> Graph:
    return _graph("resilience_scenario", "resilience_scenario", ["Operational Resilience Agent"], ["resilience.simulate"], Budget(3, 2, 150),
                  [Step("simulate", "Operational Resilience Agent", tool_step("Operational Resilience Agent", "resilience.simulate", "sim",
                        lambda st: _scenario_args(st), lambda r: f"{r['label']}: peak backlog {r['results']['disruption']['peak_backlog_hours']} h."),
                        description="Baseline vs disruption vs recovery")],
                  ["sim"], lambda st: "One specialist; three runs (baseline, disruption, recovery) inside one simulation.")


def _scenario_args(st: CaseState) -> dict[str, Any]:
    q = st.query.lower()
    s = _s(st)
    for key, words in (("software_outage", "software"), ("workforce_shortage", "workforce|staff|engineer"), ("severe_weather", "weather|storm"),
                       ("demand_surge", "surge|demand increase|spike"), ("logistics_interruption", "logistic|strike|port|freight"),
                       ("repair_tat_extension", "repair turnaround|repair time|tat"), ("supplier_delay", "supplier|vendor")):
        import re

        if re.search(words, q):
            args: dict[str, Any] = {"scenario": key}
            if key == "supplier_delay":
                args.update(supplier_id=s.get("supplier_id") or "S1", added_days=float(s.get("delay_days") or 14))
            if key == "logistics_interruption" and s.get("region"):
                args["region"] = s["region"]
            return args
    return {"scenario": "facility_outage"}


def evidence_graph() -> Graph:
    return _graph("forecast_evidence", "forecast_evidence", ["Forecast Evaluation Agent", "Knowledge Retrieval Agent"], ["forecast.evaluation", "memory.recall"],
                  Budget(4, 3, 120),
                  [Step("evaluation", "Forecast Evaluation Agent", tool_step("Forecast Evaluation Agent", "forecast.evaluation", "evaluation",
                        lambda st: {"task": "all"}, lambda r: f"{len(r['metrics'])} evaluated model task(s)."), description="Held-out metrics and baselines"),
                   Step("recall", "Knowledge Retrieval Agent", tool_step("Knowledge Retrieval Agent", "memory.recall", "recall",
                        lambda st: {"query": "forecast", "session_id": st.session_id, "limit": 3}, lambda r: f"{len(r['previous_runs'])} earlier run(s) in memory.",
                        required=False), description="Which forecast the user saw before")],
                  ["evaluation"], lambda st: "Evaluation evidence plus the user's previous forecast from memory.")


def accuracy_graph() -> Graph:
    return _graph("forecast_accuracy", "forecast_accuracy", ["Forecast Evaluation Agent"], ["forecast.evaluation"], Budget(3, 2, 120),
                  [Step("evaluation", "Forecast Evaluation Agent", tool_step("Forecast Evaluation Agent", "forecast.evaluation", "evaluation",
                        lambda st: {"task": "all"}, lambda r: f"Backtest over {len(r['backtest'])} weeks."), description="Rolling-origin backtest")],
                  ["evaluation"], lambda st: "Simple request: one specialist.")


def trace_graph() -> Graph:
    return _graph("agent_trace", "agent_trace", [GOV], ["harness.trace"], Budget(3, 2, 30),
                  [Step("trace", GOV, tool_step(GOV, "harness.trace", "trace", lambda st: {"run_id": None},
                        lambda r: f"Trace of {r['run']['id'] if r.get('run') else 'no run'} with {len(r['events'])} events."), description="Last run's real events")],
                  ["trace"], lambda st: "Reads recorded events only; nothing is re-run.")


def recall_graph() -> Graph:
    return _graph("memory_recall", "memory_recall", ["Knowledge Retrieval Agent"], ["memory.recall"], Budget(3, 2, 30),
                  [Step("recall", "Knowledge Retrieval Agent", tool_step("Knowledge Retrieval Agent", "memory.recall", "recall",
                        lambda st: {"query": st.query, "session_id": st.session_id, "limit": 5}, lambda r: f"{len(r['previous_runs'])} earlier investigation(s)."),
                        description="The user's own conversation memory")],
                  ["recall"], lambda st: "Memory lookup scoped to this user.")


def visual_graph() -> Graph:
    return _graph("visual_analysis", "visual_analysis", ["Aerospace Engineering Agent"], ["visual.capabilities"], Budget(3, 2, 90),
                  [Step("capabilities", "Aerospace Engineering Agent", tool_step("Aerospace Engineering Agent", "visual.capabilities", "visual",
                        lambda st: {"detail": "summary"}, lambda r: f"Default method: {r['capabilities']['default_method']}."), description="What visual analysis is actually available")],
                  ["visual"], lambda st: "Reports capabilities honestly; analysis of uploads happens in the Airspace Safety Lab.")


def change_graph() -> Graph:
    return _graph("change_impact", "change_impact", ["Software Change Impact Agent"], ["changeimpact.analyze"], Budget(3, 2, 60),
                  [Step("analyze", "Software Change Impact Agent", tool_step("Software Change Impact Agent", "changeimpact.analyze", "change",
                        lambda st: {"target": _s(st).get("target") or "app.integrations.mcp.registry"},
                        lambda r: f"{len(r.get('affected_modules', []))} module(s), {len(r.get('recommended_tests', []))} test file(s) affected."),
                        description="Static dependency, test and requirement impact")],
                  ["change"], lambda st: "Static analysis of this repository.")


HARNESS_GRAPHS = {
    "global_shortages": global_shortages_graph, "demand_forecast": demand_graph, "supplier_delays": supplier_delays_graph,
    "supply_delay_impact": delay_impact_graph, "component_degradation": degradation_graph, "resilience_scenario": resilience_graph,
    "forecast_evidence": evidence_graph, "forecast_accuracy": accuracy_graph, "agent_trace": trace_graph, "memory_recall": recall_graph,
    "visual_analysis": visual_graph, "change_impact": change_graph,
}


# ---------------------------------------------------------------- composers
def _fresh(r: dict[str, Any] | None) -> str:
    f = (r or {}).get("freshness") or {}
    return f"Data as of {f.get('data_as_of', '?')} · models {f.get('model_version', '?')} · SYNTHETIC data" if f else "SYNTHETIC data"


def _nav(label: str, target: str) -> dict[str, Any]:
    return {"label": label, "kind": "navigate", "target": target}


def _q(label: str) -> dict[str, Any]:
    return {"label": label, "kind": "query", "target": label}


def c_shortages(st: CaseState) -> list[dict[str, Any]]:
    m, fc = st.inputs.get("map") or {}, st.inputs.get("forecast") or {}
    sh = m.get("shortages", [])
    h = m.get("horizon_days", _h(st))
    top = sh[0] if sh else None
    st.answer = (f"**{m.get('shortage_count', 0)} projected shortage(s)** for {_scope(st)} at **+{h} days** (site × category with at least 20% stockout probability). "
                 + (f"Highest risk: **{top['category']}** at {top['facility']} ({top['city']}), stockout probability {_pct(top['stockout_prob'])}." if top else "No site crosses the threshold.")
                 + f" {_fresh(m)}.")
    blocks = [md(st.answer), kpis([{"label": "Shortages", "value": m.get("shortage_count", 0)},
                                   {"label": "Horizon", "value": f"+{h} d"},
                                   {"label": "Demand P50 (units)", "value": round(sum(r["p50"] for r in fc.get("rows", [])), 1)},
                                   {"label": "Active disruptions", "value": sum(1 for d in m.get("disruptions", []) if d["phase"] == "active")}])]
    if sh:
        blocks.append(table("Projected shortages", [("facility", "Facility"), ("region", "Region"), ("category", "Category"), ("stockout_prob", "Stockout probability"),
                                                    ("on_hand_p50", "On hand P50")], sh[:12], "Weekly reorder-policy simulation, 400 seeded paths."))
    if m.get("regions"):
        blocks.append(chart("region_shortages", "Shortages by region", "bar", [r["region"] for r in m["regions"]],
                            [{"name": "shortages", "data": [r["shortages"] for r in m["regions"]]}], source="global.map_state"))
    s = _s(st)
    target = f"/global?layer=inventory&horizon={h}" + (f"&category={s['category']}" if s.get("category") else "")
    blocks.append(actions([_nav("Open on the global map", target), _q(f"What about the next {60 if h < 60 else 90} days?"), _q("What evidence supports this forecast?")]))
    st.assumptions = (m.get("assumptions") or [])[:4]
    return blocks


def c_demand(st: CaseState) -> list[dict[str, Any]]:
    fc, se, ev = st.inputs.get("forecast") or {}, st.inputs.get("series"), st.inputs.get("evaluation") or {}
    rows = fc.get("rows", [])
    h = fc.get("horizon_days", _h(st, 90))
    mtr = ((ev.get("metrics") or {}).get("demand") or {}).get("by_horizon", {}).get(f"{h}d", {})
    top = rows[0] if rows else None
    st.answer = ((f"Highest predicted removal demand over **+{h} days** for {_scope(st)}: **{top['category']}**, P50 {top['p50']} units "
                  f"(80% interval {top['p10']}–{top['p90']}), about {top['labour_hours_p50']} labour hours. " if top else "No demand rows for that scope. ")
                 + (f"On held-out weeks this model's MAE at {h} days was {mtr.get('mae')} vs {mtr.get('baseline_moving_average', {}).get('mae')} for a moving average; "
                    f"80% interval coverage {_pct(mtr.get('coverage_80'))}. " if mtr else "")
                 + f"{_fresh(fc)}.")
    blocks = [md(st.answer)]
    if rows:
        blocks.append(chart("demand_rank", f"Predicted removals by category (+{h} d, P50 with P10/P90)", "bar", [r["category"] for r in rows[:10]],
                            [{"name": "P10", "data": [r["p10"] for r in rows[:10]]}, {"name": "P50", "data": [r["p50"] for r in rows[:10]]},
                             {"name": "P90", "data": [r["p90"] for r in rows[:10]]}], source="forecast.components"))
        blocks.append(table("Forecast detail", [("category", "Category"), ("p10", "P10"), ("p50", "P50"), ("p90", "P90"), ("labour_hours_p50", "Labour h (P50)"),
                                                ("cost_p50_usd", "Cost P50 (USD)"), ("stockout_sites", "Sites ≥20% stockout")], rows[:12]))
    if se:
        x = [h_["week_start"][5:] for h_ in se["history"]] + [f"+{f['horizon_days']}d" for f in se["forecast"]]
        blocks.append(chart("demand_series", f"{se['category']}: weekly removals and cumulative forecast", "line", x,
                            [{"name": "weekly removals", "data": [h_["removals"] for h_ in se["history"]] + [None] * len(se["forecast"])},
                             {"name": "forecast P10", "data": [None] * len(se["history"]) + [f["p10"] for f in se["forecast"]]},
                             {"name": "forecast P50", "data": [None] * len(se["history"]) + [f["p50"] for f in se["forecast"]]},
                             {"name": "forecast P90", "data": [None] * len(se["history"]) + [f["p90"] for f in se["forecast"]]}], source="forecast.series"))
    st.assumptions = [fc.get("method", ""), "Removal demand is synthetic; intervals are split-conformal 80% intervals from held-out calibration weeks."]
    blocks.append(actions([_nav("Open Component Forecasting", "/forecasting"), _q("Show historical forecast accuracy"), _q("What about Europe only?")]))
    return blocks


def c_supplier_delays(st: CaseState) -> list[dict[str, Any]]:
    m = st.inputs.get("map") or {}
    sup = m.get("suppliers", [])
    worst = sup[0] if sup else None
    st.answer = ((f"Supplier late-delivery risk at **+{m.get('horizon_days')} days**: **{worst['name']}** is highest at {_pct(worst['late_probability'])} "
                  f"(probability an open order arrives after its promised date)" + (f", including +{worst['disruption_days_added']} days from active disruption notices" if worst['disruption_days_added'] else "")
                  + ". " if worst else "No supplier data. ") + f"{_fresh(m)}.")
    return [md(st.answer), table("Supplier delay risk", [("name", "Supplier"), ("region", "Region"), ("late_probability", "Late probability"),
                                                         ("baseline_late_probability", "Without disruptions"), ("disruption_days_added", "Days added"), ("open_orders", "Open orders")], sup),
            chart("supplier_late", "Late-delivery probability by supplier", "bar", [s["name"] for s in sup], [{"name": "late probability", "data": [s["late_probability"] for s in sup]}],
                  source="global.map_state"),
            actions([_nav("Show suppliers on the global map", f"/global?layer=supply&horizon={m.get('horizon_days', 30)}"),
                     _q("What happens to our maintenance schedule if a component supplier experiences a 14-day delivery delay?")])]


def c_delay_impact(st: CaseState) -> list[dict[str, Any]]:
    r, n = st.inputs.get("impact") or {}, st.inputs.get("network") or {}
    sc = {x["scenario"]: x for x in r.get("scenarios", [])}
    worst = (r.get("rows") or [None])[0]
    sup = r.get("supplier", {})
    st.answer = (f"A **{r.get('delay_days', 14):g}-day delay at {sup.get('name', '?')}** affects {len(r.get('affected_categories', []))} component categor(ies): "
                 + ", ".join(c["category"] for c in r.get("affected_categories", [])) + ". "
                 + (f"Over +{r.get('horizon_days')} days, deferred removal-and-replace work rises from {sc['baseline']['deferred_maintenance_hours']} to "
                    f"{sc['delay']['deferred_maintenance_hours']} labour hours. Re-sourcing from an alternate supplier gives {sc['alternate']['deferred_maintenance_hours']} h; "
                    f"transferring regional warehouse stock gives {sc['transfer']['deferred_maintenance_hours']} h. " if sc else "")
                 + (f"Largest single increase: {worst['category']} at {worst['facility']}, stockout probability {_pct(worst['stockout_baseline'])} → {_pct(worst['stockout_delay'])}. " if worst else "")
                 + (f"Network backlog peaks at {n['results']['disruption']['peak_backlog_hours']} h without mitigation vs {n['results']['recovery']['peak_backlog_hours']} h with it. " if n else "")
                 + "Synthetic scenario.")
    blocks = [md(st.answer)]
    if sc:
        blocks.append(chart("delay_scen", "Deferred maintenance hours by planning option", "bar", list(sc), [{"name": "deferred hours", "data": [v["deferred_maintenance_hours"] for v in sc.values()]}],
                            source="supply.delay_impact"))
    if r.get("rows"):
        blocks.append(table("Most affected sites", [("facility", "Facility"), ("category", "Category"), ("stockout_baseline", "Stockout baseline"), ("stockout_delay", "With delay"),
                                                    ("stockout_alternate", "Alternate supplier"), ("stockout_transfer", "Stock transfer"), ("deferred_hours_delay", "Extra deferred h")], r["rows"][:10]))
    if n:
        res = n["results"]
        blocks.append(chart("delay_backlog", "Network backlog (P50 hours): baseline vs disruption vs recovery", "line", [f"W{w}" for w in n["weeks"]],
                            [{"name": k, "data": res[k]["backlog_p50"]} for k in ("baseline", "disruption", "recovery")], source="resilience.simulate"))
    st.assumptions = (r.get("assumptions") or [])[:5]
    blocks.append(actions([_nav("See it on the global map", "/global?layer=supply&horizon=60"), _nav("Open Supply Chain Intelligence", f"/supply?supplier={sup.get('id', 'S1')}")]))
    return blocks


def c_degradation(st: CaseState) -> list[dict[str, Any]]:
    t = st.inputs.get("twin") or {}
    u = t.get("unit", {})
    if not u:
        st.answer = "No matching component twin was found."
        return [md(st.answer)]
    tel = [x for x in t.get("telemetry", []) if x.get("health") is not None]
    st.answer = (f"**{u['id']}** ({u['category']}, {u['facility']}): health index {u.get('last_health')} after {u.get('age_weeks')} weeks in service, "
                 f"changing {u.get('health_slope_8w')} per week over the last 8 readings. "
                 + (f"Estimated remaining useful life {u.get('rul_combined')} weeks (category survival model P10–P90: {u.get('rul_p10')}–{u.get('rul_p90')} weeks). " if u.get("rul_combined") is not None else "")
                 + (f"Failure-risk model: {_pct(u.get('risk_30d'))} probability of removal within 30 days. " if u.get("risk_30d") is not None else "")
                 + f"{t['data_quality']['missing_health_readings']} of {t['data_quality']['weeks']} weekly health readings are missing. Advisory only; not an airworthiness determination.")
    return [md(st.answer),
            chart("twin_health", f"{u['id']}: health and vibration (last 26 weeks)", "line", [str(x["week"]) for x in tel],
                  [{"name": "health index", "data": [x["health"] for x in tel]}, {"name": "vibration", "data": [x["vibration"] for x in tel]}],
                  source="twin.unit", mark_line={"y": 0.2, "label": "removal threshold"}),
            table("Why it was flagged", [("reason", "Reason")], [{"reason": r} for r in t.get("flag_reasons", [])] or [{"reason": "No flag rule fired."}]),
            table("Documents an engineer should review", [("doc", "Document")], [{"doc": d} for d in t.get("documents_to_review", [])]),
            actions([_nav("Open the digital twin", f"/twin?unit={u['id']}"), _q("What evidence supports this forecast?")])]


def c_resilience(st: CaseState) -> list[dict[str, Any]]:
    r = st.inputs.get("sim") or {}
    if not r:
        st.answer = "The simulation did not return a result."
        return [md(st.answer)]
    res = r["results"]
    st.answer = (f"**{r['label']}** (synthetic scenario, params {r['params']}): peak backlog {res['baseline']['peak_backlog_hours']} h baseline → "
                 f"{res['disruption']['peak_backlog_hours']} h disrupted → {res['recovery']['peak_backlog_hours']} h with mitigation. "
                 + (f"Backlog returns to baseline {res['disruption']['recovery_weeks_after_disruption']} week(s) after the disruption without mitigation"
                    + (f" and {res['recovery']['recovery_weeks_after_disruption']} with it. " if res['recovery']['recovery_weeks_after_disruption'] is not None else ". ")
                    if res["disruption"]["recovery_weeks_after_disruption"] is not None else "Backlog does not recover within 13 weeks. ")
                 + f"Inventory availability at 90 days: {_pct(res['baseline']['inventory_availability']['90'])} → {_pct(res['disruption']['inventory_availability']['90'])}.")
    st.assumptions = r.get("assumptions", [])[:5]
    return [md(st.answer), chart("res_backlog", "Backlog P50 (hours)", "line", [f"W{w}" for w in r["weeks"]],
                                 [{"name": k, "data": res[k]["backlog_p50"]} for k in ("baseline", "disruption", "recovery")], source="resilience.simulate"),
            kpis([{"label": f"{k} cost P50", "value": f"${res[k]['cost_p50_usd']:,.0f}"} for k in ("baseline", "disruption", "recovery")]),
            actions([_nav("Open Operational Resilience", "/resilience")])]


def c_evidence(st: CaseState) -> list[dict[str, Any]]:
    ev, rc = st.inputs.get("evaluation") or {}, st.inputs.get("recall") or {}
    m = ev.get("metrics", {})
    d = (m.get("demand") or {}).get("by_horizon", {})
    prev = next((r for r in rc.get("previous_runs", []) if r["workflow"] in ("demand_forecast", "global_shortages", "supply_delay_impact")), None)
    st.answer = ("The forecast rests on four kinds of evidence: (1) **held-out accuracy**: on the last 26 weeks, never used for fitting, demand MAE at 30 days "
                 f"was {d.get('30d', {}).get('mae')} vs {d.get('30d', {}).get('baseline_moving_average', {}).get('mae')} for a moving average, with 80% interval coverage "
                 f"{_pct(d.get('30d', {}).get('coverage_80'))}; (2) **calibration**: failure-risk ECE {m.get('failure_risk_30d', {}).get('calibration', {}).get('ece')}, "
                 f"Brier {m.get('failure_risk_30d', {}).get('calibration', {}).get('brier')}; (3) **data**: {ev.get('freshness', {}).get('dataset')}, as of "
                 f"{ev.get('freshness', {}).get('data_as_of')}; (4) **stated assumptions** listed below. "
                 + (f"Your previous forecast question was \"{prev['query']}\"." if prev else "") + " All of it is synthetic demonstration data.")
    rows = [{"task": k, "method": v.get("method", "")[:90], "split": v.get("split", "")[:90]} for k, v in m.items()]
    st.assumptions = ["Temporal splits only; no future weeks in training.", "Intervals are split-conformal (demand) or survival-model quantiles (RUL).",
                      "Interval coverage falls below 80% at 60-90 days on held-out data; treat long horizons with more caution."]
    return [md(st.answer), table("Models and evaluation design", [("task", "Task"), ("method", "Method"), ("split", "Split")], rows),
            chart("cov", "Demand interval coverage by horizon (target 80%)", "bar", list(d), [{"name": "coverage", "data": [v["coverage_80"] for v in d.values()]}],
                  source="forecast.evaluation", mark_line={"y": 0.8, "label": "target"}),
            actions([_nav("Open Component Forecasting · accuracy", "/forecasting?tab=accuracy")])]


def c_accuracy(st: CaseState) -> list[dict[str, Any]]:
    ev = st.inputs.get("evaluation") or {}
    m, bt = ev.get("metrics", {}), ev.get("backtest", [])
    d = (m.get("demand") or {}).get("by_horizon", {})
    st.answer = ("Historical accuracy on held-out data (synthetic): demand MAE "
                 + ", ".join(f"{k} {v['mae']} (moving average {v['baseline_moving_average']['mae']})" for k, v in d.items())
                 + f". Failure-risk classifier F1 {m.get('failure_risk_30d', {}).get('model_at_0.5', {}).get('f1')} vs {m.get('failure_risk_30d', {}).get('baseline_health_below_0.35', {}).get('f1')} "
                 f"for a health-threshold rule. Anomaly detection: IsolationForest F1 {m.get('anomaly', {}).get('isolation_forest', {}).get('f1')}, simple z-score rule "
                 f"{m.get('anomaly', {}).get('baseline_zscore_gt3', {}).get('f1')} — the simpler rule is better on this data. Lead time MAE {m.get('lead_time', {}).get('mae')} days "
                 f"vs {m.get('lead_time', {}).get('baseline_supplier_median', {}).get('mae')} for supplier medians.")
    return [md(st.answer),
            chart("backtest", "7-day backtest: actual vs forecast (all hubs, weekly)", "line", [b["week_start"][5:] for b in bt],
                  [{"name": "actual", "data": [b["actual_total"] for b in bt]}, {"name": "P50", "data": [b["p50_total"] for b in bt]},
                   {"name": "P10", "data": [b["p10_total"] for b in bt]}, {"name": "P90", "data": [b["p90_total"] for b in bt]}], source="forecast.evaluation"),
            chart("mae_h", "Demand MAE by horizon: model vs baselines", "bar", list(d),
                  [{"name": "model", "data": [v["mae"] for v in d.values()]}, {"name": "moving average", "data": [v["baseline_moving_average"]["mae"] for v in d.values()]},
                   {"name": "seasonal naive", "data": [v["baseline_seasonal_naive"]["mae"] for v in d.values()]}], source="forecast.evaluation"),
            actions([_nav("Open the accuracy dashboard", "/forecasting?tab=accuracy")])]


def c_trace(st: CaseState) -> list[dict[str, Any]]:
    t = st.inputs.get("trace") or {}
    run = t.get("run")
    if not run:
        st.answer = "There is no earlier investigation to show yet. Ask a question first, then ask for the agent execution graph."
        return [md(st.answer)]
    evs = t.get("events", [])
    agents = sorted({e["agent"] for e in evs})
    st.answer = (f"Execution of your previous request \"{run['query']}\" ({run['workflow']}, {run['status']}): {len(evs)} recorded events across "
                 f"{len(agents)} agents: {', '.join(agents)}. These are the events written while it ran; nothing was re-run.")
    return [md(st.answer), {"type": "agent_trace", "graph": t.get("graph"), "events": evs, "run_id": run["id"], "plan": t.get("plan")},
            table("Events", [("step", "Step"), ("agent", "Agent"), ("status", "Status"), ("attempt", "Attempt"), ("duration_ms", "ms")], evs[-20:]),
            actions([_nav("Open the Control Tower", f"/control-tower?run={run['id']}")])]


def c_recall(st: CaseState) -> list[dict[str, Any]]:
    r = st.inputs.get("recall") or {}
    prev = r.get("previous_runs", [])
    if not prev:
        st.answer = "I have no earlier investigations stored for you yet."
        return [md(st.answer)]
    p = prev[0]
    st.answer = (f"Your previous investigation was **\"{p['query']}\"** ({p['workflow'].replace('_', ' ')}, {p['status']}, {p['created'][:16].replace('T', ' ')}). "
                 + (f"The answer began: {p['answer_excerpt'][:300]}" if p.get("answer_excerpt") else "")
                 + " Conversations are stored locally in SQLite and you can delete them from the chat history panel.")
    return [md(st.answer), table("Earlier investigations", [("query", "Question"), ("workflow", "Workflow"), ("status", "Status"), ("created", "When")], prev[:8])]


def c_visual(st: CaseState) -> list[dict[str, Any]]:
    v = st.inputs.get("visual") or {}
    c, e = v.get("capabilities", {}), v.get("evaluation", {})
    st.answer = (c.get("statement", "") + f" On the labelled synthetic set ({e.get('n')} frames) the classical baseline scored precision {e.get('precision')}, "
                 f"recall {e.get('recall')}, F1 {e.get('f1')}; false-positive rate {_pct(e.get('false_positive_rate'))}, false-negative rate {_pct(e.get('false_negative_rate'))}. "
                 "Upload prerecorded, authorized footage in the Airspace Safety Lab; it is analysed frame by frame for civilian safety research only.")
    return [md(st.answer), table("Capabilities", [("k", "Item"), ("v", "Value")], [
        {"k": "Local Qwen", "v": f"{c.get('qwen', {}).get('model') or 'not found'} ({c.get('qwen', {}).get('modality')})"},
        {"k": "Vision model", "v": c.get("vision_model", {}).get("model") or "none installed"}, {"k": "Method that will run", "v": c.get("default_method")},
        {"k": "Video frame sampling (ffmpeg)", "v": "available" if c.get("ffmpeg") else "not installed"}]),
        table("Boundaries", [("b", "This module does not")], [{"b": b} for b in c.get("boundaries", [])]),
        actions([_nav("Open the Airspace Safety Lab", "/airspace")])]


def c_change(st: CaseState) -> list[dict[str, Any]]:
    r = st.inputs.get("change") or {}
    if r.get("error"):
        st.answer = r["error"]
        return [md(st.answer)]
    st.answer = (f"Changing **{', '.join(r['resolved'])}** reaches {len(r['affected_modules'])} module(s) through imports, {len(r['affected_routes'])} API route(s) and "
                 f"{len(r['affected_frontend'])} frontend file(s). Run {len(r['recommended_tests'])} test file(s) first: "
                 + ", ".join(t["test"] for t in r["recommended_tests"][:6]) + f". Risk: **{r['risk']}**. "
                 + (f"Requirements touched: {', '.join(q['id'] for q in r['requirements'])}" + (" (some lack verification evidence)." if any(q['status'] != 'traced' for q in r['requirements']) else ".") if r["requirements"] else "")
                 + " Static import analysis, not line coverage; not a certification argument.")
    return [md(st.answer), table("Affected modules", [("module", "Module"), ("distance", "Hops"), ("path", "File")], r["affected_modules"][:15]),
            table("Recommended regression tests", [("test", "Test file"), ("distance", "Hops"), ("via", "Via")], [{**t, "via": ", ".join(t["via"])} for t in r["recommended_tests"]]),
            actions([_nav("Open Software Change Impact", f"/change-impact?target={r['resolved'][0]}")])]


HARNESS_COMPOSERS = {"global_shortages": c_shortages, "demand_forecast": c_demand, "supplier_delays": c_supplier_delays, "supply_delay_impact": c_delay_impact,
                     "component_degradation": c_degradation, "resilience_scenario": c_resilience, "forecast_evidence": c_evidence, "forecast_accuracy": c_accuracy,
                     "agent_trace": c_trace, "memory_recall": c_recall, "visual_analysis": c_visual, "change_impact": c_change}
