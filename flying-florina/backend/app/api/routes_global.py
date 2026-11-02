"""Flying Florina 3.0 read models: global map, forecast timeline, component forecasting, digital twin, supply chain, resilience.

All values are computed by `app.global_intel` from the SYNTHETIC global dataset. Responses carry freshness and assumptions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope, require
from app.core import audit, db
from app.core.security import Actor, current_actor
from app.core.util import new_id, now_iso
from app.global_intel import dataset as ds
from app.global_intel import simulate as sim
from app.global_intel.forecast import HORIZONS_DAYS, LABOR_RATE, engine

router = APIRouter()
PROV = {"source": "Flying Florina 3.0 synthetic global dataset", "synthetic": True}
REGIONS = ["Europe", "North America", "Middle East", "Asia-Pacific", "Latin America", "Africa"]


def _h(days: int) -> int:
    return min([0, *HORIZONS_DAYS], key=lambda d: abs(d - days))


def map_state(days: int, category: str | None = None) -> dict[str, Any]:
    e = engine()
    days = _h(days)
    facs = e.facility_state(days)
    if category:
        for f in facs:
            f["shortages"] = [s for s in f.get("shortages", []) if s["category_id"] == category]
            f["shortage_count"] = len(f["shortages"])
            dem = e.demand(days, facility=f["id"], category=category) if days else []
            if dem:
                f["demand_p50"], f["demand_p10"], f["demand_p90"] = dem[0]["p50"], dem[0]["p10"], dem[0]["p90"]
    sups = e.supplier_state(days)
    links = []
    for lk in e.links:
        if category and lk["category_id"] != category:
            continue
        s = e.sup[lk["supplier_id"]]
        for f in e.fac.values():
            if f["kind"] == "mro":
                links.append({"supplier_id": s["id"], "facility_id": f["id"], "category_id": lk["category_id"], "share": lk["share"],
                              "from": [s["lon"], s["lat"]], "to": [f["lon"], f["lat"]]})
    dis = e.active_disruptions(days)
    regions = []
    for r in REGIONS:
        fr = [f for f in facs if f["region"] == r]
        regions.append({"region": r, "facilities": len(fr), "demand_p50": round(sum(f.get("demand_p50", 0) for f in fr), 2),
                        "shortages": sum(f.get("shortage_count", 0) for f in fr),
                        "health_mean": round(float(np.mean([f["health_mean"] for f in fr if "health_mean" in f])), 4) if any("health_mean" in f for f in fr) else None,
                        "cost_p50_usd": round(sum(f.get("cost_p50_usd", 0) for f in fr), 0),
                        "disruptions": sum(1 for d in dis if d["region"] == r and d["phase"] == "active")})
    return {"horizon_days": days, "facilities": facs, "suppliers": sups, "links": links, "disruptions": dis, "regions": regions,
            "categories": [{"id": c["id"], "name": c["name"], "family": c["family"]} for c in e.cat.values()],
            "freshness": e.freshness(), "assumptions": ds.assumptions() + [
                "Inventory projections simulate a weekly reorder policy (reorder point, 4 weeks' quantity) with recorded supplier lead times.",
                "Shortage = stockout probability of at least 20% at the selected horizon.",
                "Health is each tracked unit's latest health index extrapolated along its 8-week trend (clipped to 0..1).",
                "Workload utilisation = forecast removal labour hours / unscheduled-work crew (125% of historical average weekly hours)."]}


@router.get("/api/global/map")
def global_map(request: Request, horizon: int = Query(0, ge=0, le=90), category: str | None = Query(None, max_length=40),
               actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "global:map", "INTERNAL")
    return envelope(request, map_state(horizon, category), provenance=PROV)


@router.get("/api/global/timeline")
def global_timeline(request: Request, category: str | None = Query(None, max_length=40), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Every horizon at once so the map can transition between periods without waiting."""
    require(actor, "read", "global:map", "INTERNAL")
    return envelope(request, {str(d): map_state(d, category) for d in [0, *HORIZONS_DAYS]}, provenance=PROV)


@router.get("/api/global/search")
def global_search(request: Request, q: str = Query(..., min_length=1, max_length=60), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "global:map", "INTERNAL")
    e, ql = engine(), q.lower()
    hits = [{"kind": "facility", **{k: f[k] for k in ("id", "name", "city", "country", "region", "lat", "lon")}} for f in e.fac.values()
            if ql in f"{f['name']} {f['city']} {f['country']} {f['region']}".lower()]
    hits += [{"kind": "supplier", **{k: s[k] for k in ("id", "name", "city", "country", "region", "lat", "lon")}} for s in e.sup.values()
             if ql in f"{s['name']} {s['city']} {s['country']} {s['region']}".lower()]
    return envelope(request, hits[:20], provenance=PROV)


@router.get("/api/global/report", response_class=PlainTextResponse)
def global_report(request: Request, horizon: int = Query(30, ge=0, le=90), region: str | None = Query(None, max_length=30),
                  actor: Actor = Depends(current_actor)) -> PlainTextResponse:
    require(actor, "export", "global:report", "INTERNAL", destination="local_download")
    st = map_state(horizon)
    lines = [f"# Global Aerospace Intelligence report (+{st['horizon_days']} days)", "",
             "> SYNTHETIC demonstration data. Not live operational information. Independent concept demo, not affiliated with IFS.", "",
             f"Data as of {st['freshness']['data_as_of']} · models built {st['freshness']['models_built_at']} · {st['freshness']['model_version']}", "",
             "## Regions", "", "| Region | Demand P50 | Shortages | Mean health | Cost P50 (USD) | Active disruptions |", "|---|---|---|---|---|---|"]
    for r in st["regions"]:
        if region and r["region"] != region:
            continue
        lines.append(f"| {r['region']} | {r['demand_p50']} | {r['shortages']} | {r['health_mean']} | {r['cost_p50_usd']:,.0f} | {r['disruptions']} |")
    lines += ["", "## Facilities", "", "| Facility | Region | Demand P10–P90 | Utilisation | Shortages |", "|---|---|---|---|---|"]
    for f in st["facilities"]:
        if region and f["region"] != region or "demand_p50" not in f:
            continue
        lines.append(f"| {f['name']} | {f['region']} | {f['demand_p10']}–{f['demand_p90']} | {f.get('workload_utilisation', 0):.0%} | {f.get('shortage_count', 0)} |")
    lines += ["", "## Assumptions", ""] + [f"* {a}" for a in st["assumptions"]]
    audit.append(actor.id, "report.global_exported", f"Global intelligence report +{st['horizon_days']}d", {"region": region})
    return PlainTextResponse("\n".join(lines), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="global_intelligence_{st["horizon_days"]}d.md"'})


# ------------------------------------------------------------------ component forecasting
def component_forecast(days: int = 90, category: str | None = None, region: str | None = None) -> dict[str, Any]:
    e = engine()
    days = _h(days) or 7
    rows: dict[str, dict[str, Any]] = {}
    for d in e.demand(days, category=category, region=region):
        c = rows.setdefault(d["category_id"], {"category_id": d["category_id"], "category": e.cat[d["category_id"]]["name"],
                                               "family": e.cat[d["category_id"]]["family"], "p10": 0.0, "p50": 0.0, "p90": 0.0,
                                               "stockout_sites": 0, "max_stockout_prob": 0.0})
        for q in ("p10", "p50", "p90"):
            c[q] += d[q]
        inv = e.inventory.get((d["facility_id"], d["category_id"]), {}).get(days)
        if inv:
            c["max_stockout_prob"] = max(c["max_stockout_prob"], inv["stockout_prob"])
            c["stockout_sites"] += 1 if inv["stockout_prob"] >= 0.2 else 0
    for c in rows.values():
        cat = e.cat[c["category_id"]]
        for q in ("p10", "p50", "p90"):
            c[q] = round(c[q], 2)
        c["labour_hours_p50"] = round(c["p50"] * cat["labor_hours"], 1)
        c["cost_p10_usd"] = round(c["p10"] * (cat["unit_cost_usd"] + LABOR_RATE * cat["labor_hours"]), 0)
        c["cost_p50_usd"] = round(c["p50"] * (cat["unit_cost_usd"] + LABOR_RATE * cat["labor_hours"]), 0)
        c["cost_p90_usd"] = round(c["p90"] * (cat["unit_cost_usd"] + LABOR_RATE * cat["labor_hours"]), 0)
        units = [u for u in e.units.values() if u["category_id"] == c["category_id"] and u["status"] == "installed"
                 and (not region or e.fac[u["facility_id"]]["region"] == region)]
        c["mean_risk_30d"] = round(float(np.mean([u.get("risk_30d", 0) for u in units])), 4) if units else None
        c["units_high_risk"] = sum(1 for u in units if (u.get("risk_30d") or 0) >= 0.5)
        c["repair_tat_p50_days"] = next((v[1] for (_ctr, cid), v in e.repair_q.items() if cid == c["category_id"]), None)
    ranked = sorted(rows.values(), key=lambda r: -r["p50"])
    return {"horizon_days": days, "category": category, "region": region, "rows": ranked, "freshness": e.freshness(),
            "method": e.metrics["demand"]["method"]}


@router.get("/api/forecast/components")
def forecast_components(request: Request, horizon: int = Query(90, ge=7, le=90), category: str | None = Query(None, max_length=40),
                        region: str | None = Query(None, max_length=30), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "forecast:components", "INTERNAL")
    return envelope(request, component_forecast(horizon, category, region), provenance=PROV)


def series(category: str, facility: str | None = None, region: str | None = None) -> dict[str, Any]:
    e = engine()
    keys = [k for k in e.demand_hist if k[1] == category and (not facility or k[0] == facility) and (not region or e.fac[k[0]]["region"] == region)]
    if not keys:
        raise ApiError(404, "not_found", "No demand series for that selection.")
    hist = np.sum([e.demand_hist[k] for k in keys], axis=0)
    fc = {d: tuple(round(sum(e.demand_fc[k][d][i] for k in keys), 2) for i in range(3)) for d in HORIZONS_DAYS}
    inv = {d: {q: round(sum(e.inventory[k][d][q] for k in keys if k in e.inventory), 2) for q in ("p10", "p50", "p90")} for d in [0, *HORIZONS_DAYS]}
    sp = {d: round(float(np.mean([e.inventory[k][d]["stockout_prob"] for k in keys if k in e.inventory])), 4) for d in [0, *HORIZONS_DAYS]}
    return {"category_id": category, "category": e.cat[category]["name"], "facility": facility, "region": region,
            "history": [{"week_start": ds._week_start(w), "removals": int(v)} for w, v in enumerate(hist)],
            "forecast": [{"horizon_days": d, "p10": fc[d][0], "p50": fc[d][1], "p90": fc[d][2]} for d in HORIZONS_DAYS],
            "inventory": [{"horizon_days": d, **inv[d], "stockout_prob": sp[d]} for d in [0, *HORIZONS_DAYS]], "freshness": e.freshness()}


@router.get("/api/forecast/series")
def forecast_series(request: Request, category: str = Query(..., max_length=40), facility: str | None = Query(None, max_length=10),
                    region: str | None = Query(None, max_length=30), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "forecast:components", "INTERNAL")
    return envelope(request, series(category, facility, region), provenance=PROV)


@router.get("/api/forecast/evaluation")
def forecast_evaluation(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "forecast:evaluation", "INTERNAL")
    e = engine()
    return envelope(request, {"metrics": e.metrics, "backtest": e.backtest, "freshness": e.freshness(),
                              "risk_feature_importance": getattr(e, "risk_importance", {}),
                              "weibull": e.weibull,
                              "runs": db.query("SELECT id, ts, model_version, dataset, build_ms FROM forecast_runs ORDER BY ts DESC LIMIT 10")},
                    provenance=PROV)


@router.get("/api/forecast/heatmap")
def forecast_heatmap(request: Request, horizon: int = Query(30, ge=7, le=90), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "forecast:components", "INTERNAL")
    e = engine()
    d = _h(horizon) or 7
    facs = sorted({k[0] for k in e.demand_fc})
    cats = sorted(e.cat)
    cells = [[i, j, round(e.demand_fc[(f, c)][d][1] * e.cat[c]["labor_hours"], 1)] for i, f in enumerate(facs) for j, c in enumerate(cats)]
    return envelope(request, {"x": [e.fac[f]["city"] for f in facs], "y": [e.cat[c]["name"] for c in cats], "cells": cells, "horizon_days": d,
                              "unit": "forecast labour hours (P50)"}, provenance=PROV)


# ------------------------------------------------------------------ digital twin
@router.get("/api/twin/units")
def twin_units(request: Request, facility: str | None = Query(None, max_length=10), category: str | None = Query(None, max_length=40),
               installed_only: bool = True, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "twin:units", "INTERNAL")
    e = engine()
    us = [u for u in e.units.values() if (not facility or u["facility_id"] == facility) and (not category or u["category_id"] == category)
          and (not installed_only or u["status"] == "installed")]
    us.sort(key=lambda u: -(u.get("risk_30d") or 0))
    return envelope(request, [{**u, "facility": e.fac[u["facility_id"]]["name"], "category": e.cat[u["category_id"]]["name"]} for u in us[:300]],
                    provenance=PROV)


def twin(unit_id: str) -> dict[str, Any]:
    e = engine()
    u = e.units.get(unit_id)
    if not u:
        raise ApiError(404, "not_found", "Unknown unit.")
    weeks = db.query("SELECT week, health, vibration, temperature, pressure, operating_hours, anomaly FROM g_unit_weeks WHERE unit_id = ? ORDER BY week", (unit_id,))
    events = db.query("SELECT * FROM g_unit_events WHERE unit_id = ? ORDER BY week", (unit_id,))
    history = db.query("SELECT id, install_week, removal_week, life_weeks, status FROM g_units WHERE facility_id = ? AND category_id = ? AND position = ? ORDER BY install_week",
                       (u["facility_id"], u["category_id"], u["position"]))
    cat, w = e.cat[u["category_id"]], e.weibull[u["category_id"]]
    reasons = []
    if (u.get("risk_30d") or 0) >= 0.5:
        reasons.append(f"Failure-risk model: {u['risk_30d']:.0%} probability of removal within 30 days (RandomForest, test F1 "
                       f"{e.metrics['failure_risk_30d']['model_at_0.5']['f1']}).")
    if u.get("anomaly_now"):
        reasons.append("Latest sensor week flagged by the IsolationForest anomaly detector.")
    if u.get("last_health") is not None and u["last_health"] < 0.45:
        reasons.append(f"Health index {u['last_health']:.2f} is below 0.45 (removal threshold 0.20).")
    if u.get("health_slope_8w") is not None and u["health_slope_8w"] < -0.01:
        reasons.append(f"Health falling {abs(u['health_slope_8w']):.3f} per week over the last 8 readings.")
    if u.get("rul_combined") is not None and u["rul_combined"] < 8:
        reasons.append(f"Estimated remaining useful life {u['rul_combined']:.1f} weeks.")
    missing = sum(1 for r in weeks if r["health"] is None)
    # uncertainty over time: survival quantiles at future ages
    unc = []
    if u["status"] == "installed":
        for k in (0, 4, 8, 13, 26):
            unc.append({"weeks_ahead": k, **dict(zip(("p10", "p50", "p90"), e._rul_survival(w, u["age_weeks"] + k), strict=True))})
    docs = sorted({ev["doc_ref"] for ev in events if ev["doc_ref"]} | {"DOC-003"})
    return {"unit": {**u, "facility": e.fac[u["facility_id"]]["name"], "category": cat["name"], "family": cat["family"],
                     "unit_cost_usd": cat["unit_cost_usd"]},
            "telemetry": weeks, "events": events, "position_history": history, "flag_reasons": reasons,
            "data_quality": {"weeks": len(weeks), "missing_health_readings": missing},
            "survival_model": {**w, "category": cat["name"]}, "rul_uncertainty": unc,
            "predicted_demand_90d": e.demand_fc[(u["facility_id"], u["category_id"])][90],
            "documents_to_review": docs,
            "assumptions": ["Synthetic unit; health index and sensor channels are generated, not real telemetry.",
                            "Remaining-useful-life uses the unit's own health trend when it has >= 6 readings and is degrading, otherwise the category's Weibull survival curve conditional on age.",
                            "Advisory only. Not an airworthiness determination; certified maintenance procedures govern any action."],
            "freshness": e.freshness()}


@router.get("/api/twin/{unit_id}")
def twin_detail(request: Request, unit_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "twin:unit", "INTERNAL")
    return envelope(request, twin(unit_id[:40]), provenance=PROV)


# ------------------------------------------------------------------ supply chain + resilience
class DelayBody(BaseModel):
    supplier_id: str = Field(max_length=10)
    delay_days: float = Field(ge=0, le=120)
    horizon_days: int = Field(60, ge=7, le=90)


@router.post("/api/supply/delay-impact")
def supply_delay(request: Request, body: DelayBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "simulate", "supply:delay_impact", "INTERNAL")
    try:
        r = sim.delay_impact(engine(), body.supplier_id, body.delay_days, body.horizon_days)
    except KeyError as err:
        raise ApiError(404, "not_found", "Unknown supplier.") from err
    _save_scenario(actor, "supply_delay", f"{body.supplier_id} +{body.delay_days:g}d", body.model_dump(), r["scenarios"])
    return envelope(request, r, provenance=PROV)


@router.get("/api/supply/overview")
def supply_overview(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "supply:overview", "INTERNAL")
    e = engine()
    deliveries = db.query("SELECT supplier_id, promised_days, actual_days, ordered_week FROM g_deliveries WHERE actual_days IS NOT NULL")
    by: dict[str, list[dict[str, Any]]] = {}
    for d in deliveries:
        by.setdefault(d["supplier_id"], []).append(d)
    sups = []
    for sid, s in e.sup.items():
        ds_ = by.get(sid, [])
        lt = np.array([d["actual_days"] for d in ds_])
        ratio = np.array([d["actual_days"] / d["promised_days"] for d in ds_])
        q = [round(float(np.quantile(lt, x)), 1) for x in (0.1, 0.25, 0.5, 0.75, 0.9)] if len(lt) else []
        trend = []
        for half in (0, 1):
            seg = [d for d in ds_ if (d["ordered_week"] >= 52) == bool(half)]
            trend.append(round(float(np.mean([d["actual_days"] <= d["promised_days"] for d in seg])), 3) if seg else None)
        cats = [lk for lk in e.links if lk["supplier_id"] == sid]
        sups.append({**{k: s[k] for k in ("id", "name", "city", "country", "region", "lat", "lon")},
                     "deliveries": len(ds_), "lead_time_quantiles": q, "on_time_rate": round(float(np.mean(ratio <= 1)), 3) if len(ratio) else None,
                     "delivery_variability_cv": round(float(lt.std() / lt.mean()), 3) if len(lt) else None,
                     "on_time_first_year": trend[0], "on_time_second_year": trend[1],
                     "late_probability_open_orders": e.supplier_late.get(sid), "categories": [c["category_id"] for c in cats]})
    conc = []
    for cid, c in e.cat.items():
        shares = [lk["share"] for lk in e.links if lk["category_id"] == cid]
        conc.append({"category_id": cid, "category": c["name"], "suppliers": len(shares), "hhi": round(sum(x * x for x in shares), 3),
                     "single_source": len(shares) == 1})
    conc.sort(key=lambda r: -r["hhi"])
    repair = [{"center_id": k[0], "center": e.fac[k[0]]["name"], "category_id": k[1], "p10": v[0], "p50": v[1], "p90": v[2]} for k, v in e.repair_q.items()]
    nodes = [{"id": s["id"], "label": s["name"], "kind": "supplier"} for s in e.sup.values()] + \
            [{"id": c["id"], "label": c["name"], "kind": "category"} for c in e.cat.values()]
    edges = [{"source": lk["supplier_id"], "target": lk["category_id"], "share": lk["share"]} for lk in e.links]
    return envelope(request, {"suppliers": sups, "concentration": conc, "repair_turnaround": repair, "graph": {"nodes": nodes, "edges": edges},
                              "lead_time_model": {k: v for k, v in e.metrics["lead_time"].items() if k not in ("late_delivery",)},
                              "late_delivery_eval": e.metrics["lead_time"].get("late_delivery"), "freshness": e.freshness()}, provenance=PROV)


class ResilienceBody(BaseModel):
    scenario: str = Field(max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    mitigation: dict[str, float] = Field(default_factory=dict)
    save_as: str | None = Field(None, max_length=80)


@router.get("/api/resilience/scenarios")
def resilience_scenarios(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "resilience:scenarios", "INTERNAL")
    saved = db.query("SELECT id, kind, name, params_json, ts FROM saved_scenarios WHERE user_id = ? ORDER BY ts DESC LIMIT 30", (actor.id,))
    return envelope(request, {"scenarios": [{"id": k, **v} for k, v in sim.SCENARIOS.items()], "saved": saved})


@router.post("/api/resilience/simulate")
def resilience_simulate(request: Request, body: ResilienceBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "simulate", "resilience:simulate", "INTERNAL")
    params = {k: v for k, v in body.params.items() if isinstance(v, (int, float, str)) and len(str(v)) <= 40}
    try:
        r = sim.resilience(engine(), body.scenario, params, body.mitigation)
    except KeyError as err:
        raise ApiError(404, "not_found", "Unknown scenario.") from err
    except (ValueError, TypeError) as err:
        raise ApiError(422, "invalid_params", str(err)) from err
    if body.save_as:
        _save_scenario(actor, body.scenario, body.save_as, {"params": params, "mitigation": body.mitigation},
                       {k: {x: v[x] for x in ("peak_backlog_hours", "cost_p50_usd")} for k, v in r["results"].items()})
    return envelope(request, r, provenance=PROV)


def _save_scenario(actor: Actor, kind: str, name: str, params: dict[str, Any], result: Any) -> None:
    db.execute("INSERT INTO saved_scenarios VALUES (?,?,?,?,?,?,?)", (new_id("SCN"), actor.id, kind, name, db.jdump(params), db.jdump(result), now_iso()))
