"""Read-only domain queries. Every figure is computed from stored rows and returned
together with the sources it came from, so answers can cite them."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from app.config import get_settings
from app.db import row, rows
from app.enterprise.data import AS_OF, company, weeks


def src(kind: str, label: str, ref: str, detail: str = "") -> dict:
    return {"kind": kind, "label": label, "ref": ref, "detail": detail}


SYNTHETIC = "Synthetic enterprise dataset (fixed seed)"


def products() -> dict[str, dict]:
    return {p["sku"]: p for p in rows("SELECT * FROM ent_products ORDER BY sku")}


def _pct(new: float, old: float) -> float | None:
    return round((new - old) / old * 100, 1) if old else None


def _filters(province: str | None, sku: str | None, channel: str | None) -> tuple[str, list]:
    clauses, params = [], []
    for column, value in (("province", province), ("sku", sku), ("channel", channel)):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def sales_summary(window: int = 4, province: str | None = None, sku: str | None = None,
                  channel: str | None = None) -> dict:
    all_weeks = weeks()
    window = max(1, min(window, len(all_weeks) // 2))
    current, previous = all_weeks[-window:], all_weeks[-2 * window:-window]
    extra, params = _filters(province, sku, channel)

    def totals(ws: list[str]) -> dict:
        return row(f"SELECT COALESCE(SUM(units),0) AS units, COALESCE(SUM(revenue_cents),0) AS revenue"
                   f" FROM ent_sales_weekly WHERE week_start IN ({','.join('?' * len(ws))}){extra}", (*ws, *params))

    cur, prev = totals(current), totals(previous)
    marks = ",".join("?" * len(current))
    by_sku = rows(f"SELECT sku, SUM(units) AS units, SUM(revenue_cents) AS revenue FROM ent_sales_weekly WHERE"
                  f" week_start IN ({marks}){extra} GROUP BY sku ORDER BY revenue DESC", (*current, *params))
    by_province = rows(f"SELECT province, SUM(units) AS units, SUM(revenue_cents) AS revenue FROM ent_sales_weekly"
                       f" WHERE week_start IN ({marks}){extra} GROUP BY province ORDER BY revenue DESC",
                       (*current, *params))
    by_channel = rows(f"SELECT channel, SUM(units) AS units, SUM(revenue_cents) AS revenue FROM ent_sales_weekly"
                      f" WHERE week_start IN ({marks}){extra} GROUP BY channel ORDER BY revenue DESC",
                      (*current, *params))
    trend = rows(f"SELECT week_start, SUM(units) AS units, SUM(revenue_cents) AS revenue FROM ent_sales_weekly"
                 f" WHERE 1 = 1{extra} GROUP BY week_start ORDER BY week_start", tuple(params))
    names = products()
    for item in by_sku:
        item["name"] = names[item["sku"]]["name"]
    scope = ", ".join(x for x in (sku, province, channel) if x) or "all products, regions and channels"
    return {
        "scope": scope, "window_weeks": window, "current_weeks": [current[0], current[-1]],
        "previous_weeks": [previous[0], previous[-1]],
        "units": cur["units"], "revenue_cents": cur["revenue"],
        "previous_units": prev["units"], "previous_revenue_cents": prev["revenue"],
        "revenue_change_pct": _pct(cur["revenue"], prev["revenue"]),
        "units_change_pct": _pct(cur["units"], prev["units"]),
        "by_sku": by_sku, "by_province": by_province, "by_channel": by_channel, "trend": trend,
        "sources": [src("data", SYNTHETIC, "ent_sales_weekly",
                        f"weekly sales {current[0]}..{current[-1]} vs {previous[0]}..{previous[-1]}; {scope}")],
    }


def _campaign_rows() -> list[dict]:
    items = rows("SELECT * FROM ent_campaigns ORDER BY start")
    for item in items:
        item["skus"] = json.loads(item.pop("skus_json"))
    return items


def campaign_performance(campaign_id: str | None = None) -> dict:
    """Measured uplift: average weekly units of the promoted SKUs in the campaign region
    during the campaign, compared with the 4 weeks before it."""
    all_weeks = weeks()
    results = []
    for c in _campaign_rows():
        if campaign_id and c["id"] != campaign_id:
            continue
        if c["status"] != "completed":
            continue
        promo = [w for w in all_weeks if c["start"] <= w <= c["end"]]
        before = [w for w in all_weeks if w < c["start"]][-4:]
        marks = ",".join("?" * len(c["skus"]))

        def avg(ws: list[str], c=c, marks=marks) -> tuple[float, float]:
            r = row(f"SELECT COALESCE(SUM(units),0) AS u, COALESCE(SUM(revenue_cents),0) AS r FROM ent_sales_weekly"
                    f" WHERE province = ? AND sku IN ({marks}) AND week_start IN ({','.join('?' * len(ws))})",
                    (c["region"], *c["skus"], *ws))
            return r["u"] / len(ws), r["r"] / len(ws)

        promo_units, promo_rev = avg(promo)
        base_units, base_rev = avg(before)
        results.append({
            "id": c["id"], "name": c["name"], "mechanic": c["mechanic"], "region": c["region"], "skus": c["skus"],
            "start": c["start"], "end": c["end"],
            "baseline_weekly_units": round(base_units), "promo_weekly_units": round(promo_units),
            "unit_uplift_pct": _pct(promo_units, base_units),
            "baseline_weekly_revenue_cents": round(base_rev), "promo_weekly_revenue_cents": round(promo_rev),
            "revenue_change_pct": _pct(promo_rev, base_rev),
            "method": f"avg weekly units {promo[0]}..{promo[-1]} vs the 4 weeks before ({before[0]}..{before[-1]})",
        })
    return {"campaigns": results, "scheduled": [c for c in _campaign_rows() if c["status"] == "scheduled"],
            "sources": [src("data", SYNTHETIC, "ent_campaigns + ent_sales_weekly",
                            "uplift measured from weekly sales; no causal adjustment")]}


def live_storefront_orders() -> dict:
    """Real orders placed on the locally deployed storefront (commerce.db)."""
    path = get_settings().commerce_db
    empty = {"orders": 0, "paid_orders": 0, "units": 0, "free_units": 0, "revenue_cents": 0,
             "refunded_cents": 0, "redemptions": 0, "customers": 0}
    if not path.exists():
        return {**empty, "available": False, "sources": []}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        o = conn.execute("SELECT COUNT(*) AS n, SUM(status IN ('paid','partially_returned','returned','cancelled')) AS"
                         " paid, COALESCE(SUM(CASE WHEN status != 'payment_failed' THEN total_cents END),0) AS rev,"
                         " COALESCE(SUM(refunded_cents),0) AS ref, COUNT(DISTINCT customer_id) AS customers"
                         " FROM orders").fetchone()
        u = conn.execute("SELECT COUNT(*) AS units, COALESCE(SUM(is_free),0) AS free FROM order_units ou JOIN orders o"
                         " ON o.id = ou.order_id WHERE o.status != 'payment_failed'").fetchone()
        try:
            red = conn.execute("SELECT COUNT(*) FROM redemptions WHERE status = 'committed'").fetchone()[0]
        except sqlite3.OperationalError:
            red = 0
    finally:
        conn.close()
    return {"available": True, "orders": o["n"], "paid_orders": o["paid"] or 0, "units": u["units"],
            "free_units": u["free"], "revenue_cents": o["rev"], "refunded_cents": o["ref"], "redemptions": red,
            "customers": o["customers"],
            "sources": [src("live", "Live storefront orders (local commerce.db)", "storefront:orders",
                            "orders placed on the deployed FreshSip storefront, including demo traffic")]}


def inventory_status(warehouse: str | None = None, sku: str | None = None) -> dict:
    recent = weeks()[-4:]
    names = products()
    items = []
    for w in rows("SELECT * FROM ent_warehouses ORDER BY id"):
        if warehouse and w["id"] != warehouse:
            continue
        serves = json.loads(w["serves_json"])
        for s in rows("SELECT * FROM ent_stock WHERE warehouse = ? ORDER BY sku", (w["id"],)):
            if sku and s["sku"] != sku:
                continue
            weekly = row(f"SELECT COALESCE(SUM(units),0) AS u FROM ent_sales_weekly WHERE sku = ? AND province IN"
                         f" ({','.join('?' * len(serves))}) AND week_start IN ({','.join('?' * len(recent))})",
                         (s["sku"], *serves, *recent))["u"] / 4
            daily = weekly / 7
            cover = round(s["on_hand"] / daily, 1) if daily else None
            reorder_point = round(daily * (w["lead_time_days"] + w["safety_days"]))
            inbound = rows("SELECT po, units, eta FROM ent_inbound WHERE warehouse = ? AND sku = ? ORDER BY eta",
                           (w["id"], s["sku"]))
            if cover is not None and cover < w["lead_time_days"]:
                status = "critical"
            elif s["on_hand"] < reorder_point:
                status = "reorder"
            else:
                status = "ok"
            items.append({"warehouse": w["id"], "warehouse_name": w["name"], "sku": s["sku"],
                          "name": names[s["sku"]]["name"], "on_hand": s["on_hand"], "avg_daily_demand": round(daily, 1),
                          "days_of_cover": cover, "reorder_point": reorder_point,
                          "lead_time_days": w["lead_time_days"], "status": status, "inbound": inbound})
    order = {"critical": 0, "reorder": 1, "ok": 2}
    items.sort(key=lambda i: (order[i["status"]], i["days_of_cover"] or 0))
    sim = rows("SELECT sku, stock FROM sim_stock ORDER BY sku")
    return {
        "as_of": AS_OF, "items": items, "alerts": [i for i in items if i["status"] != "ok"],
        "ecommerce_allocation": sim,
        "method": "avg daily demand = last 4 weeks of sales in the provinces each DC serves / 28; "
                  "reorder point = demand × (lead time + safety days); critical when cover < lead time",
        "sources": [src("data", SYNTHETIC, "ent_stock + ent_sales_weekly + ent_inbound", f"stock snapshot {AS_OF}"),
                    src("live", "Inventory simulator (live e-commerce allocation)", "sim_stock",
                        "stock reserved by storefront checkouts")],
    }


def campaign_stock_risk() -> dict:
    """Projected stock at DC-TOR for the scheduled Ontario weekend campaign (labelled assumptions)."""
    cfg = company()["upcoming_campaign"]
    comparable = next((c for c in campaign_performance(cfg["comparable_campaign"])["campaigns"]), None)
    uplift = (comparable["unit_uplift_pct"] or 0) / 100 if comparable else 0
    recent = weeks()[-4:]
    days_to_start = (date.fromisoformat(cfg["start"]) - date.fromisoformat(AS_OF)).days
    inv = {i["sku"]: i for i in inventory_status("DC-TOR")["items"]}
    lines = []
    for sku in cfg["skus"]:
        weekly_on = row(f"SELECT COALESCE(SUM(units),0) AS u FROM ent_sales_weekly WHERE sku = ? AND province = ?"
                        f" AND week_start IN ({','.join('?' * len(recent))})", (sku, cfg["region"], *recent))["u"] / 4
        weekend_base = weekly_on * 2 / 7
        forecast = round(weekend_base * (1 + uplift))
        stock = inv[sku]
        arriving = sum(i["units"] for i in stock["inbound"] if i["eta"] <= cfg["start"])
        projected_raw = stock["on_hand"] - stock["avg_daily_demand"] * days_to_start + arriving
        projected = max(0, round(projected_raw))
        risk = "high" if projected < forecast else ("medium" if projected < forecast * 1.5 else "low")
        lines.append({"sku": sku, "name": stock["name"], "on_hand_now": stock["on_hand"],
                      "projected_at_start": projected, "weekend_forecast_units": forecast,
                      "shortfall_units": max(0, forecast - projected),
                      "stockout_before_start": projected_raw <= 0,
                      "inbound_before_start": arriving,
                      "next_inbound": stock["inbound"][0] if stock["inbound"] else None, "risk": risk})
    return {
        "campaign": cfg, "warehouse": "DC-TOR", "days_to_start": days_to_start,
        "assumed_uplift_pct": round(uplift * 100, 1), "lines": lines,
        "assumptions": [
            "Weekend baseline = last 4 weeks of Ontario sales × 2/7 (all channels).",
            f"Uplift taken from the most similar past campaign ({cfg['comparable_campaign']}, "
            f"{round(uplift * 100, 1)}% measured).",
            f"Stock depletes at the recent daily rate for the {days_to_start} days before the start; only inbound "
            "arriving by the start date counts.",
        ],
        "sources": [src("data", SYNTHETIC, "ent_stock + ent_sales_weekly + ent_inbound", "DC-TOR projection"),
                    src("data", SYNTHETIC, f"campaign {cfg['comparable_campaign']}", "comparable uplift")],
    }


def _norm(items: list[str]) -> list[str]:
    return sorted(i.strip().lower() for i in items)


def compliance_check(sku: str | None = None, channel: str | None = None) -> dict:
    names = products()
    records = {r["sku"]: r for r in rows("SELECT * FROM ent_product_records WHERE current = 1")}
    issues, checked = [], 0
    for listing in rows("SELECT * FROM ent_listings ORDER BY sku, channel"):
        if (sku and listing["sku"] != sku) or (channel and listing["channel"] != channel):
            continue
        checked += 1
        rec = records[listing["sku"]]
        rec_all, lst_all = _norm(json.loads(rec["allergens_json"])), _norm(json.loads(listing["allergens_json"]))
        rec_ing, lst_ing = _norm(json.loads(rec["ingredients_json"])), _norm(json.loads(listing["ingredients_json"]))
        base = {"sku": listing["sku"], "name": names[listing["sku"]]["name"], "channel": listing["channel"],
                "record_version": rec["version"], "listing_version": listing["record_version"], "note": listing["note"]}
        missing_allergens = sorted(set(rec_all) - set(lst_all))
        if missing_allergens:
            issues.append({**base, "severity": "critical", "rule": "allergen statement",
                           "detail": f"listing is missing declared allergen(s): {', '.join(missing_allergens)}"})
        if rec_ing != lst_ing:
            missing = sorted(set(rec_ing) - set(lst_ing))
            extra = sorted(set(lst_ing) - set(rec_ing))
            issues.append({**base, "severity": "warning", "rule": "ingredient list",
                           "detail": "ingredients differ from the approved record"
                                     + (f"; missing: {', '.join(missing)}" if missing else "")
                                     + (f"; not in record: {', '.join(extra)}" if extra else "")})
        if listing["record_version"] != rec["version"]:
            issues.append({**base, "severity": "warning", "rule": "record version",
                           "detail": f"listing built from record v{listing['record_version']},"
                                     f" current is v{rec['version']}"})
    issues.sort(key=lambda i: (i["severity"] != "critical", i["sku"], i["channel"]))
    return {"listings_checked": checked, "issues": issues,
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "method": "field-by-field comparison of each channel listing with the current approved product record",
            "sources": [src("record", "Approved product records", "ent_product_records", "Regulatory Affairs"),
                        src("data", "Channel listings (synthetic)", "ent_listings", "web, retail, marketplace")]}


def product_record(sku: str) -> dict | None:
    rec = row("SELECT * FROM ent_product_records WHERE sku = ? AND current = 1", (sku,))
    if not rec:
        return None
    rec["ingredients"] = json.loads(rec.pop("ingredients_json"))
    rec["allergens"] = json.loads(rec.pop("allergens_json"))
    rec["name"] = products()[sku]["name"]
    rec["sources"] = [src("record", f"Approved product record {sku} v{rec['version']}", f"ent_product_records:{sku}")]
    return rec


def executive_overview() -> dict:
    sales = sales_summary(4)
    perf = campaign_performance()
    inv = inventory_status()
    comp = compliance_check()
    risk = campaign_stock_risk()
    live = live_storefront_orders()
    top = sales["by_sku"][0] if sales["by_sku"] else None
    return {
        "label": "Synthetic enterprise data plus live demo records. Not real business results.",
        "sales": {k: sales[k] for k in ("units", "revenue_cents", "revenue_change_pct", "units_change_pct",
                                         "current_weeks", "previous_weeks", "trend", "by_province", "by_sku")},
        "top_product": top,
        "campaigns": perf["campaigns"], "scheduled_campaigns": perf["scheduled"],
        "inventory_alerts": inv["alerts"], "compliance": {k: comp[k] for k in ("critical", "warnings", "issues")},
        "campaign_stock_risk": risk["lines"], "live_storefront": live,
    }
