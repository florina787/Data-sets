"""Graph 1 agents: maintenance investigation of a synthetic aircraft anomaly.

Agents produce hypotheses and drafts. None of them diagnoses airworthiness,
signs off work or returns an aircraft to service (see fictional DOC-014).
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any

from app.agents.common import call_tool
from app.core import policy
from app.core.util import DEMO_TODAY
from app.seed.generator import DEMO_VIBRATION_THRESHOLD
from app.services import approvals
from app.workflows.engine import CaseState, StepContext, StepHalt

REQUIRED_QUALS = ["Engine mount replacement (demo)", "Kestrel engine run-up (demo)"]
TRANSFER_HOURS = {("EAST-DEPOT", "MAIN-HUB"): 10, ("NORTH-FIELD", "MAIN-HUB"): 6}  # fictional logistics assumptions
RECEIVING_INSPECTION_HOURS = 4


def intake(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ents = state.intent.get("entities", {})
    ac = (ents.get("aircraft") or ["AC-204"])[0]
    from app.services import data

    detail = data.aircraft_detail(ac)
    if not detail:
        raise StepHalt("needs_clarification", f"Aircraft {ac} is not in the synthetic fleet (AC-001..AC-149, AC-204).")
    state.inputs.update({"aircraft_id": ac, "aircraft_type": detail["type"], "base": detail["base"],
                         "part_number": (ents.get("parts") or ["P-7731"])[0]})
    defaulted = "" if ents.get("aircraft") else " (defaulted to seeded incident aircraft)"
    return {"summary": f"Normalized request: aircraft {ac}{defaulted}, type {detail['type']}, base {detail['base']}.",
            "aircraft": ac}


def policy_precheck(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    # Starting a workflow needs PUBLIC access within the home organization;
    # each tool call then enforces the label of the data it touches.
    d = policy.evaluate(ctx.human, policy.PolicyRequest(action="query", resource=f"workflow:{state.workflow}", label="PUBLIC",
                                                        run_id=state.run_id, extra={"require_home_org": True}))
    with ctx.lock:
        state.policy_decisions.append(d.as_dict())
    if not d.allowed:
        raise StepHalt("denied", f"Policy precheck denied: {d.reason} ({d.policy_id})")
    return {"summary": f"Precheck ALLOW for {ctx.human.id} ({ctx.human.role}) via {d.policy_id}.", "decision": d.as_dict()}


def telemetry(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ac = state.inputs["aircraft_id"]
    res, rec = call_tool(state, ctx, "Asset Telemetry Agent", "telemetry.get_series", {"aircraft_id": ac, "days": 90})
    if res is None:
        return {"summary": f"Telemetry withheld or unavailable ({rec['status']}).", "available": False, "tools": [rec["tool"]]}
    series = res["series"]
    vib = [(r["day"], r["vibration_index"]) for r in series]
    present = [(d, v) for d, v in vib if v is not None]
    missing = [d for d, v in vib if v is None]
    baseline = [v for d, v in present if d < (date.fromisoformat(DEMO_TODAY) - timedelta(days=21)).isoformat()]
    mu = statistics.mean(baseline)
    sd = statistics.pstdev(baseline) or 1e-6
    recent = [v for d, v in present[-7:]]
    outliers = [{"day": d, "value": v, "z": round((v - mu) / sd, 1)} for d, v in present if (v - mu) / sd > 3]
    rising = 0
    for i in range(len(present) - 1, 0, -1):
        if present[i][1] >= present[i - 1][1] - 0.02:
            rising += 1
        else:
            break
    over = [d for d, v in present if v >= DEMO_VIBRATION_THRESHOLD]
    egt = [r["egt_delta_c"] for r in series if r["egt_delta_c"] is not None]
    egt_recent = statistics.mean(egt[-7:])
    egt_base = statistics.mean(egt[:-21])
    single_spikes = [o for o in outliers if o["day"] not in {d for d, _ in present[-21:]}]
    stats = {
        "baseline_mean": round(mu, 3), "baseline_sd": round(sd, 3), "recent_7d_mean": round(statistics.mean(recent), 3),
        "recent_z": round((statistics.mean(recent) - mu) / sd, 1), "days_rising": rising, "days_over_demo_threshold": len(over),
        "first_over_threshold": over[0] if over else None, "missing_days": missing, "outlier_days": len(outliers),
        "egt_delta_recent": round(egt_recent, 2), "egt_delta_baseline": round(egt_base, 2),
        "isolated_spikes_outside_trend": len(single_spikes),
    }
    band = {r["day"]: r["mean"] for r in res["fleet_band"]}
    with ctx.lock:
        state.inputs["telemetry_series"] = [{"day": d, "vibration_index": v, "fleet_mean": round(band.get(d) or 0, 3)} for d, v in vib]
        state.inputs["telemetry_stats"] = stats
    quality = f"{len(missing)} missing day(s) flagged as data-quality gaps" if missing else "no missing readings"
    return {"summary": f"7-day vibration mean {stats['recent_7d_mean']} vs baseline {stats['baseline_mean']} "
                       f"(z={stats['recent_z']}); {rising} days rising; {len(over)} days at/above fictional demo threshold; {quality}.",
            "stats": stats, "tools": ["telemetry.get_series"],
            "evidence": [{"kind": "telemetry", "ref": f"sensor_readings:{ac}", "detail": "90 days synthetic daily readings"}]}


def retrieval(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    q = f"vibration engine mount isolator inspection {state.inputs.get('aircraft_type', '')} borescope sensor"
    res, rec = call_tool(state, ctx, "Knowledge Retrieval Agent", "docs.search", {"query": q, "limit": 8})
    if res is None:
        return {"summary": "Document search unavailable.", "tools": ["docs.search"]}
    hits = res["results"]
    injected = [h for h in hits if "prompt_injection_quarantined" in h["flags"]]
    blocked = []
    for h in injected:
        # The retrieved text asks for an export. Evaluate exactly that request with
        # its true origin; POL-011 denies it and the tool is never invoked.
        _, r2 = call_tool(state, ctx, "Knowledge Retrieval Agent", "records.export_email",
                          {"destination": "address found in retrieved text", "record_set": "restricted maintenance records"},
                          instruction_source="retrieved_content")
        blocked.append({"doc_id": h["doc_id"], "decision": r2.get("decision", {}).get("policy_id")})
        with ctx.lock:
            state.warnings.append(f"{h['doc_id']} contains instruction-like text; it was quarantined and treated as data only.")
    with ctx.lock:
        state.retrieved_docs = hits
    return {"summary": f"{len(hits)} permitted documents ranked by {res['method']}; {res['withheld_by_policy']} withheld by "
                       f"classification filter before ranking; {len(injected)} quarantined for prompt injection.",
            "withheld": res["withheld_by_policy"], "injection_blocked": blocked, "tools": ["docs.search"],
            "evidence": [{"kind": "document", "ref": f"{h['doc_id']} rev {h['revision']}", "detail": h["title"]} for h in hits]}


def history(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    ac = state.inputs["aircraft_id"]
    res, rec = call_tool(state, ctx, "Diagnostic Evidence Agent", "maintenance.get_history", {"aircraft_id": ac, "limit": 20})
    if res is None:
        return {"summary": f"Maintenance history withheld ({rec.get('decision', {}).get('policy_id', rec['status'])}).",
                "available": False, "tools": ["maintenance.get_history"]}
    with ctx.lock:
        state.inputs["history"] = res
    last_mount = next((e for e in res["events"] if "mount" in e["description"].lower()), None)
    open_wos = [w for w in res["work_orders"] if w["status"] != "closed"]
    return {"summary": f"{len(res['events'])} events; last engine-mount inspection "
                       f"{last_mount['date'] if last_mount else 'not found'}; {len(open_wos)} open work order(s).",
            "last_mount_inspection": last_mount, "open_work_orders": [w["id"] for w in open_wos], "tools": ["maintenance.get_history"],
            "evidence": [{"kind": "work_order", "ref": w["id"], "detail": w["description"]} for w in open_wos]}


def diagnostics(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    s = state.inputs.get("telemetry_stats")
    docs = {d["doc_id"]: d for d in state.retrieved_docs}
    if not s:
        return {"summary": "Insufficient permitted evidence for hypotheses.", "hypotheses": []}
    egt_move = s["egt_delta_recent"] - s["egt_delta_baseline"]
    hyps = [
        {"id": "H1", "hypothesis": "Engine mount isolator degradation",
         "supporting": [f"Sustained rise over {s['days_rising']} days (not a single spike)",
                        f"Recent z-score {s['recent_z']} vs own 90-day baseline",
                        "Last isolator inspection months ago found no defects (history may be stale)"],
         "contradicting": ["No physical inspection finding yet"],
         "reference_required": "DOC-003 inspection task card (RESTRICTED)", "score": 3},
        {"id": "H2", "hypothesis": "Internal engine damage",
         "supporting": [f"EGT delta moved {egt_move:+.1f} C alongside vibration"] if egt_move > 2 else [],
         "contradicting": [] if egt_move > 2 else ["EGT delta stable"],
         "reference_required": "DOC-005 borescope guidance", "score": 2 if egt_move > 2 else 1},
        {"id": "H3", "hypothesis": "Sensor or data-quality artefact",
         "supporting": [f"{len(s['missing_days'])} missing reading(s) in the window"] if s["missing_days"] else [],
         "contradicting": ["Trend persists across many consecutive days", "Second parameter (EGT) also moved"],
         "reference_required": "DOC-006 sensor data quality handling", "score": 0.5},
    ]
    for h in hyps:
        ref = h["reference_required"].split()[0]
        h["reference_available"] = ref in docs
        h["likelihood"] = "higher" if h["score"] >= 3 else "moderate" if h["score"] >= 1.5 else "lower"
    hyps.sort(key=lambda h: -h["score"])
    with ctx.lock:
        state.inputs["hypotheses"] = hyps
    return {"summary": "Ranked hypotheses (not a diagnosis): " + "; ".join(f"{h['id']} {h['hypothesis']} ({h['likelihood']})" for h in hyps),
            "hypotheses": hyps, "uncertainty": "Qualitative ranking from synthetic evidence; confirmation requires physical inspection per referenced task card."}


def parts(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    pn = state.inputs["part_number"]
    res, rec = call_tool(state, ctx, "Parts Agent", "parts.check_availability", {"part_number": pn})
    if res is None:
        return {"summary": "Parts data unavailable.", "tools": ["parts.check_availability"]}
    approved_alts = [s for s in res["substitutes"] if s["approved"]]
    alt_avail = []
    for s in approved_alts:
        r2, _ = call_tool(state, ctx, "Parts Agent", "parts.check_availability", {"part_number": s["part_number"]})
        if r2:
            alt_avail += r2["availability"]
    with ctx.lock:
        state.inputs["parts"] = {"primary": res, "alternate_availability": alt_avail}
    conflicts = [a for a in res["availability"] if a["conflict"]]
    verified_total = sum(a["verified_qty"] for a in res["availability"])
    return {"summary": f"{pn}: {verified_total} verified unit(s) across bases; {len(conflicts)} source conflict(s); "
                       f"{len(approved_alts)} approved alternate(s); {len([s for s in res['substitutes'] if not s['approved']])} rejected for lack of authority.",
            "tools": ["parts.check_availability"],
            "evidence": [{"kind": "inventory", "ref": f"{a['part_number']}@{a['location']}", "detail": a["note"] or "verified"} for a in res["availability"]]}


def scheduling(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    base = state.inputs["base"]
    tomorrow = (date.fromisoformat(DEMO_TODAY) + timedelta(days=1)).isoformat()
    roster, _ = call_tool(state, ctx, "Maintenance Planner Agent", "roster.find_qualified",
                          {"base": base, "required": REQUIRED_QUALS, "on_date": tomorrow})
    slots, _ = call_tool(state, ctx, "Maintenance Planner Agent", "hangar.find_slots", {"base": base})
    if roster is None or slots is None:
        return {"summary": "Roster or slot data withheld.", "tools": ["roster.find_qualified", "hangar.find_slots"]}
    covered = {q: [t["id"] for t in roster["qualified"] if q in t["matched"]] for q in REQUIRED_QUALS}
    with ctx.lock:
        state.inputs["roster"] = roster
        state.inputs["slots"] = slots["available"]
        state.inputs["coverage"] = covered
    gaps = [q for q, ts in covered.items() if not ts]
    return {"summary": f"{len(roster['qualified'])} qualified technician(s) at {base}; {len(roster['expired'])} excluded for expired "
                       f"qualifications; {len(slots['available'])} open slot(s) in next 10 days; coverage gaps: {gaps or 'none'}.",
            "tools": ["roster.find_qualified", "hangar.find_slots"]}


def recovery_options(state: CaseState) -> list[dict[str, Any]]:
    """Compare recovery options using only verified inventory and approved alternates."""
    from datetime import datetime

    base = state.inputs["base"]
    t0 = datetime.fromisoformat(f"{DEMO_TODAY}T09:00:00")
    parts_ = state.inputs.get("parts", {})
    primary = parts_.get("primary", {})
    slots = state.inputs.get("slots", [])
    opts = []

    def first_slot(after: datetime) -> str | None:
        for s in slots:
            if datetime.fromisoformat(s["start"]) >= after:
                return s["start"]
        return None

    def add(name: str, part: str, loc: str, lead_h: float, notes: list[str], compliant: bool) -> None:
        ready = t0 + timedelta(hours=lead_h)
        slot = first_slot(ready)
        done = (datetime.fromisoformat(slot) + timedelta(hours=9)) if slot else None
        opts.append({"option": name, "part_number": part, "source_location": loc, "part_ready_hours": lead_h,
                     "slot_start": slot, "est_downtime_hours": round((done - t0).total_seconds() / 3600, 1) if done else None,
                     "compliant": compliant, "notes": notes})

    for a in primary.get("availability", []):
        if a["location"] == base and a["verified_qty"] > 0:
            add("Use on-site stock", a["part_number"], a["location"], 1, ["Verified on-site count"], True)
        elif a["verified_qty"] > 0 and (a["location"], base) in TRANSFER_HOURS:
            add(f"Transfer from {a['location']}", a["part_number"], a["location"], TRANSFER_HOURS[(a["location"], base)],
                [f"Verified count {a['verified_qty']} at {a['location']}", "Fictional transfer-time assumption"], True)
        elif a["location"] == base and a["conflict"]:
            opts.append({"option": f"On-site stock at {base} (rejected)", "part_number": a["part_number"], "source_location": a["location"],
                         "part_ready_hours": None, "slot_start": None, "est_downtime_hours": None, "compliant": False,
                         "notes": [a["note"].strip(), f"Sources report {a['reported_qty_by_source']}"]})
    for a in parts_.get("alternate_availability", []):
        if a["verified_qty"] > 0 and (a["location"], base) in TRANSFER_HOURS:
            add(f"Approved alternate {a['part_number']} from {a['location']}", a["part_number"], a["location"],
                TRANSFER_HOURS[(a["location"], base)] + RECEIVING_INSPECTION_HOURS,
                ["Approved by fictional DOC-019 rev C", "Receiving inspection +4 h"], True)
    for s in primary.get("substitutes", []):
        if not s["approved"]:
            opts.append({"option": f"Substitute {s['part_number']} (rejected)", "part_number": s["part_number"], "source_location": "-",
                         "part_ready_hours": None, "slot_start": None, "est_downtime_hours": None, "compliant": False,
                         "notes": [s["reason"]]})
    lead_days = (primary.get("part") or {}).get("lead_time_days", 6)
    add("Order new from supplier", state.inputs["part_number"], (primary.get("part") or {}).get("supplier_id", "SUP"),
        lead_days * 24, [f"Promised lead time {lead_days} d; supplier history shows recent slips"], True)
    ranked = sorted([o for o in opts if o["compliant"] and o["est_downtime_hours"] is not None], key=lambda o: o["est_downtime_hours"])
    for i, o in enumerate(ranked):
        o["rank"] = i + 1
    return ranked + [o for o in opts if not o["compliant"] or o["est_downtime_hours"] is None]


def compliance(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    docs = {d["doc_id"]: d for d in state.retrieved_docs}
    coverage = state.inputs.get("coverage", {})
    opts = recovery_options(state) if state.inputs.get("parts") else []
    best = next((o for o in opts if o.get("rank") == 1), None)
    checks = [
        {"check": "Inspection task card retrieved and current", "ok": "DOC-003" in docs and docs["DOC-003"]["authoritative"],
         "evidence": "DOC-003" if "DOC-003" in docs else "not permitted / not found"},
        {"check": "Replacement procedure retrieved and current", "ok": "DOC-004" in docs and docs["DOC-004"]["authoritative"],
         "evidence": "DOC-004" if "DOC-004" in docs else "not permitted / not found"},
        {"check": "Every required qualification covered by unexpired technician", "ok": bool(coverage) and all(coverage.values()),
         "evidence": ", ".join(f"{q}: {len(t)}" for q, t in coverage.items()) or "roster unavailable"},
        {"check": "Recommended part is traceable and physically verified", "ok": bool(best),
         "evidence": best["option"] if best else "no compliant option"},
        {"check": "Non-authoritative sources excluded from citations", "ok": True,
         "evidence": ", ".join(d for d, v in docs.items() if not v["authoritative"]) or "none retrieved"},
        {"check": "Return to service remains a human authorization (DOC-014)", "ok": True, "evidence": "Software never signs off"},
    ]
    passed = sum(c["ok"] for c in checks)
    with ctx.lock:
        state.inputs["compliance"] = checks
        state.inputs["options"] = opts
    return {"summary": f"Evidence sufficiency {passed}/{len(checks)} checks. This is a checklist, not a certification.",
            "checks": checks}


def draft_plan(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    opts = state.inputs.get("options", [])
    best = next((o for o in opts if o.get("rank") == 1), None)
    if not best:
        return {"summary": "No compliant option; plan not drafted.", "drafted": False}
    coverage = state.inputs.get("coverage", {})
    techs = sorted({t for ts in coverage.values() for t in ts})
    plan = {"steps": [
        "Perform engine mount isolator inspection per DOC-003 (record findings).",
        "If degradation confirmed: replace isolator kit per DOC-004 using the recommended part source.",
        "If inspection is clean: perform borescope per DOC-005 and review sensor data quality per DOC-006.",
        "Prepare evidence packet; certifying human authorizes return to service per DOC-014."],
        "option": best, "technicians": techs, "hypotheses": [h["id"] for h in state.inputs.get("hypotheses", [])]}
    title = f"{state.inputs['aircraft_id']} vibration troubleshooting and isolator replacement ({best['option']})"
    res, rec = call_tool(state, ctx, "Maintenance Planner Agent", "workorder.create_draft",
                         {"aircraft_id": state.inputs["aircraft_id"], "title": title, "part_number": best["part_number"], "plan": plan})
    if res is None:
        return {"summary": f"Draft not created ({rec.get('decision', {}).get('policy_id', rec['status'])}).", "drafted": False}
    with ctx.lock:
        state.inputs["draft"] = res
    return {"summary": f"Dry-run draft {res['draft_id']} prepared: {best['option']}, est. downtime {best['est_downtime_hours']} h.",
            "drafted": True, "draft_id": res["draft_id"], "tools": ["workorder.create_draft"]}


def approval_gate(state: CaseState, ctx: StepContext) -> dict[str, Any]:
    draft = state.inputs.get("draft")
    if not draft:
        return {"summary": "No draft to approve."}
    techs = draft["plan"].get("technicians") or [None]
    payload = {"aircraft_id": draft["aircraft_id"], "title": draft["title"], "part_number": draft["part_number"],
               "technician": techs[0], "plan": draft["plan"], "draft_id": draft["draft_id"]}
    a = approvals.create("work_order", draft["title"], ctx.human, payload, run_id=state.run_id, risk="high")
    with ctx.lock:
        state.approvals.append({k: a[k] for k in ("id", "kind", "title", "status", "expires_at", "payload_sha256", "requested_by", "idempotency_key")})
    return {"summary": f"Approval {a['id']} requested from a different qualified approver (separation of duties). Write remains dry-run until approved.",
            "approval_id": a["id"]}
