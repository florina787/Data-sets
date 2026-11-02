"""3.0 intents for the hybrid router: high-precision rules + deterministic slot extraction + slot-carrying follow-ups.

Runs after the policy and greeting stages (so injection/export attempts are still caught first) and before the 2.0 family rules.
Patterns are deliberately specific so the four 2.0 signature questions keep their routes (verified by the 2.0 evaluation sets).
"""

from __future__ import annotations

import re
from typing import Any

INTENTS = {
    "global_shortages": "Global component shortages",
    "demand_forecast": "Component demand forecast",
    "supplier_delays": "Supplier delay map",
    "supply_delay_impact": "Supplier delay impact",
    "component_degradation": "Component degradation (digital twin)",
    "resilience_scenario": "Operational resilience scenario",
    "forecast_evidence": "Forecast evidence",
    "forecast_accuracy": "Historical forecast accuracy",
    "agent_trace": "Agent execution graph",
    "memory_recall": "Previous investigation",
    "visual_analysis": "Visual analysis lab",
    "change_impact": "Software change impact",
}

RULES: dict[str, list[str]] = {
    "agent_trace": [r"(agent|execution) (execution )?graph|which agents (ran|were used|worked)|show (me )?the (agent|execution) (trace|timeline)|agent trace"],
    "memory_recall": [r"(previous|last|earlier|prior) (investigation|question|analysis|conversation|session|query)|what did (i|we) ask|"
                      r"what happened (in|with) my (previous|last)|remind me what"],
    "visual_analysis": [r"\b(drone|uav|quadcopter)s?\b.{0,40}\b(video|footage|image|photo|frame|clip)|\b(video|footage|image|photo|frame|clip)s?\b.{0,40}\b(drone|uav)"],
    "change_impact": [r"(software|code|module|interface|api|function|class|release|commit).{0,60}(affected|impact|break|regression|depend)|"
                      r"(dependenc(y|ies)|tests?) .{0,40}(affected|impacted)|change[- ]impact"],
    "forecast_accuracy": [r"(historical|past|backtest|how accurate|accuracy|calibrat|\bmae\b|\brmse\b|error).{0,40}(forecast|prediction|model)s?|"
                          r"(forecast|prediction|model)s?.{0,30}(accuracy|accurate|backtest|calibrat|error)"],
    "forecast_evidence": [r"(evidence|support|based on|why should (i|we) trust|assumptions?|justif).{0,40}(forecast|prediction|projection)|"
                          r"(forecast|prediction).{0,30}(evidence|supported|assumptions)"],
    "supply_delay_impact": [r"(what happens|impact|affect|effect|consequence|what if|if).{0,80}(supplier|vendor|delivery).{0,60}(delay|late|slip)|"
                            r"(supplier|vendor).{0,60}(delay|late|slip).{0,80}(schedule|maintenance|impact|affect)|\d+[- ]day (delivery |supplier )?delay"],
    "supplier_delays": [r"(supplier|vendor)s?.{0,30}(delay|late|lead[- ]time|on[- ]time|reliab)|(delay|late)s?.{0,20}(supplier|vendor)"],
    "resilience_scenario": [r"(simulate|what if|scenario|stress[- ]test).{0,60}(outage|strike|storm|weather|workforce|staff|engineer shortage|surge|"
                            r"software outage|logistics|facility)|maintenance planning scenarios?|compare .{0,30}(planning|resilience|recovery) scenarios?|"
                            r"(baseline|disruption) (vs|versus|and) (disruption|recovery)"],
    "component_degradation": [r"degrad|remaining useful life|\brul\b|health (trend|index)|wear(ing)? (trend|out)|digital twin|"
                              r"(component|unit|part)'?s? (health|trend|condition)"],
    "global_shortages": [r"short(age|fall)s?|stock[- ]?outs?|run(ning)? out|deplet|inventory (risk|gap|forecast)"],
    "demand_forecast": [r"(forecast|predict|project|expect)\w*.{0,50}(demand|removals?|replacements?|consumption|usage|need)|"
                        r"(demand|removals?|replacements?).{0,40}(forecast|next \d+|coming|upcoming)|highest (predicted )?(maintenance )?demand|"
                        r"components? .{0,30}(most|highest).{0,20}(demand|maintenance)"],
}
# A 2.0 aircraft question (AC-xxx) keeps its 2.0 route unless the 3.0 cue is explicit.
EXPLICIT_3 = re.compile(r"(?i)global|region|europe|asia|america|africa|middle east|supplier|forecast|shortage|stock|digital twin|component|"
                        r"drone|software|agent|previous|accuracy|scenario|degrad")
AIRCRAFT = re.compile(r"\bAC-\d{3}\b", re.I)
# 2.0 questions that mention suppliers in a parts-criticality or readiness/cost sense keep their 2.0 routes (parts_status, executive)
# unless an explicit 3.0 cue (map, region, forecast horizon, N-day delay, maintenance schedule) is present.
VETO = {"supplier_delays": re.compile(r"(?i)critic|stock|reliab|readiness|\bcost"),
        "supply_delay_impact": re.compile(r"(?i)readiness|\bcost")}
KEEP_3 = re.compile(r"(?i)\bmap\b|global|europe|asia|america|africa|middle east|region|\d+[- ]?day|schedule|forecast|lead[- ]time")

CATEGORY_WORDS = [
    ("hydraulic_accumulator", r"hydraulic accumulators?"), ("hydraulic_pump", r"hydraulic pumps?"), ("landing_gear_actuator", r"landing[- ]gear actuators?|gear actuators?"),
    ("fuel_control_unit", r"fuel control units?|\bfcus?\b"), ("fuel_pump", r"fuel pumps?"), ("avionics_module", r"avionics modules?"),
    ("engine_temp_sensor", r"(engine )?temperature sensors?|\begt sensors?"), ("cabin_env_system", r"cabin environmental|environmental control|\becs\b"),
    ("electrical_generator", r"generators?"), ("cooling_component", r"cooling"), ("comm_equipment", r"communication|comms? equipment|radios?"),
    ("apu", r"auxiliary power|\bapus?\b"), ("brake_assembly", r"brakes?"), ("bleed_air_valve", r"bleed"), ("flight_control_computer", r"flight control computers?"),
    ("weather_radar", r"weather radar|radars?"), ("oxygen_system", r"oxygen"), ("starter_motor", r"starters?"),
    ("cabin_pressure_controller", r"(cabin )?pressur\w* controllers?"), ("navigation_receiver", r"navigation receivers?|nav receivers?|gnss|gps"),
]
FAMILY_WORDS = [("Hydraulics", r"hydraulic"), ("Landing gear", r"landing gear"), ("Avionics", r"avionic"), ("Fuel", r"\bfuel\b"),
                ("Electrical", r"electrical"), ("Environmental", r"environmental"), ("Communications", r"communication")]
REGION_WORDS = [("Europe", r"europe|european|\beu\b|emea"), ("North America", r"north america|\bus\b|usa|united states|canada|american"),
                ("Middle East", r"middle east|gulf|\buae\b|dubai"), ("Asia-Pacific", r"asia|apac|pacific|australia|singapore|japan"),
                ("Latin America", r"latin america|south america|latam|chile"), ("Africa", r"africa|kenya")]
SUPPLIER_WORDS = [("S1", r"veltrion|\bs1\b"), ("S2", r"corvalis|\bs2\b"), ("S3", r"tessarine|\bs3\b"), ("S4", r"meridane|\bs4\b"),
                  ("S5", r"kestrava|\bs5\b"), ("S6", r"nordvik|\bs6\b"), ("S7", r"lumora|\bs7\b"), ("S8", r"duneval|\bs8\b")]
HORIZONS = (7, 14, 30, 60, 90)
FOLLOW = re.compile(r"(?i)^\s*(and|what about|how about|same for|now|instead|ok,? (and|now)|then)\b|^\s*(for|in|over) (the )?(next|coming)|"
                    r"^\s*(next|over the next) \d+|^\s*(only|just) |\b(those|that|them|it|these)\b")


def _snap(days: int) -> int:
    return min(HORIZONS, key=lambda h: abs(h - days))


def slots(q: str) -> dict[str, Any]:
    ql = q.lower()
    out: dict[str, Any] = {}
    for cid, pat in CATEGORY_WORDS:
        if re.search(pat, ql):
            out["category"] = cid
            break
    if "category" not in out:
        for fam, pat in FAMILY_WORDS:
            if re.search(pat, ql):
                out["family"] = fam
                break
    for reg, pat in REGION_WORDS:
        if re.search(pat, ql):
            out["region"] = reg
            break
    m = re.search(r"(\d{1,3})\s*(days?|d\b)", ql)
    w = re.search(r"(\d{1,2})\s*weeks?", ql)
    mo = re.search(r"(\d{1,2}|one|two|three)\s*months?|quarter", ql)
    delay = re.search(r"(\d{1,3})[- ]?day (delivery |supplier |shipping )?(delay|slip|late)|delay(ed)? (of|by) (\d{1,3}) days?|(\d{1,3}) days? (late|delay)", ql)
    if delay:
        out["delay_days"] = int(next(g for g in (delay.group(1), delay.group(6), delay.group(7)) if g))
    if m and not (delay and int(m.group(1)) == out.get("delay_days")):
        out["horizon_days"] = _snap(int(m.group(1)))
    elif w:
        out["horizon_days"] = _snap(int(w.group(1)) * 7)
    elif mo:
        n = {"one": 1, "two": 2, "three": 3}.get(mo.group(1) or "", None) if mo.group(1) else 3
        n = n or (int(mo.group(1)) if mo.group(1) and mo.group(1).isdigit() else 3)
        out["horizon_days"] = _snap(n * 30)
    for sid, pat in SUPPLIER_WORDS:
        if re.search(pat, ql):
            out["supplier_id"] = sid
            break
    u = re.search(r"\bU-F\d{2}-C\d{2}-P\d-\d{1,2}\b", q, re.I)
    if u:
        out["unit_id"] = u.group(0).upper()
    t = re.search(r"(app(\.[a-z_]+)+|/api/[a-z0-9_/\-{}]+|[A-Z][A-Za-z]+(Spec|Engine|Registry|Gateway|Args|State))", q)
    if t:
        out["target"] = t.group(0)
    return out


def score(q: str) -> list[tuple[str, int]]:
    hits = []
    for label, pats in RULES.items():
        for p in pats:
            m = re.search(p, q, re.I)
            if m:
                hits.append((label, m.start()))
                break
    return hits


def detect(q: str, context: dict[str, Any] | None) -> tuple[str, dict[str, Any], str, bool] | None:
    """Return (intent, slots, reason, is_follow_up) or None to let the 2.0 router continue."""
    s = slots(q)
    prev = (context or {}).get("workflow")
    if prev in INTENTS and FOLLOW.search(q) and len(q.split()) <= 14:
        hits = score(q)
        new_intent = hits[0][0] if hits and hits[0][0] != prev and len(hits) == 1 and not set(s) - {"horizon_days", "region", "category", "family"} else None
        keep = ("category", "family", "region", "horizon_days", "supplier_id", "delay_days", "unit_id", "target")
        merged = {**{k: v for k, v in ((context or {}).get("entities") or {}).items() if k in keep}, **s}
        if "category" in s:
            merged.pop("family", None)
        if "family" in s:
            merged.pop("category", None)
        return (new_intent or prev, merged, f"Follow-up to the previous {INTENTS[prev].lower()} question; slots carried over and updated with {sorted(s) or 'none'}.", True)
    hits = score(q)
    if not hits:
        return None
    if AIRCRAFT.search(q) and not EXPLICIT_3.search(q):
        return None
    hits = [h for h in hits if not (VETO.get(h[0]) and VETO[h[0]].search(q) and not KEEP_3.search(q))]
    if not hits:
        return None
    # order of RULES encodes precedence for overlapping cues (e.g. "supplier delay ... what happens" -> impact, not the map)
    order = list(RULES)
    best = sorted(hits, key=lambda h: order.index(h[0]))[0][0]
    return best, s, f"3.0 rule match '{best}'; slots {s or '{}'}.", False
