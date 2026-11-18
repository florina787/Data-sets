"""Executive Decision Memory analytics.

Outcome classification uses the recorded KPI values: progress = (observed - baseline) / (target - baseline);
delivered >= 95%, partially delivered >= 40%, otherwise not delivered; pending when no observation exists yet.
For decisions linked to measurable FLO data (e.g. D-0001 fee repositioning), the observed value is MEASURED from the
data products at query time. All statements are associations between decisions and KPI movements: they do not
establish causal impact (other drivers, e.g. markets and industry flows, change concurrently)."""
from __future__ import annotations

from datetime import date

from analytics.money import from_cents

CAUSALITY_CAVEAT = ("KPI movements after a decision are associations, not proof of causal impact; concurrent drivers "
                    "(markets, industry flows, pricing actions) are not controlled for.")


def measured_d0001(adapters) -> dict:
    """Average monthly net flows of the ten repriced Canadian equity mutual funds, 6 months before vs after 2025-11-30."""
    prods = {p["id"] for p in adapters.accounting.products() if p["strategy"] == "Canadian Equity" and p["vehicle"] == "Mutual Fund"}
    rows = [r for r in adapters.accounting.product_monthly() if r["product_id"] in prods]
    repriced = {r["product_id"] for r in rows if r["month"] == date(2025, 11, 30) and r["fee_bps"] < next(
        x["fee_bps"] for x in rows if x["product_id"] == r["product_id"] and x["month"] == date(2025, 10, 31))}

    def avg(m0, m1, ids):
        sel = [r for r in rows if r["product_id"] in ids and m0 <= r["month"] <= m1]
        months = len({r["month"] for r in sel}) or 1
        return float(from_cents(sum(r["subscriptions_cents"] - r["redemptions_cents"] for r in sel))) / 1e6 / months

    before = avg(date(2025, 5, 31), date(2025, 10, 31), repriced)
    after = avg(date(2025, 11, 30), date(2026, 4, 30), repriced)
    ctrl_ids = prods - repriced
    return {"repriced_funds": sorted(repriced), "avg_monthly_net_flows_before_cad_m": round(before, 2),
            "avg_monthly_net_flows_after_cad_m": round(after, 2),
            "comparison_group_before_cad_m": round(avg(date(2025, 5, 31), date(2025, 10, 31), ctrl_ids), 2),
            "comparison_group_after_cad_m": round(avg(date(2025, 11, 30), date(2026, 4, 30), ctrl_ids), 2),
            "method": "6-month averages before/after effective date; non-repriced Canadian equity funds as an uncontrolled comparison group."}


def classify(d: dict) -> str:
    if d.get("observed_value") is None:
        return "pending"
    base, tgt, obs = d["baseline_value"], d["target_value"], d["observed_value"]
    progress = 0 if tgt == base else (obs - base) / (tgt - base)
    return "delivered" if progress >= 0.95 else ("partially_delivered" if progress >= 0.4 else "not_delivered")


def decisions_view(adapters, as_of: date) -> list[dict]:
    out = []
    for d in adapters.warehouse.table("decisions"):
        row = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in d.items()}
        if d["id"] == "D-0001":
            meas = measured_d0001(adapters)
            row["observed_value"] = meas["avg_monthly_net_flows_after_cad_m"]
            row["baseline_value"] = meas["avg_monthly_net_flows_before_cad_m"]
            row["measurement"] = meas
        row["outcome_status"] = classify(row)
        row["open_follow_ups"] = [f for f in d["follow_ups"] if f["status"] == "open"]
        row["overdue_follow_ups"] = [f for f in row["open_follow_ups"] if f["due"] < as_of.isoformat()]
        row["past_deadline"] = d["deadline"] < as_of
        out.append(row)
    return out


def summary(adapters, as_of: date) -> dict:
    rows = decisions_view(adapters, as_of)
    inits = adapters.warehouse.table("initiatives")
    by = {}
    for r in rows:
        by[r["outcome_status"]] = by.get(r["outcome_status"], 0) + 1
    return {
        "counts_by_outcome": by,
        "delivered": [r for r in rows if r["outcome_status"] == "delivered"][:15],
        "behind_schedule_initiatives": [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in i.items()}
                                        for i in inits if i["status"] == "behind"],
        "unresolved_commitments": [{"decision_id": r["id"], "title": r["title"], **f} for r in rows for f in r["overdue_follow_ups"]][:25],
        "unresolved_commitment_count": sum(len(r["overdue_follow_ups"]) for r in rows),
        "caveat": CAUSALITY_CAVEAT,
    }
