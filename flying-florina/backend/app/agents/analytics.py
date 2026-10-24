"""Agents for analytics, simulation, governance, legacy, bridge and executive workflows."""

from __future__ import annotations

import statistics
from typing import Any

from app.agents.common import call_tool
from app.core import policy
from app.core.config import SEED
from app.integrations.legacy import xray
from app.integrations.mcp import bridge
from app.integrations.mcp.registry import invocation_count
from app.services import data
from app.simulation.engine import DelayScenarioInputs, RoiInputs, compare_delays, roi
from app.workflows.engine import CaseState, StepContext, StepHalt


def precheck(action: str, label: str = "INTERNAL"):
    def step(state: CaseState, ctx: StepContext) -> dict[str, Any]:
        d = policy.evaluate(ctx.human, policy.PolicyRequest(action=action, resource=f"workflow:{state.workflow}", label=label, run_id=state.run_id,
                                                            extra={"require_home_org": True}))
        with ctx.lock:
            state.policy_decisions.append(d.as_dict())
        if not d.allowed:
            raise StepHalt("denied", f"{d.reason} ({d.policy_id})")
        return {"summary": f"ALLOW {action} for {ctx.human.role} ({d.policy_id}).", "decision": d.as_dict()}
    return step


# ---------------------------------------------------------------- downtime analysis

def downtime_trend(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    months = data.downtime_by_month()
    asked = state.intent.get("entities", {}).get("months") or ["october"]
    names = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    target_num = names.index(asked[0]) + 1
    candidates = [m for m in months if int(m["month"][5:]) == target_num]
    if not candidates:
        raise StepHalt("needs_clarification", f"No synthetic data for {asked[0].title()}.")
    target = candidates[-1]
    prior = [m for m in months if m["month"] < target["month"]][-12:]
    with ctx.lock:
        state.inputs.update(months=months, target=target, prior=prior)
    base = statistics.mean(m["hours_per_aircraft_day"] for m in prior)
    return {"summary": f"{target['month']}: {target['hours_per_aircraft_day']:.3f} downtime h per aircraft-day vs trailing-12 mean "
                       f"{base:.3f} ({(target['hours_per_aircraft_day'] / base - 1) * 100:+.0f}%). Partial month normalized ({target['days_observed']} days).",
            "evidence": [{"kind": "dataset", "ref": "maintenance_events", "detail": "monthly aggregation"}]}


def downtime_causes(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    target = state.inputs["target"]
    prior = state.inputs["prior"]
    cur = {c["cause"]: c for c in data.downtime_causes(target["month"])}
    base: dict[str, list[float]] = {}
    for m in prior:
        for c in data.downtime_causes(m["month"]):
            base.setdefault(c["cause"], []).append(c["hours"] / m["days_observed"])
    rows = []
    for cause in sorted(set(cur) | set(base)):
        now_rate = cur.get(cause, {}).get("hours", 0) / target["days_observed"]
        hist = base.get(cause, [0])
        mean = statistics.mean(hist)
        rows.append({"cause": cause, "hours": cur.get(cause, {}).get("hours", 0), "events": cur.get(cause, {}).get("events", 0),
                     "hours_per_day": round(now_rate, 1), "baseline_hours_per_day": round(mean, 1),
                     "delta_per_day": round(now_rate - mean, 1), "z": round(data.zscore(hist, now_rate), 1)})
    rows.sort(key=lambda r: -r["delta_per_day"])
    sup = {s["id"]: s for s in data.supplier_reliability()}
    with ctx.lock:
        state.inputs.update(cause_rows=rows, suppliers=sup)
    top = rows[:2]
    return {"summary": "Largest increases: " + "; ".join(f"{r['cause']} {r['delta_per_day']:+.1f} h/day (z={r['z']})" for r in top) + ".",
            "evidence": [{"kind": "dataset", "ref": "maintenance_events.cause_category", "detail": "planner-recorded cause"}]}


def downtime_stats(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    target = state.inputs["target"]
    cur = data.event_downtimes(target["month"])
    prior_vals = [v for m in state.inputs["prior"] for v in data.event_downtimes(m["month"])]
    mean_c, lo_c, hi_c = data.bootstrap_ci(cur, SEED)
    mean_p, lo_p, hi_p = data.bootstrap_ci(prior_vals, SEED + 1)
    with ctx.lock:
        state.inputs["ci"] = {"current": [round(mean_c, 1), round(lo_c, 1), round(hi_c, 1)], "prior": [round(mean_p, 1), round(lo_p, 1), round(hi_p, 1)],
                              "n_current": len(cur), "n_prior": len(prior_vals)}
    overlap = lo_c <= hi_p
    return {"summary": f"Mean downtime per event {mean_c:.1f} h (95% bootstrap CI {lo_c:.1f}-{hi_c:.1f}, n={len(cur)}) vs prior "
                       f"{mean_p:.1f} h ({lo_p:.1f}-{hi_p:.1f}, n={len(prior_vals)}). Intervals {'overlap' if overlap else 'do not overlap'}.",
            "method": "Seeded bootstrap, 1000 resamples"}


# ---------------------------------------------------------------- scenario simulation

def scenario_inputs(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ents = state.intent.get("entities", {})
    hours = ents.get("hours") or []
    delays = sorted(set(hours)) if hours else [24, 48]
    if len(delays) == 1:
        delays = sorted({delays[0], delays[0] * 2})
    overrides = ctx.options.get("simulation", {}) or {}
    inp = DelayScenarioInputs(part_number=(ents.get("parts") or ["P-7731"])[0], delays_hours=delays, **{
        k: v for k, v in overrides.items() if k in DelayScenarioInputs.model_fields and k not in ("part_number",)})
    if "delays_hours" in overrides:
        inp = inp.model_copy(update={"delays_hours": overrides["delays_hours"]})
    with ctx.lock:
        state.inputs["sim_inputs"] = inp.model_dump()
    return {"summary": f"Scenarios {inp.delays_hours} h for {inp.part_number} at {inp.base}; cost assumption ${inp.downtime_cost_per_hour_low:,.0f}-${inp.downtime_cost_per_hour_high:,.0f}/h."}


def scenario_run(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    res = compare_delays(DelayScenarioInputs(**state.inputs["sim_inputs"]))
    with ctx.lock:
        state.inputs["sim"] = res
    s = res["scenarios"]
    return {"summary": "; ".join(f"{x['delay_hours']} h delay -> {x['downtime_hours']} h downtime (P90 {x['monte_carlo']['p90_hours'] if x['monte_carlo'] else '-'} h)" for x in s),
            "evidence": [{"kind": "simulation", "ref": res["version"], "detail": f"seed {res['seed']}"}]}


# ---------------------------------------------------------------- governance

def export_attempt(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    """Graph 3: the requested export is evaluated by policy *before* the tool can run."""
    dest = state.intent.get("destination", "external_email")
    before = invocation_count("records.export_email")
    _, rec = call_tool(state, ctx, "Security & Governance Agent", "records.export_email",
                       {"destination": dest, "record_set": "restricted maintenance records"})
    after = invocation_count("records.export_email")
    with ctx.lock:
        state.inputs["export"] = {"record": rec, "tool_invocations_before": before, "tool_invocations_after": after, "destination": dest}
    d = rec.get("decision", {})
    if rec["status"] == "denied":
        raise StepHalt("denied", f"DENY {d.get('policy_id')}: {d.get('reason')} Tool executions: {after - before}.")
    return {"summary": "Export permitted (unexpected in demo)."}


def governance_summary(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    denied = policy.list_decisions("DENY", limit=500)
    by_policy: dict[str, int] = {}
    for d in denied:
        by_policy[d["policy_id"]] = by_policy.get(d["policy_id"], 0) + 1
    with ctx.lock:
        state.inputs["denied"] = denied
        state.inputs["by_policy"] = by_policy
    return {"summary": f"{len(denied)} denied decisions across {len(by_policy)} policies."}


# ---------------------------------------------------------------- documents

def doc_freshness(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    from app.core.policy import label_allows

    docs = data.document_freshness()
    visible = [d for d in docs if label_allows(ctx.human, d["classification"])[0]]
    with ctx.lock:
        state.inputs["docs"] = visible
        state.inputs["docs_withheld"] = len(docs) - len(visible)
    issues = [d for d in visible if d["issues"]]
    return {"summary": f"{len(issues)} of {len(visible)} visible documents have freshness or provenance issues; {len(docs) - len(visible)} withheld by classification."}


# ---------------------------------------------------------------- legacy (graph 2)

def legacy_import(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ls = xray.landscape()
    with ctx.lock:
        state.inputs["landscape"] = {k: v for k, v in ls.items() if k != "parsed"}
    return {"summary": f"Parsed {len(ls['sources'])} metadata sources (bundled fixtures + uploads), no code executed.",
            "evidence": [{"kind": "metadata", "ref": s["source"], "detail": s["kind"]} for s in ls["sources"]]}


def legacy_graph(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ls = state.inputs["landscape"]
    return {"summary": f"{ls['summary']['systems']} systems, {ls['summary']['tables']} tables, {ls['summary']['apis']} APIs, "
                       f"{len(ls['edges'])} edges; hotspots: {', '.join(h['system'] for h in ls['hotspots'][:3])}."}


def legacy_risks(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ls = state.inputs["landscape"]
    return {"summary": f"{ls['summary']['high']} high and {ls['summary']['medium']} medium findings; {len(ls['unknowns'])} explicit unknowns."}


def legacy_options(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    recs = xray.recommendations(state.inputs["landscape"])
    with ctx.lock:
        state.inputs["recommendations"] = recs
    return {"summary": f"{sum(r['applies'] for r in recs)} applicable patterns, {sum(not r['applies'] for r in recs)} conditional."}


def legacy_target(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    with ctx.lock:
        state.inputs["roadmap"] = xray.roadmap()
    return {"summary": "Target: agents -> MCP -> policy gateway -> typed read-only adapters -> legacy (unchanged core)."}


def adapter_preview(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    d = policy.evaluate(ctx.human, policy.PolicyRequest(action="generate_code", resource="bridge:part_availability", label="INTERNAL", run_id=state.run_id))
    with ctx.lock:
        state.policy_decisions.append(d.as_dict())
    if not d.allowed:
        return {"summary": f"Adapter generation not permitted for role {ctx.human.role} ({d.policy_id}); recommendations still shown."}
    b = bridge.generate(ctx.human.id)
    with ctx.lock:
        state.inputs["bundle"] = {k: b[k] for k in ("bundle_id", "files", "static_checks", "mapping", "status")}
        state.generated_artifacts.append({"kind": "adapter_bundle", "id": b["bundle_id"], "title": "Read-only part availability adapter + MCP tool"})
    return {"summary": f"Generated bundle {b['bundle_id']} ({len(b['files'])} files); not executed.", "tools": ["bridge.generate"]}


def contract_static(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    b = state.inputs.get("bundle")
    if not b:
        return {"summary": "No bundle generated."}
    ok = sum(c["passed"] for c in b["static_checks"])
    return {"summary": f"Static contract/security checks {ok}/{len(b['static_checks'])} passed. Runtime tests run on explicit request in Bridge Studio."}


def security_review(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ls = state.inputs["landscape"]
    high = [f for f in ls["findings"] if f["severity"] == "high"]
    return {"summary": "Security review: " + ("; ".join(f"{f['kind']} at {f['object']}" for f in high) or "no high findings") + "."}


# ---------------------------------------------------------------- bridge workflow

def bridge_discover(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    with ctx.lock:
        state.inputs["sources"] = bridge.DISCOVERED_SOURCES
        state.inputs["capability"] = bridge.CAPABILITIES["part_availability"]
    return {"summary": f"{len(bridge.DISCOVERED_SOURCES)} candidate sources; selected read-only capability get_part_availability(part_number)."}


def bridge_generate(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    b = bridge.generate(ctx.human.id)
    with ctx.lock:
        state.inputs["bundle"] = {k: b[k] for k in ("bundle_id", "files", "static_checks", "mapping", "status", "preview")}
        state.generated_artifacts.append({"kind": "adapter_bundle", "id": b["bundle_id"], "title": "Read-only part availability adapter + MCP tool"})
    return {"summary": f"Generated {b['bundle_id']}: FastAPI adapter, Pydantic models, MCP server, tests, OpenAPI, threat model."}


# ---------------------------------------------------------------- executive

def exec_findings(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    fleet = data.fleet_overview()
    months = data.downtime_by_month()
    ls = xray.landscape()
    denied = len(policy.list_decisions("DENY", limit=1000))
    with ctx.lock:
        state.inputs["exec"] = {"fleet": {k: fleet[k] for k in ("total_aircraft", "available_pct", "aog_count", "open_work_orders", "mean_health_score")},
                                "downtime_last": months[-1], "downtime_prev": months[-2],
                                "legacy": ls["summary"], "hotspots": ls["hotspots"], "denied_actions": denied,
                                "incidents": len(data.incidents())}
        state.inputs["roadmap"] = xray.roadmap()
        state.inputs["recommendations"] = xray.recommendations(ls)
    return {"summary": "Findings gathered from fleet, downtime, legacy and governance read models (all synthetic)."}


def exec_roi(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    r = roi(RoiInputs(**(ctx.options.get("roi") or {})))
    with ctx.lock:
        state.inputs["roi"] = r
    return {"summary": f"Modeled annual benefit ${r['annual_benefit']['low']['total']:,}-${r['annual_benefit']['high']['total']:,}; first-year cost ${r['first_year_cost']:,} (assumptions, not a promise)."}


def exec_report(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    from app.reports import generator

    d = policy.evaluate(ctx.human, policy.PolicyRequest(action="export", resource="report:executive_brief", label="INTERNAL",
                                                        destination="local_download", run_id=state.run_id))
    with ctx.lock:
        state.policy_decisions.append(d.as_dict())
    if not d.allowed:
        return {"summary": f"Brief not generated for this role ({d.policy_id})."}
    reps = [generator.generate(ctx.human, "executive_brief", fmt, context=state.inputs) for fmt in ("pdf", "md", "html")]
    with ctx.lock:
        for r in reps:
            state.generated_artifacts.append({"kind": "report", "id": r["id"], "title": r["title"], "fmt": r["fmt"]})
    return {"summary": f"Executive brief generated as PDF, Markdown and HTML ({', '.join(r['id'] for r in reps)})."}


# ---------------------------------------------------------------- parts / fleet / quality

def parts_overview(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    pn = (state.intent.get("entities", {}).get("parts") or [None])[0]
    if pn:
        res, _ = call_tool(state, ctx, "Parts Agent", "parts.check_availability", {"part_number": pn})
        with ctx.lock:
            state.inputs["part_detail"] = res
    with ctx.lock:
        state.inputs["critical"] = data.critical_stock()
        state.inputs["suppliers_rel"] = data.supplier_reliability()
    return {"summary": f"{len(state.inputs['critical'])} critical/high parts at or below 2 verified units; supplier reliability computed from {sum(s['deliveries'] for s in state.inputs['suppliers_rel'])} synthetic deliveries."}


def fleet_summary(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    f = data.fleet_overview()
    with ctx.lock:
        state.inputs["fleet"] = f
    return {"summary": f"{f['total_aircraft']} aircraft, {f['available_pct']}% in service, {f['aog_count']} AOG, {len(f['anomaly_aircraft'])} above fictional vibration threshold."}


def quality_ncr(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    sup = data.supplier_reliability()
    worst = min(sup, key=lambda s: s["on_time_pct"] or 100)
    res, _ = call_tool(state, ctx, "Compliance Agent", "docs.search", {"query": "nonconformance corrective action supplier quality", "limit": 5})
    with ctx.lock:
        state.inputs["quality"] = {"supplier": worst, "docs": res["results"] if res else []}
        state.retrieved_docs = res["results"] if res else []
    return {"summary": f"NCR candidate: supplier {worst['id']} on-time {worst['on_time_pct']}%, recent slip {worst['recent_avg_slip_days']} d. CAPA draft requires quality approval."}
