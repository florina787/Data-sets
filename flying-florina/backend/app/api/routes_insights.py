"""Executive Command Center, Predictive Maintenance and Evaluation & Observability read models.

Every value is computed from the synthetic database, the workflow/event/decision tables or the evaluation
result files. Statistical anomaly scores are deterministic rules, not a trained model, and are labelled so.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope, labels_for, require
from app.core import db
from app.core.config import REPO_ROOT
from app.core.security import Actor, current_actor
from app.core.util import DEMO_TODAY
from app.seed.generator import DEMO_VIBRATION_THRESHOLD
from app.services import data

router = APIRouter()


def _aircraft(fleet: str | None, base: str | None, ac_type: str | None) -> list[dict[str, Any]]:
    rows = data.fleet_overview()["aircraft"]
    return [a for a in rows if (not fleet or a["fleet"] == fleet) and (not base or a["base"] == base) and (not ac_type or a["type"] == ac_type)]


@router.get("/api/command/overview")
def command_overview(request: Request, fleet: str | None = Query(None, max_length=40), base: str | None = Query(None, max_length=20),
                     ac_type: str | None = Query(None, max_length=40), severity: str | None = Query(None, max_length=10),
                     months: int = Query(12, ge=3, le=18), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "command:overview", "INTERNAL")
    acs = _aircraft(fleet, base, ac_type)
    ids = {a["id"] for a in acs}
    n = len(acs) or 1
    status = Counter(a["status"] for a in acs)
    allowed = labels_for(actor)
    wos = [w for w in db.query("SELECT * FROM work_orders WHERE status != 'closed'") if w["aircraft_id"] in ids and w["classification"] in allowed]
    if severity:
        wos = [w for w in wos if w["priority"] == severity]
    parts = {p["part_number"]: p for p in db.query("SELECT part_number, ata_chapter, criticality FROM parts")}
    # Availability trend: 1 - downtime hours / (aircraft x 24 x observed days), per month, for the filtered aircraft.
    ev = db.query("SELECT aircraft_id, substr(date,1,7) m, SUM(downtime_hours) h, COUNT(*) c, SUM(CASE WHEN type='unscheduled' THEN 1 ELSE 0 END) u "
                  "FROM maintenance_events GROUP BY aircraft_id, m")
    per_month: dict[str, dict[str, float]] = defaultdict(lambda: {"h": 0.0, "c": 0, "u": 0})
    for r in ev:
        if r["aircraft_id"] in ids:
            per_month[r["m"]]["h"] += r["h"]
            per_month[r["m"]]["c"] += r["c"]
            per_month[r["m"]]["u"] += r["u"]
    dm = {m["month"]: m["days_observed"] for m in data.downtime_by_month()}
    trend = []
    for m in sorted(per_month)[-months:]:
        days = dm.get(m, 30)
        trend.append({"month": m, "availability_pct": round(100 * (1 - per_month[m]["h"] / (n * 24 * days)), 2), "events": per_month[m]["c"],
                      "unscheduled": per_month[m]["u"], "downtime_hours": round(per_month[m]["h"], 1)})
    health = [a["health_score"] for a in acs if a["health_score"] is not None]
    buckets = [(0, 60), (60, 75), (75, 85), (85, 95), (95, 101)]
    health_dist = [{"bucket": f"{lo}-{min(hi, 100)}", "aircraft": sum(lo <= h < hi for h in health)} for lo, hi in buckets]
    # Component risk heatmap: open work orders by ATA chapter x base.
    heat = Counter((parts.get(w["part_number"], {}).get("ata_chapter", "?"), next((a["base"] for a in acs if a["id"] == w["aircraft_id"]), "?")) for w in wos)
    chapters = sorted({c for c, _ in heat})
    bases = sorted({b for _, b in heat})
    backlog = Counter((w["status"], w["priority"]) for w in wos)
    crit = data.critical_stock()
    gov = db.query_one("SELECT COUNT(*) n, SUM(CASE WHEN decision='DENY' THEN 1 ELSE 0 END) d FROM policy_decisions")
    runs = db.query("SELECT workflow, status, COUNT(*) n FROM workflow_runs GROUP BY workflow, status")
    pending = db.query_one("SELECT COUNT(*) n FROM approvals WHERE status='pending'")["n"]
    techs = db.query("SELECT base, COUNT(*) n FROM technicians GROUP BY base")
    tat = [r["d"] for r in db.query("SELECT julianday(closed) - julianday(opened) d FROM work_orders WHERE closed IS NOT NULL") if r["d"] is not None]
    above = [a for a in acs if a["above_threshold"]]
    risk = sorted(({"aircraft": a["id"], "health_score": a["health_score"], "open_work_orders": a["open_work_orders"], "status": a["status"], "base": a["base"],
                    "type": a["type"]} for a in acs), key=lambda r: (r["health_score"] or 100))[:12]
    from app.simulation.engine import DelayScenarioInputs, compare_delays

    sim = compare_delays(DelayScenarioInputs(delays_hours=[24, 72], monte_carlo_runs=0))
    kpis = {
        "total_aircraft": len(acs), "available": status.get("in_service", 0), "readiness_pct": round(100 * status.get("in_service", 0) / n, 1),
        "requiring_maintenance": status.get("scheduled_maintenance", 0) + status.get("unscheduled_maintenance", 0), "aog": status.get("aog", 0),
        "engineering_alerts": len(above), "open_work_orders": len(wos), "critical_parts_at_risk": len(crit),
        "mean_turnaround_days": round(statistics.mean(tat), 2) if tat else None,
        "technicians": sum(t["n"] for t in techs if not base or t["base"] == base),
        "active_workflows": sum(r["n"] for r in runs if r["status"] in ("running", "queued", "awaiting_approval")),
        "pending_approvals": pending, "policy_denials": gov["d"] or 0,
        "simulated_downtime_exposure_usd": {"low": sim["scenarios"][0]["cost_low_usd"], "high": sim["scenarios"][-1]["cost_high_usd"],
                                            "label": "SIMULATION: AC-204 24-72 h part delay x fictional cost/h"},
        "predicted_maintenance_events": None,
    }
    return envelope(request, {
        "filters": {"fleet": fleet, "base": base, "ac_type": ac_type, "severity": severity,
                    "options": {"fleet": sorted({a["fleet"] for a in data.fleet_overview()["aircraft"]}), "base": sorted({a["base"] for a in data.fleet_overview()["aircraft"]}),
                                "ac_type": sorted({a["type"] for a in data.fleet_overview()["aircraft"]}), "severity": ["routine", "urgent"]}},
        "kpis": kpis, "status": dict(status), "availability_trend": trend, "health_distribution": health_dist,
        "heatmap": {"x": bases, "y": chapters, "cells": [[bases.index(b), chapters.index(c), v] for (c, b), v in heat.items()]},
        "backlog": [{"status": s, "priority": p, "count": c} for (s, p), c in sorted(backlog.items())],
        "parts_shortage": crit[:10], "risk_matrix": risk, "agent_activity": runs,
        "decisions": {"pending_approvals": pending, "denials": gov["d"] or 0, "decisions": gov["n"] or 0,
                      "top_risks": [f"{a['id']} above fictional vibration threshold" for a in above] + [f"{c['part_number']} {c['verified_total']} verified unit(s)" for c in crit[:3]]},
        "notes": ["Availability % = 1 - downtime hours / (aircraft x 24 h x observed days), from synthetic maintenance events.",
                  "Predicted maintenance events: not shown. Flying_Florina has no trained predictive model; see Predictive Maintenance for statistical anomaly scores."],
    })


def _stats(values: list[float]) -> tuple[float, float]:
    return (statistics.mean(values), statistics.pstdev(values) or 1e-6) if values else (0.0, 1e-6)


@router.get("/api/predictive/overview")
def predictive_overview(request: Request, ac_type: str | None = Query(None, max_length=40), base: str | None = Query(None, max_length=20),
                        actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Deterministic statistical anomaly scores (z-scores vs each aircraft's own baseline). Not a trained model."""
    require(actor, "read", "predictive:overview", "INTERNAL")
    acs = {a["id"]: a for a in _aircraft(None, base, ac_type)}
    end = date.fromisoformat(DEMO_TODAY)
    since = (end - timedelta(days=89)).isoformat()
    recent_from = (end - timedelta(days=6)).isoformat()
    base_to = (end - timedelta(days=21)).isoformat()
    rows = db.query("SELECT aircraft_id, day, vibration_index v, egt_delta_c e, oil_pressure_index o FROM sensor_readings WHERE day >= ? ORDER BY day", (since,))
    by_ac: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["aircraft_id"] in acs:
            by_ac[r["aircraft_id"]].append(r)
    scores = []
    anomaly_days: Counter = Counter()
    for ac, rs in by_ac.items():
        out = {"aircraft": ac, "type": acs[ac]["type"], "base": acs[ac]["base"]}
        missing = sum(1 for r in rs if r["v"] is None)
        for key, name in (("v", "vibration"), ("e", "egt"), ("o", "oil")):
            b = [r[key] for r in rs if r[key] is not None and r["day"] < base_to]
            rec = [r[key] for r in rs if r[key] is not None and r["day"] >= recent_from]
            mu, sd = _stats(b)
            out[f"{name}_z"] = round((statistics.mean(rec) - mu) / sd, 1) if rec else None
            if key == "v":
                for r in rs:
                    if r[key] is not None and (r[key] - mu) / sd > 3:
                        anomaly_days[r["day"]] += 1
        out["missing_days"] = missing
        out["data_quality"] = "gaps" if missing >= 2 else "ok" if missing == 0 else "minor gap"
        z = max(abs(out["vibration_z"] or 0), abs(out["egt_z"] or 0) * 0.6, abs(out["oil_z"] or 0) * 0.6)
        out["risk_score"] = round(z, 1)
        out["priority"] = "high" if z >= 6 else "medium" if z >= 3 else "low"
        scores.append(out)
    scores.sort(key=lambda r: -r["risk_score"])
    dist = Counter(s["priority"] for s in scores)
    return envelope(request, {
        "method": {"type": "deterministic statistical rules (no trained model)",
                   "risk_score": "max(|vibration z|, 0.6 x |EGT z|, 0.6 x |oil z|): 7-day mean vs the aircraft's own 90-day baseline (excluding the last 21 days)",
                   "priority": "high >= 6, medium >= 3, low < 3 (fictional demo cut-offs)",
                   "not_trustworthy_when": ["fewer than ~30 baseline days", "sensor gaps in the recent 7 days", "recent maintenance reset the baseline",
                                            "a single isolated spike (likely sensor glitch)", "real operational data differs from this synthetic generator"],
                   "accuracy": "No accuracy, precision or recall is reported: there are no labelled outcomes to evaluate against."},
        "scores": scores, "distribution": [{"priority": p, "aircraft": dist.get(p, 0)} for p in ("high", "medium", "low")],
        "anomaly_timeline": [{"day": d, "aircraft_with_z_over_3": c} for d, c in sorted(anomaly_days.items())],
        "heatmap": {"aircraft": [s["aircraft"] for s in scores[:20]], "sensors": ["vibration", "egt", "oil"],
                    "cells": [[j, i, abs(s.get(f"{k}_z") or 0)] for i, s in enumerate(scores[:20]) for j, k in enumerate(["vibration", "egt", "oil"])]},
        "threshold": {"vibration_index": DEMO_VIBRATION_THRESHOLD, "label": "fictional demo threshold"},
    })


class ExplainBody(BaseModel):
    aircraft_id: str = Field(pattern=r"^AC-\d{3}$")


@router.post("/api/predictive/explain")
def predictive_explain(request: Request, body: ExplainBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Qwen explains the deterministic scores for one aircraft; the Evidence Challenger checks every number and ID."""
    require(actor, "read", f"predictive:{body.aircraft_id}", "INTERNAL")
    from app.llm.gateway import LLMError, LLMUnavailable, gateway
    from app.workflows.explain import Explanation, challenge

    ov = predictive_overview(request, None, None, actor)["data"]
    s = next((x for x in ov["scores"] if x["aircraft"] == body.aircraft_id), None)
    if not s:
        raise ApiError(404, "not_found", "Aircraft not in scope.")
    facts = ("FACTS (deterministic statistical scores, not a trained model): " + json.dumps(s) + " METHOD: " + ov["method"]["risk_score"]
             + " LIMITS: " + "; ".join(ov["method"]["not_trustworthy_when"]))
    g = gateway()
    if not g.available():
        return envelope(request, {"available": False, "reason": g.discovery.reason, "scores": s})
    try:
        r = g.generate(agent="Predictive Maintenance Agent", task="explain:predictive", schema=Explanation, user=facts,
                       system=("Explain these anomaly scores to a reliability engineer. Use only numbers in FACTS. They are statistical scores, not "
                               "predictions or diagnoses; say when they should not be trusted. JSON keys: headline, summary, key_findings, "
                               "recommended_next_steps, limitations."))
    except (LLMError, LLMUnavailable) as err:
        return envelope(request, {"available": True, "error": str(err), "scores": s})
    ch = challenge(r.data or {}, facts)
    return envelope(request, {"available": True, "verdict": ch["verdict"], "explanation": ch["explanation"] if ch["verdict"] != "reject" else None,
                              "challenger": ch, "meta": r.as_dict(), "scores": s})


@router.get("/api/observability/workflows")
def obs_workflows(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    runs = db.query("SELECT workflow, status, state_json FROM workflow_runs")
    by_wf: dict[str, Counter] = defaultdict(Counter)
    totals = []
    routes = Counter()
    for r in runs:
        by_wf[r["workflow"]][r["status"]] += 1
        st = json.loads(r["state_json"] or "{}")
        if st.get("timing", {}).get("total_ms"):
            totals.append(st["timing"]["total_ms"])
        routes[(st.get("route") or {}).get("method", "n/a")] += 1
    ev = db.query("SELECT agent, step, status, duration_ms, attempt FROM workflow_events WHERE status IN ('completed','failed','retrying','skipped')")
    agents: dict[str, dict[str, Any]] = defaultdict(lambda: {"steps": 0, "failed": 0, "retries": 0, "skipped": 0, "ms": []})
    for e in ev:
        a = agents[e["agent"]]
        a["steps"] += 1
        a["failed"] += e["status"] == "failed"
        a["retries"] += e["status"] == "retrying"
        a["skipped"] += e["status"] == "skipped"
        if e["duration_ms"] is not None and e["status"] == "completed":
            a["ms"].append(e["duration_ms"])

    def pct(v: list[float], p: float) -> float | None:
        return round(sorted(v)[min(len(v) - 1, round(p * (len(v) - 1)))], 1) if v else None

    agent_rows = [{"agent": k, "steps": v["steps"], "failed": v["failed"], "retries": v["retries"], "skipped": v["skipped"], "p50_ms": pct(v["ms"], 0.5),
                   "p95_ms": pct(v["ms"], 0.95)} for k, v in agents.items()]
    tools = db.query("SELECT tool, status, COUNT(*) n, AVG(duration_ms) ms FROM tool_invocations GROUP BY tool, status")
    dec = db.query("SELECT policy_id, decision, COUNT(*) n FROM policy_decisions GROUP BY policy_id, decision")
    appr = db.query("SELECT status, COUNT(*) n FROM approvals GROUP BY status")
    ok = sum(c for wf in by_wf.values() for s, c in wf.items() if s in ("completed", "awaiting_approval"))
    challenger = [json.loads(r["data_json"]) for r in db.query("SELECT data_json FROM audit_events WHERE kind='llm.explanation'")]
    return envelope(request, {
        "runs": len(runs), "success_rate": round(ok / len(runs), 3) if runs else None,
        "workflow_ms": {"p50": pct(totals, 0.5), "p95": pct(totals, 0.95)},
        "by_workflow": [{"workflow": k, **dict(v)} for k, v in sorted(by_wf.items())], "by_agent": sorted(agent_rows, key=lambda r: -r["steps"]),
        "tools": tools, "policy": dec, "approvals": appr, "route_methods": dict(routes),
        "schema_failures": db.query_one("SELECT COUNT(*) n FROM llm_calls WHERE error = 'schema_invalid'")["n"],
        "challenger": {"explanations": len(challenger), "rejected": sum(c.get("verdict") == "reject" for c in challenger),
                       "unsupported_items": sum(c.get("unsupported", 0) for c in challenger)},
    })


@router.get("/api/observability/eval")
def obs_eval(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    out = []
    folder = REPO_ROOT / "docs" / "eval"
    for p in sorted(folder.glob("four_questions_*.json")):
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        out.append({"file": p.name, **{k: d.get(k) for k in ("split", "items", "routing_accuracy", "macro_f1", "four_family_routing_accuracy",
                                                              "follow_up_accuracy", "workflow_correctness", "evidence_accuracy", "unsupported_claim_rate",
                                                              "answer_completeness", "latency_ms", "governance", "route_methods", "qwen")},
                    "per_label": d.get("per_label"), "errors": (d.get("errors") or [])[:10]})
    return envelope(request, out)
