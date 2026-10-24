"""Reporting Agent: turns a finished CaseState into workspace blocks.

Every number shown is read from the state the agents produced (which in turn
came from the synthetic read models). Nothing here invents values.
"""

from __future__ import annotations

from typing import Any

from app.agents.common import actions, assumptions, chart, citations, kpis, md, table, warnings
from app.integrations.mcp.registry import invocation_count
from app.seed.generator import DEMO_VIBRATION_THRESHOLD
from app.workflows.engine import CaseState
from app.workflows.intent import SUGGESTIONS


def compose(state: CaseState) -> None:
    fn = COMPOSERS.get(state.workflow, _generic)
    blocks: list[dict[str, Any]] = []
    if state.status in ("denied", "needs_clarification") and state.workflow != "data_export":
        reason = next((e["error"] for e in state.errors), "") or (state.warnings[-1] if state.warnings else "")
        halted = [d for d in state.policy_decisions if d["decision"] == "DENY"]
        state.answer = (f"**Request stopped: {state.status.replace('_', ' ')}.** "
                        + (halted[-1]["reason"] + f" ({halted[-1]['policy_id']})" if halted else reason))
        blocks = [md(state.answer)]
        if state.status == "needs_clarification":
            blocks.append({"type": "clarify", "suggestions": SUGGESTIONS})
    else:
        blocks = fn(state)
    if state.retrieved_docs and not any(b["type"] == "citations" for b in blocks):
        blocks.append(citations(state.retrieved_docs))
    if state.warnings:
        blocks.append(warnings(sorted(set(state.warnings))))
    if state.assumptions:
        blocks.append(assumptions(state.assumptions))
    decisions = state.policy_decisions
    if decisions:
        blocks.append({"type": "policy", "decisions": decisions[-25:], "allowed": sum(d["decision"] == "ALLOW" for d in decisions),
                       "denied": sum(d["decision"] == "DENY" for d in decisions)})
    if state.approvals:
        blocks.append({"type": "approval", "items": state.approvals})
    if state.generated_artifacts:
        blocks.append({"type": "artifacts", "items": state.generated_artifacts})
    state.workspace = blocks


def _generic(state: CaseState) -> list[dict[str, Any]]:
    state.answer = state.answer or "No composer for this workflow."
    return [md(state.answer)]


def _maintenance(state: CaseState) -> list[dict[str, Any]]:
    i = state.inputs
    ac = i.get("aircraft_id", "?")
    s = i.get("telemetry_stats")
    hyps = i.get("hypotheses", [])
    opts = i.get("options", [])
    best = next((o for o in opts if o.get("rank") == 1), None)
    comp = i.get("compliance", [])
    lines = [f"**{ac} ({i.get('aircraft_type', '')}, {i.get('base', '')}) - investigation summary (synthetic data).**", ""]
    if s:
        lines.append(f"- Vibration index 7-day mean **{s['recent_7d_mean']}** vs own baseline {s['baseline_mean']} (z = {s['recent_z']}); "
                     f"rising {s['days_rising']} consecutive days; {s['days_over_demo_threshold']} days at or above the fictional demo threshold {DEMO_VIBRATION_THRESHOLD}.")
        lines.append(f"- EGT delta moved from {s['egt_delta_baseline']} to {s['egt_delta_recent']} C; {len(s['missing_days'])} missing reading(s) treated as data-quality gaps.")
    else:
        lines.append("- Telemetry was withheld for this persona; conclusions are limited.")
    if hyps:
        lines.append("- Hypotheses (not a diagnosis): " + "; ".join(f"**{h['id']}** {h['hypothesis']} ({h['likelihood']})" for h in hyps) + ".")
    if best:
        lines.append(f"- Fastest compliant recovery: **{best['option']}** - est. downtime {best['est_downtime_hours']} h from now, slot {best['slot_start']}.")
    if comp:
        lines.append(f"- Evidence sufficiency: {sum(c['ok'] for c in comp)}/{len(comp)} checks. Return to service remains a certifying human's decision (DOC-014).")
    if state.approvals:
        lines.append(f"- Draft work order awaits approval **{state.approvals[0]['id']}** by a different qualified approver; nothing has been written.")
    state.answer = "\n".join(lines)
    state.assumptions = ["Thresholds, procedures and transfer times are fictional demo values.",
                         "Hypothesis ranking is qualitative and based only on permitted synthetic evidence.",
                         "Inventory: most recent physical count wins; critical counts older than 30 days are unverified (fictional DOC-009)."]
    blocks: list[dict[str, Any]] = [md(state.answer)]
    if s:
        blocks.append(kpis([
            {"label": "Vibration 7d mean", "value": s["recent_7d_mean"], "tone": "red" if s["recent_7d_mean"] >= DEMO_VIBRATION_THRESHOLD else "amber"},
            {"label": "z vs baseline", "value": s["recent_z"]},
            {"label": "Days rising", "value": s["days_rising"]},
            {"label": "Missing readings", "value": len(s["missing_days"]), "tone": "amber" if s["missing_days"] else "teal"},
            {"label": "Compliant options", "value": sum(1 for o in opts if o.get("rank"))},
        ]))
        ser = i.get("telemetry_series", [])
        blocks.append(chart("vibration", f"{ac} vibration index vs fleet mean (90 days)", "line", [r["day"] for r in ser],
                            [{"name": ac, "data": [r["vibration_index"] for r in ser]},
                             {"name": "Fleet mean", "data": [r["fleet_mean"] for r in ser]}],
                            caption="Gaps are missing readings. Dashed line: fictional demo threshold, not a maintenance limit.",
                            source="sensor_readings (synthetic)", mark_line={"y": DEMO_VIBRATION_THRESHOLD, "label": "Demo threshold"}, y_label="index"))
    if hyps:
        blocks.append(table("Diagnostic hypotheses (evidence, not conclusions)",
                            [("id", "ID"), ("hypothesis", "Hypothesis"), ("likelihood", "Relative likelihood"), ("supporting", "Supporting"),
                             ("contradicting", "Contradicting"), ("reference_required", "Authoritative reference required")],
                            [{**h, "supporting": "; ".join(h["supporting"]) or "-", "contradicting": "; ".join(h["contradicting"]) or "-"} for h in hyps]))
    parts_ = i.get("parts", {}).get("primary")
    if parts_:
        blocks.append(table(f"{i.get('part_number')} availability reconciled across systems",
                            [("location", "Location"), ("verified_qty", "Verified qty"), ("reported_qty_by_source", "Reported by source"),
                             ("last_verified", "Last count"), ("note", "Note")],
                            [{**a, "reported_qty_by_source": ", ".join(f"{k}: {v}" for k, v in a["reported_qty_by_source"].items())} for a in parts_["availability"]]))
    if opts:
        blocks.append(table("Recovery options (compliant first, ranked by modeled downtime)",
                            [("rank", "Rank"), ("option", "Option"), ("part_number", "Part"), ("est_downtime_hours", "Est. downtime h"),
                             ("slot_start", "Slot"), ("compliant", "Compliant"), ("notes", "Notes")],
                            [{**o, "notes": "; ".join(o["notes"]), "rank": o.get("rank", "-")} for o in opts]))
        ranked = [o for o in opts if o.get("rank")]
        blocks.append(chart("options", "Modeled downtime by compliant option", "bar", [o["option"] for o in ranked],
                            [{"name": "Est. downtime (h)", "data": [o["est_downtime_hours"] for o in ranked]}], source="Planner + Parts agents"))
    roster = i.get("roster")
    if roster:
        blocks.append(table("Technician coverage (unexpired qualifications only)", [("id", "ID"), ("name", "Name"), ("shift", "Shift"), ("matched", "Qualifications")],
                            [{**t, "matched": ", ".join(t["matched"])} for t in roster["qualified"]],
                            caption=f"Excluded for expired qualification: {', '.join(t['id'] for t in roster['expired']) or 'none'}"))
    if comp:
        blocks.append(table("Compliance evidence checklist (not a certification)", [("check", "Check"), ("ok", "OK"), ("evidence", "Evidence")], comp))
    if "scenario_run" in state.task_results:
        blocks += _scenario_blocks(state)
    blocks.append(actions([{"label": "Open approval queue", "kind": "navigate", "target": "/trust?tab=approvals"},
                           {"label": "Compare delay scenarios", "kind": "query", "target": "Compare 24-hour and 48-hour delay scenarios for a replacement part."},
                           {"label": "Export workspace (PDF)", "kind": "export", "target": "pdf"}]))
    return blocks


def _scenario_blocks(state: CaseState) -> list[dict[str, Any]]:
    sim = state.inputs.get("sim")
    if not sim:
        return []
    sc = sim["scenarios"]
    blocks = [
        chart("scenario", "Modeled downtime by part delay", "bar", [f"{s['delay_hours']} h" for s in sc],
              [{"name": "Deterministic downtime (h)", "data": [s["downtime_hours"] for s in sc]},
               {"name": "Monte Carlo P90 (h)", "data": [s["monte_carlo"]["p90_hours"] if s["monte_carlo"] else None for s in sc]}],
              caption="P90 resamples synthetic supplier delivery history (seeded).", source=sim["version"]),
        table("Scenario comparison", [("delay_hours", "Delay h"), ("arrival", "Part arrival"), ("slot_start", "Slot start"), ("slot_wait_hours", "Slot wait h"),
                                      ("downtime_hours", "Downtime h"), ("cost_low_usd", "Cost low $"), ("cost_high_usd", "Cost high $"),
                                      ("incremental_downtime_vs_first", "+h vs first")], sc),
        table("Sensitivity (first scenario, mid-point cost)", [("factor", "Factor"), ("low_usd", "Low $"), ("baseline_usd", "Baseline $"), ("high_usd", "High $"), ("swing_usd", "Swing $")], sim["sensitivity"]),
        {"type": "formulas", "items": sim["formulas"]},
        {"type": "scenario_controls", "inputs": sim["inputs"]},
    ]
    state.assumptions = list(dict.fromkeys(state.assumptions + sim["assumptions"]))
    return blocks


def _scenario(state: CaseState) -> list[dict[str, Any]]:
    sim = state.inputs.get("sim")
    if not sim:
        return _generic(state)
    sc = sim["scenarios"]
    first, last = sc[0], sc[-1]
    state.answer = (f"**Delay scenarios for {sim['inputs']['part_number']} at {sim['inputs']['base']} (synthetic).** "
                    f"A {first['delay_hours']} h delay gives {first['downtime_hours']} h modeled downtime (${first['cost_low_usd']:,}-${first['cost_high_usd']:,}); "
                    f"{last['delay_hours']} h gives {last['downtime_hours']} h (${last['cost_low_usd']:,}-${last['cost_high_usd']:,}). "
                    f"The difference is driven by hangar slot availability, not just the delay itself: slot wait {first['slot_wait_hours']} h vs {last['slot_wait_hours']} h. "
                    "Change the inputs below and re-run; results are deterministic for the same inputs.")
    return [md(state.answer), kpis([{"label": f"{s['delay_hours']} h delay", "value": f"{s['downtime_hours']} h", "hint": f"P90 {s['monte_carlo']['p90_hours'] if s['monte_carlo'] else '-'} h"} for s in sc])] + _scenario_blocks(state)


def _downtime(state: CaseState) -> list[dict[str, Any]]:
    i = state.inputs
    t = i["target"]
    rows = i.get("cause_rows", [])
    ci = i.get("ci", {})
    prior_mean = sum(m["hours_per_aircraft_day"] for m in i["prior"]) / len(i["prior"])
    top = rows[:2]
    sup3 = i.get("suppliers", {}).get("SUP-03", {})
    deltas = ", ".join("{:+.1f} h/day".format(r["delta_per_day"]) for r in top)
    state.answer = (f"**Downtime in {t['month']} rose to {t['hours_per_aircraft_day']:.3f} h per aircraft-day, "
                    f"{(t['hours_per_aircraft_day'] / prior_mean - 1) * 100:+.0f}% vs the trailing 12-month mean ({prior_mean:.3f}).** "
                    f"The largest contributors are {', '.join(r['cause'].replace('_', ' ') for r in top)} "
                    f"({deltas} vs baseline). "
                    f"Supplier SUP-03 recent deliveries slipped {sup3.get('recent_avg_slip_days', '?')} days on average, consistent with the parts-delay increase. "
                    f"Mean downtime per event: {ci.get('current', ['?'])[0]} h (95% CI {ci.get('current', [0, '?', '?'])[1]}-{ci.get('current', [0, '?', '?'])[2]}) vs "
                    f"{ci.get('prior', ['?'])[0]} h ({ci.get('prior', [0, '?', '?'])[1]}-{ci.get('prior', [0, '?', '?'])[2]}). "
                    f"These are associations in synthetic data, not proven causes; the current month is partial ({t['days_observed']} days).")
    state.assumptions = ["Cause categories are recorded by planners at closure and may be inconsistent.",
                         "Normalization per aircraft-day handles the partial current month.",
                         "Bootstrap CI uses 1000 seeded resamples of event-level downtime."]
    months = i["months"]
    return [
        md(state.answer),
        kpis([{"label": f"{t['month']} h/aircraft-day", "value": round(t["hours_per_aircraft_day"], 3), "tone": "amber"},
              {"label": "Trailing-12 mean", "value": round(prior_mean, 3)},
              {"label": "Events this month", "value": t["events"]},
              {"label": "Mean h/event (95% CI)", "value": f"{ci['current'][0]} ({ci['current'][1]}-{ci['current'][2]})"}]),
        chart("downtime_trend", "Downtime hours per aircraft-day by month", "line", [m["month"] for m in months],
              [{"name": "h per aircraft-day", "data": [m["hours_per_aircraft_day"] for m in months]}],
              caption="Current month normalized for partial observation.", source="maintenance_events (synthetic)"),
        chart("causes", f"Cause change vs baseline ({t['month']})", "bar", [r["cause"].replace("_", " ") for r in rows],
              [{"name": "This month h/day", "data": [r["hours_per_day"] for r in rows]}, {"name": "Baseline h/day", "data": [r["baseline_hours_per_day"] for r in rows]}],
              source="maintenance_events.cause_category"),
        table("Cause decomposition", [("cause", "Cause"), ("events", "Events"), ("hours", "Hours"), ("hours_per_day", "h/day"),
                                      ("baseline_hours_per_day", "Baseline h/day"), ("delta_per_day", "Delta"), ("z", "z")], rows),
    ]


def _legacy(state: CaseState) -> list[dict[str, Any]]:
    ls = state.inputs["landscape"]
    recs = state.inputs.get("recommendations", [])
    b = state.inputs.get("bundle")
    state.answer = (f"**Non-invasive modernization path (synthetic landscape).** Parsed {len(ls['sources'])} metadata sources: "
                    f"{ls['summary']['systems']} systems, {ls['summary']['tables']} tables, {ls['summary']['apis']} APIs. "
                    f"Found {ls['summary']['high']} high and {ls['summary']['medium']} medium findings, and {len(ls['unknowns'])} unknowns that must be answered by system owners. "
                    "Recommended start: a **read-only view adapter + MCP tool** (R1, R8) and a **validated batch bridge** (R4), then a **strangler facade** with an "
                    "**anti-corruption layer** (R2, R3). CDC (R5) and vendor ERP/IFS projections (R7) are conditional: no access to any IFS instance was assumed or tested.")
    state.assumptions = ["All schemas, APIs and systems are fictional fixtures or user uploads; nothing was executed.",
                         "Effort figures are planning assumptions, not estimates from the customer's environment."]
    blocks = [md(state.answer),
              kpis([{"label": "Systems", "value": ls["summary"]["systems"]}, {"label": "Tables", "value": ls["summary"]["tables"]},
                    {"label": "High findings", "value": ls["summary"]["high"], "tone": "red"}, {"label": "Unknowns", "value": len(ls["unknowns"]), "tone": "amber"}]),
              {"type": "graph", "title": "Dependency map (evidence-backed)", "nodes": [n for n in ls["nodes"] if n["type"] in ("system", "unknown", "api")],
               "edges": [e for e in ls["edges"] if e["kind"] not in ("contains",) or e["target"].startswith("API:")]},
              table("Findings", [("severity", "Severity"), ("kind", "Kind"), ("object", "Object"), ("detail", "Detail"), ("source", "Source")], ls["findings"]),
              table("Unknowns (must be answered, not assumed)", [("id", "ID"), ("question", "Question"), ("why", "Why it matters")], ls["unknowns"]),
              {"type": "recommendations", "items": recs},
              {"type": "roadmap", "items": state.inputs.get("roadmap", [])}]
    if b:
        blocks.append(table("Generated adapter static checks", [("check", "Check"), ("passed", "Passed")], b["static_checks"],
                            caption=f"Bundle {b['bundle_id']} generated, not executed. Run runtime tests in API & MCP Bridge Studio."))
    blocks.append(actions([{"label": "Open Legacy X-Ray", "kind": "navigate", "target": "/legacy"},
                           {"label": "Open Bridge Studio", "kind": "navigate", "target": "/bridge" + (f"?bundle={b['bundle_id']}" if b else "")}]))
    return blocks


def _bridge(state: CaseState) -> list[dict[str, Any]]:
    b = state.inputs.get("bundle")
    if not b:
        return _generic(state)
    state.answer = (f"**Generated read-only bridge {b['bundle_id']}** for `get_part_availability(part_number)` over the approved view "
                    "V_PART_AVAILABILITY: FastAPI adapter, canonical Pydantic models, MCP stdio server (official SDK), contract/security/MCP tests, "
                    "OpenAPI, threat model and README. The code has **not been executed**; run its tests in the sandbox from Bridge Studio.")
    return [md(state.answer),
            table("Legacy -> canonical mapping", [("legacy", "Legacy column"), ("canonical", "Canonical field"), ("type", "Type"), ("note", "Note")], b["mapping"]),
            table("Generated files", [("path", "Path"), ("bytes", "Bytes"), ("sha256", "SHA-256")], b["files"]),
            table("Static checks (no execution)", [("check", "Check"), ("passed", "Passed")], b["static_checks"]),
            {"type": "code", "title": "adapter/app.py (preview)", "language": "python", "code": b.get("preview", {}).get("adapter/app.py", "")},
            {"type": "bridge_test", "bundle_id": b["bundle_id"]},
            actions([{"label": "Open in Bridge Studio", "kind": "navigate", "target": f"/bridge?bundle={b['bundle_id']}"},
                     {"label": "Download bundle (.zip)", "kind": "download", "target": f"/api/bridge/{b['bundle_id']}/download"}])]


def _governance(state: CaseState) -> list[dict[str, Any]]:
    denied = state.inputs.get("denied", [])
    by_policy = state.inputs.get("by_policy", {})
    from app.core.policy import load_policy_catalog

    cat = {p["id"]: p for p in load_policy_catalog()}
    state.answer = (f"**{len(denied)} actions have been denied** by the deterministic policy engine. Each denial names the governing policy; "
                    "no language model participates in these decisions. Denied tools are never executed (invocation counts below).")
    return [md(state.answer),
            chart("denials", "Denied decisions by policy", "bar", list(by_policy.keys()), [{"name": "Denials", "data": list(by_policy.values())}], source="policy_decisions"),
            table("Governing policies", [("id", "Policy"), ("title", "Title"), ("count", "Denials"), ("description", "Rule")],
                  [{**cat.get(p, {"id": p, "title": "?", "description": ""}), "count": n} for p, n in sorted(by_policy.items())]),
            table("Recent denied actions", [("ts", "Time"), ("actor", "Actor"), ("action", "Action"), ("resource", "Resource"), ("policy_id", "Policy"), ("reason", "Reason")], denied[:40]),
            kpis([{"label": "records.export_email executions", "value": invocation_count("records.export_email"), "tone": "teal",
                   "hint": "Denied tool calls never reach the tool"}])]


def _export(state: CaseState) -> list[dict[str, Any]]:
    ex = state.inputs.get("export", {})
    rec = ex.get("record", {})
    d = rec.get("decision", {})
    executed = ex.get("tool_invocations_after", 0) - ex.get("tool_invocations_before", 0)
    state.answer = (f"**DENIED before execution.** Policy **{d.get('policy_id')}** ({d.get('reason')}) "
                    f"The export tool `records.export_email` was invoked **{executed}** times for this request. "
                    "The attempt, identity, classification and decision are recorded in the hash-chained audit log.")
    return [md(state.answer),
            kpis([{"label": "Decision", "value": d.get("decision", "?"), "tone": "red"},
                  {"label": "Policy", "value": d.get("policy_id", "?")},
                  {"label": "Tool executions", "value": executed, "tone": "teal"},
                  {"label": "Total ever executed", "value": ex.get("tool_invocations_after", 0), "tone": "teal"}]),
            {"type": "decision_trace", "decision": d, "identity": state.actor, "classification": "RESTRICTED", "destination": ex.get("destination")},
            actions([{"label": "Open Defense Trust Center", "kind": "navigate", "target": "/trust"},
                     {"label": "Try an allowed read", "kind": "query", "target": "Show which maintenance documents are stale or missing provenance."}])]


def _documents(state: CaseState) -> list[dict[str, Any]]:
    docs = state.inputs.get("docs", [])
    bad = [d for d in docs if d["issues"]]
    state.answer = (f"**{len(bad)} of {len(docs)} visible documents need attention** (superseded, overdue review, missing provenance or unreviewed classification). "
                    f"{state.inputs.get('docs_withheld', 0)} documents were withheld by classification. Non-authoritative documents are never cited as authoritative (POL-010).")
    return [md(state.answer),
            kpis([{"label": "Superseded", "value": sum(d["status"] == "superseded" for d in docs), "tone": "amber"},
                  {"label": "Review overdue", "value": sum(any("overdue" in x for x in d["issues"]) for d in docs), "tone": "amber"},
                  {"label": "Missing provenance", "value": sum(not d["has_provenance"] for d in docs), "tone": "red"}]),
            table("Documents with issues", [("id", "ID"), ("title", "Title"), ("revision", "Rev"), ("effective_date", "Effective"), ("review_due", "Review due"),
                                            ("classification", "Label"), ("issues", "Issues")], [{**d, "issues": "; ".join(d["issues"])} for d in bad])]


def _executive(state: CaseState) -> list[dict[str, Any]]:
    e = state.inputs.get("exec", {})
    r = state.inputs.get("roi", {})
    state.answer = ("**90-day modernization pitch (synthetic customer).** Keep the legacy core; add governed read-only bridges, agent workflows with human approval, "
                    "and executable trust controls. Value figures are an assumption-driven model with editable inputs, not a promise.")
    blocks = [md(state.answer)]
    if r:
        lo, hi = r["annual_benefit"]["low"], r["annual_benefit"]["high"]
        blocks += [kpis([{"label": "Modeled annual benefit", "value": f"${lo['total']:,} - ${hi['total']:,}"},
                         {"label": "First-year cost", "value": f"${r['first_year_cost']:,}"},
                         {"label": "Payback (modeled)", "value": f"{r['payback_months']['high_case']}-{r['payback_months']['low_case']} mo"},
                         {"label": "Incremental license cost", "value": f"${r['inputs']['incremental_software_license_cost']:,.0f}"}]),
                   chart("roi", "Benefit components (low vs high case)", "bar", ["Labor", "Downtime", "Rework"],
                         [{"name": "Low", "data": [lo["labor"], lo["downtime"], lo["rework"]]}, {"name": "High", "data": [hi["labor"], hi["downtime"], hi["rework"]]}],
                         source="ROI model inputs"),
                   {"type": "formulas", "items": r["formulas"] + [r["disclaimer"]]},
                   {"type": "roi_controls", "inputs": r["inputs"]}]
    blocks += [{"type": "roadmap", "items": state.inputs.get("roadmap", [])},
               table("Risks and governance gaps", [("risk", "Risk"), ("mitigation", "Mitigation")], [
                   {"risk": "Unknown system ownership/consumers (U1, U5)", "mitigation": "Discovery workshops in days 0-30"},
                   {"risk": "No verified ERP/IFS access", "mitigation": "Use only documented, licensed projections (R7)"},
                   {"risk": "Demo security is not production security", "mitigation": "Enterprise IdP, hardened hosting, formal assessment"},
                   {"risk": "Financial model unvalidated", "mitigation": "Replace assumptions with pilot measurements"}]),
               table("API / MCP strategy", [("pattern", "Pattern"), ("title", "Recommendation"), ("confidence", "Confidence")],
                     [{"pattern": x["pattern"], "title": x["title"], "confidence": x["confidence"]} for x in state.inputs.get("recommendations", [])])]
    if e:
        blocks.append(kpis([{"label": "Fleet in service", "value": f"{e['fleet']['available_pct']}%"}, {"label": "Open work orders", "value": e["fleet"]["open_work_orders"]},
                            {"label": "Legacy high findings", "value": e["legacy"]["high"]}, {"label": "Denied unsafe actions", "value": e["denied_actions"]}]))
    return blocks


def _parts(state: CaseState) -> list[dict[str, Any]]:
    crit = state.inputs.get("critical", [])
    sup = state.inputs.get("suppliers_rel", [])
    state.answer = f"**{len(crit)} critical/high parts have 2 or fewer verified units.** Supplier reliability is computed from synthetic delivery history."
    blocks = [md(state.answer),
              table("Critical stock (verified quantities only)", [("part_number", "Part"), ("name", "Name"), ("criticality", "Criticality"), ("verified_total", "Verified"), ("lead_time_days", "Lead d")], crit),
              chart("suppliers", "Supplier on-time % (synthetic history)", "bar", [s["id"] for s in sup], [{"name": "On-time %", "data": [s["on_time_pct"] for s in sup]}],
                    source="supplier_deliveries"),
              table("Supplier reliability", [("id", "Supplier"), ("name", "Name"), ("deliveries", "Deliveries"), ("on_time_pct", "On-time %"), ("avg_slip_days", "Avg slip d"), ("recent_avg_slip_days", "Recent slip d")], sup)]
    pd = state.inputs.get("part_detail")
    if pd:
        blocks.append(table(f"{pd['part']['part_number']} availability", [("location", "Location"), ("verified_qty", "Verified"), ("note", "Note")], pd["availability"]))
        blocks.append(table("Substitution check", [("part_number", "Alternate"), ("approved", "Approved"), ("reason", "Reason")], pd["substitutes"]))
    return blocks


def _fleet(state: CaseState) -> list[dict[str, Any]]:
    f = state.inputs["fleet"]
    state.answer = (f"**Fleet of {f['total_aircraft']} synthetic aircraft: {f['available_pct']}% in service, {f['aog_count']} AOG, {f['open_work_orders']} open work orders.** "
                    f"Above the fictional vibration threshold: {', '.join(f['anomaly_aircraft']) or 'none'}. Health scores are demo heuristics, not airworthiness determinations.")
    return [md(state.answer),
            kpis([{"label": "Aircraft", "value": f["total_aircraft"]}, {"label": "In service", "value": f"{f['available_pct']}%"},
                  {"label": "AOG", "value": f["aog_count"], "tone": "red"}, {"label": "Mean health", "value": f["mean_health_score"]}]),
            chart("status", "Fleet by status", "pie", list(f["by_status"].keys()), [{"name": "Aircraft", "data": list(f["by_status"].values())}], source="aircraft"),
            actions([{"label": "Open Fleet & Asset Health", "kind": "navigate", "target": "/fleet"}])]


def _quality(state: CaseState) -> list[dict[str, Any]]:
    q = state.inputs["quality"]
    s = q["supplier"]
    state.answer = (f"**Nonconformance investigation draft (synthetic).** Supplier {s['id']} ({s['name']}) has the lowest on-time rate ({s['on_time_pct']}%) "
                    f"and recent average slip {s['recent_avg_slip_days']} days. A CAPA draft is prepared below; disposition and approval belong to the quality approver (DOC-015/016).")
    return [md(state.answer),
            table("CAPA draft (requires quality approval)", [("field", "Field"), ("value", "Draft")], [
                {"field": "Problem", "value": f"Lead-time slips from {s['id']} delaying critical parts"},
                {"field": "Containment", "value": "Use approved alternates only (DOC-019); expedite verified stock transfers"},
                {"field": "Root cause (hypothesis)", "value": "Supplier capacity constraint - to be confirmed with supplier evidence"},
                {"field": "Corrective action", "value": "Supplier corrective action request; dual-source critical parts"},
                {"field": "Effectiveness check", "value": "On-time % over next 60 days of deliveries"},
                {"field": "Approver", "value": "Quality approver (human)"}])]


COMPOSERS = {
    "maintenance_investigation": _maintenance,
    "recovery_options": _maintenance,
    "scenario_compare": _scenario,
    "downtime_analysis": _downtime,
    "legacy_assessment": _legacy,
    "bridge_generation": _bridge,
    "governance_review": _governance,
    "data_export": _export,
    "document_freshness": _documents,
    "executive_pitch": _executive,
    "parts_status": _parts,
    "fleet_overview": _fleet,
    "quality_investigation": _quality,
}
