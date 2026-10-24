"""Read models computed from the single synthetic database.

Every KPI, chart and table in the UI is produced by one of these functions, so
fleet totals, drilldowns, parts and work orders always agree.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from app.core import db
from app.core.util import DEMO_TODAY
from app.seed.generator import DEMO_VIBRATION_THRESHOLD

CRITICAL_VERIFY_DAYS = 30  # DOC-009 (fictional): critical stock counts older than 30 days are unverified


# ---------------------------------------------------------------- fleet

def fleet_overview() -> dict[str, Any]:
    aircraft = db.query("SELECT * FROM aircraft ORDER BY id")
    by_status = Counter(a["status"] for a in aircraft)
    by_type = Counter(a["type"] for a in aircraft)
    by_base = Counter(a["base"] for a in aircraft)
    open_wo = db.query(
        "SELECT aircraft_id, COUNT(*) n FROM work_orders WHERE status != 'closed' GROUP BY aircraft_id")
    open_by_ac = {r["aircraft_id"]: r["n"] for r in open_wo}
    latest = latest_health()
    anomalies = [a for a, h in latest.items() if h["above_threshold"]]
    health_values = [h["health_score"] for h in latest.values()]
    total_open = sum(open_by_ac.values())
    rows = []
    for a in aircraft:
        h = latest.get(a["id"], {})
        rows.append({**a, "health_score": h.get("health_score"), "vibration_7d": h.get("vibration_7d"),
                     "open_work_orders": open_by_ac.get(a["id"], 0), "above_threshold": h.get("above_threshold", False)})
    return {
        "total_aircraft": len(aircraft),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "by_base": dict(by_base),
        "available_pct": round(100 * by_status.get("in_service", 0) / len(aircraft), 1),
        "aog_count": by_status.get("aog", 0),
        "open_work_orders": total_open,
        "anomaly_aircraft": sorted(anomalies),
        "mean_health_score": round(statistics.mean(health_values), 1) if health_values else None,
        "aircraft": rows,
        "demo_threshold": {"vibration_index": DEMO_VIBRATION_THRESHOLD, "label": "Fictional demo threshold - not a maintenance limit"},
        "as_of": DEMO_TODAY,
    }


def latest_health() -> dict[str, dict[str, Any]]:
    """Demo health index from the last 7 days of synthetic telemetry (heuristic, not airworthiness)."""
    since = (date.fromisoformat(DEMO_TODAY) - timedelta(days=6)).isoformat()
    data = db.query(
        "SELECT aircraft_id, AVG(vibration_index) v, AVG(egt_delta_c) e, AVG(oil_pressure_index) o, "
        "SUM(CASE WHEN vibration_index IS NULL THEN 1 ELSE 0 END) missing "
        "FROM sensor_readings WHERE day >= ? GROUP BY aircraft_id", (since,))
    out = {}
    for r in data:
        v = r["v"] or 0
        penalty = max(0.0, (v - 0.45) * 60) + abs(r["e"] or 0) * 1.5 + abs((r["o"] or 1) - 1) * 80 + r["missing"] * 2
        out[r["aircraft_id"]] = {
            "health_score": round(max(0.0, min(100.0, 100 - penalty)), 1),
            "vibration_7d": round(v, 3),
            "above_threshold": v >= DEMO_VIBRATION_THRESHOLD,
        }
    return out


def aircraft_detail(ac_id: str) -> dict[str, Any] | None:
    a = db.query_one("SELECT * FROM aircraft WHERE id = ?", (ac_id,))
    if not a:
        return None
    a["health"] = latest_health().get(ac_id)
    a["open_work_orders"] = db.query(
        "SELECT * FROM work_orders WHERE aircraft_id = ? AND status != 'closed' ORDER BY opened DESC", (ac_id,))
    a["recent_events"] = db.query(
        "SELECT * FROM maintenance_events WHERE aircraft_id = ? ORDER BY date DESC LIMIT 10", (ac_id,))
    return a


def telemetry_series(ac_id: str, days: int = 90) -> list[dict[str, Any]]:
    since = (date.fromisoformat(DEMO_TODAY) - timedelta(days=days - 1)).isoformat()
    return db.query(
        "SELECT day, vibration_index, egt_delta_c, oil_pressure_index FROM sensor_readings "
        "WHERE aircraft_id = ? AND day >= ? ORDER BY day", (ac_id, since))


def fleet_vibration_band(days: int = 90) -> list[dict[str, Any]]:
    since = (date.fromisoformat(DEMO_TODAY) - timedelta(days=days - 1)).isoformat()
    return db.query(
        "SELECT day, AVG(vibration_index) mean, MAX(vibration_index) mx FROM sensor_readings "
        "WHERE day >= ? GROUP BY day ORDER BY day", (since,))


def maintenance_frequency_by_month() -> list[dict[str, Any]]:
    return db.query(
        "SELECT substr(date,1,7) month, COUNT(*) events, SUM(CASE WHEN type='unscheduled' THEN 1 ELSE 0 END) unscheduled "
        "FROM maintenance_events GROUP BY month ORDER BY month")


# ---------------------------------------------------------------- work orders

def work_orders(status: str | None = None, aircraft_id: str | None = None, labels: list[str] | None = None,
                limit: int = 100, offset: int = 0) -> dict[str, Any]:
    where, params = [], []
    if status:
        if status == "open":
            where.append("status != 'closed'")
        else:
            where.append("status = ?")
            params.append(status)
    if aircraft_id:
        where.append("aircraft_id = ?")
        params.append(aircraft_id)
    if labels is not None:
        where.append(f"classification IN ({','.join('?' * len(labels))})")
        params += labels
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.query_one(f"SELECT COUNT(*) n FROM work_orders{clause}", params)["n"]  # noqa: S608 - clause built from constants
    items = db.query(f"SELECT * FROM work_orders{clause} ORDER BY opened DESC, id LIMIT ? OFFSET ?", params + [limit, offset])  # noqa: S608
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def duplicate_work_orders() -> list[dict[str, Any]]:
    return db.query("SELECT * FROM work_orders WHERE duplicate_of IS NOT NULL")


def maintenance_history(ac_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return db.query("SELECT * FROM maintenance_events WHERE aircraft_id = ? ORDER BY date DESC LIMIT ?", (ac_id, limit))


# ---------------------------------------------------------------- parts

def _age_days(iso: str) -> int:
    return (date.fromisoformat(DEMO_TODAY) - date.fromisoformat(iso)).days


def part_availability(part_number: str | None = None) -> list[dict[str, Any]]:
    """Inventory reconciled across systems of record.

    For each part/location the most recent count wins. Critical parts whose
    latest count is older than 30 days are 'unverified'. Disagreeing sources
    are surfaced as conflicts instead of being silently merged.
    """
    params: list[Any] = []
    sql = "SELECT i.*, p.name, p.criticality, p.supplier_id, p.lead_time_days, p.unit_cost_usd FROM inventory i JOIN parts p USING(part_number)"
    if part_number:
        sql += " WHERE i.part_number = ?"
        params.append(part_number)
    records = db.query(sql + " ORDER BY i.part_number, i.location, i.last_verified DESC", params)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        grouped[(r["part_number"], r["location"])].append(r)
    out = []
    for (pn, loc), recs in grouped.items():
        latest = recs[0]
        age = _age_days(latest["last_verified"])
        critical = latest["criticality"] in ("critical", "high")
        verified = not (critical and age > CRITICAL_VERIFY_DAYS) and latest["lot"] != "UNKNOWN"
        qtys = {r["source_system"]: r["qty"] for r in recs}
        conflict = len(set(qtys.values())) > 1
        out.append({
            "part_number": pn, "name": latest["name"], "location": loc, "criticality": latest["criticality"],
            "verified_qty": latest["qty"] if verified else 0, "reported_qty_by_source": qtys,
            "latest_source": latest["source_system"], "last_verified": latest["last_verified"], "age_days": age,
            "verified": verified, "conflict": conflict, "lot": latest["lot"], "supplier_id": latest["supplier_id"],
            "lead_time_days": latest["lead_time_days"], "unit_cost_usd": latest["unit_cost_usd"],
            "note": ("Sources disagree; most recent physical count used. " if conflict else "")
                    + ("Count older than 30 days for a critical part: unverified (DOC-009). " if critical and age > CRITICAL_VERIFY_DAYS else "")
                    + ("Unknown lot: not traceable. " if latest["lot"] == "UNKNOWN" else ""),
        })
    return out


def part(part_number: str) -> dict[str, Any] | None:
    p = db.query_one("SELECT * FROM parts WHERE part_number = ?", (part_number,))
    if p:
        p["compatible_types"] = db.jload(p["compatible_types"], [])
        p["substitutes"] = db.jload(p["substitutes"], [])
    return p


def substitution_check(part_number: str) -> list[dict[str, Any]]:
    """Alternates are 'approved' only when a current authoritative document exists."""
    p = part(part_number)
    if not p:
        return []
    out = []
    for s in p["substitutes"]:
        doc = db.query_one("SELECT id, revision, status, provenance_sha256 FROM documents WHERE id = ?", (s["authority_doc"],)) if s["authority_doc"] else None
        approved = bool(doc and doc["status"] == "current" and doc["provenance_sha256"] and s["status"] == "approved")
        out.append({**s, "approved": approved, "authority": doc,
                    "reason": "Current engineering disposition on file." if approved else "No authoritative evidence of interchangeability; do not substitute."})
    return out


def supplier_reliability() -> list[dict[str, Any]]:
    rows_ = db.query(
        "SELECT s.id, s.name, COUNT(d.id) deliveries, SUM(CASE WHEN d.actual_days <= d.promised_days THEN 1 ELSE 0 END) on_time, "
        "AVG(d.actual_days - d.promised_days) avg_slip FROM suppliers s LEFT JOIN supplier_deliveries d ON d.supplier_id = s.id "
        "GROUP BY s.id ORDER BY s.id")
    recent_since = (date.fromisoformat(DEMO_TODAY) - timedelta(days=45)).isoformat()
    recent = {r["supplier_id"]: r for r in db.query(
        "SELECT supplier_id, COUNT(*) n, AVG(actual_days - promised_days) slip FROM supplier_deliveries WHERE ordered >= ? GROUP BY supplier_id",
        (recent_since,))}
    for r in rows_:
        r["on_time_pct"] = round(100 * r["on_time"] / r["deliveries"], 1) if r["deliveries"] else None
        r["avg_slip_days"] = round(r["avg_slip"] or 0, 2)
        rr = recent.get(r["id"])
        r["recent_avg_slip_days"] = round(rr["slip"], 2) if rr else None
        r["recent_deliveries"] = rr["n"] if rr else 0
        r.pop("avg_slip", None)
    return rows_


def supplier_slip_samples(supplier_id: str) -> list[int]:
    return [r["slip"] for r in db.query(
        "SELECT actual_days - promised_days slip FROM supplier_deliveries WHERE supplier_id = ? ORDER BY id", (supplier_id,))]


def critical_stock() -> list[dict[str, Any]]:
    avail = part_availability()
    totals: dict[str, int] = defaultdict(int)
    meta: dict[str, dict[str, Any]] = {}
    for a in avail:
        totals[a["part_number"]] += a["verified_qty"]
        meta[a["part_number"]] = a
    return [{"part_number": pn, "name": meta[pn]["name"], "criticality": meta[pn]["criticality"], "verified_total": q,
             "lead_time_days": meta[pn]["lead_time_days"]}
            for pn, q in sorted(totals.items()) if meta[pn]["criticality"] in ("critical", "high") and q <= 2]


# ---------------------------------------------------------------- people and slots

def qualified_technicians(base: str, required: list[str], on_date: str) -> list[dict[str, Any]]:
    out = []
    for t in db.query("SELECT * FROM technicians WHERE base = ? ORDER BY id", (base,)):
        quals = db.jload(t["qualifications"], [])
        valid = {q["name"] for q in quals if q["expires"] >= on_date}
        expired = {q["name"] for q in quals if q["expires"] < on_date}
        matched = [r for r in required if r in valid]
        if matched:
            out.append({"id": t["id"], "name": t["name"], "shift": t["shift"], "matched": matched,
                        "expired_relevant": [r for r in required if r in expired]})
    return out


def technicians_with_expired(base: str, required: list[str], on_date: str) -> list[dict[str, Any]]:
    out = []
    for t in db.query("SELECT * FROM technicians WHERE base = ? ORDER BY id", (base,)):
        quals = db.jload(t["qualifications"], [])
        exp = [q for q in quals if q["name"] in required and q["expires"] < on_date]
        if exp:
            out.append({"id": t["id"], "name": t["name"], "expired": exp})
    return out


def hangar_slots(base: str, status: str = "available") -> list[dict[str, Any]]:
    return db.query("SELECT * FROM hangar_slots WHERE base = ? AND status = ? ORDER BY start", (base, status))


# ---------------------------------------------------------------- analytics

def downtime_by_month() -> list[dict[str, Any]]:
    """Downtime hours per month, normalized per aircraft-day to handle the partial current month."""
    fleet = db.query_one("SELECT COUNT(*) n FROM aircraft")["n"]
    data = db.query("SELECT substr(date,1,7) month, SUM(downtime_hours) hours, COUNT(*) events FROM maintenance_events GROUP BY month ORDER BY month")
    first = db.query_one("SELECT MIN(day) d FROM sensor_readings")["d"]
    out = []
    for r in data:
        y, m = map(int, r["month"].split("-"))
        start = date(y, m, 1)
        end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        start = max(start, date.fromisoformat(first))
        end = min(end, date.fromisoformat(DEMO_TODAY))
        ndays = (end - start).days + 1
        out.append({**r, "hours": round(r["hours"], 1), "days_observed": ndays,
                    "hours_per_aircraft_day": round(r["hours"] / (fleet * ndays), 4)})
    return out


def downtime_causes(month: str) -> list[dict[str, Any]]:
    return db.query(
        "SELECT cause_category cause, COUNT(*) events, ROUND(SUM(downtime_hours),1) hours FROM maintenance_events "
        "WHERE substr(date,1,7) = ? GROUP BY cause ORDER BY hours DESC", (month,))


def bootstrap_ci(values: list[float], seed: int, n: int = 1000, alpha: float = 0.05) -> tuple[float, float, float]:
    import random

    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(n))
    lo = means[int(n * alpha / 2)]
    hi = means[int(n * (1 - alpha / 2)) - 1]
    return (statistics.mean(values), lo, hi)


def event_downtimes(month: str) -> list[float]:
    return [r["downtime_hours"] for r in db.query("SELECT downtime_hours FROM maintenance_events WHERE substr(date,1,7) = ?", (month,))]


def zscore(values: list[float], x: float) -> float:
    if len(values) < 2:
        return 0.0
    sd = statistics.pstdev(values)
    return 0.0 if sd == 0 else (x - statistics.mean(values)) / sd


def nan_safe(v: float | None) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


# ---------------------------------------------------------------- documents / governance helpers

def document_freshness() -> list[dict[str, Any]]:
    out = []
    for d in db.query("SELECT id, title, revision, effective_date, review_due, classification, source, status, provenance_sha256, superseded_by FROM documents ORDER BY id"):
        issues = []
        if d["status"] == "superseded":
            issues.append(f"Superseded by {d['superseded_by']}")
        if d["review_due"] < DEMO_TODAY:
            issues.append(f"Review overdue since {d['review_due']}")
        if not d["provenance_sha256"]:
            issues.append("Missing provenance hash")
        if d["classification"] == "UNKNOWN":
            issues.append("Classification not reviewed")
        d["issues"] = issues
        d["has_provenance"] = bool(d.pop("provenance_sha256"))
        out.append(d)
    return out


def incidents() -> list[dict[str, Any]]:
    return db.query("SELECT * FROM incidents ORDER BY opened DESC")


def applications() -> list[dict[str, Any]]:
    apps = db.query("SELECT * FROM applications ORDER BY id")
    for a in apps:
        a["interfaces"] = db.jload(a["interfaces"], [])
    return apps


def app_dependencies() -> list[dict[str, Any]]:
    return db.query("SELECT * FROM app_dependencies")
