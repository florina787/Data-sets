"""Practice analytics: advisor productivity, an advisor's own book health, and client retention.

Deterministic aggregates over the CRM, client positions and portfolio valuations. Advisor productivity is an enterprise
aggregate per advisor (employees, no client identification). Book health is computed only for one advisor's own book;
the tool layer passes the requesting principal's advisor id and never accepts one from the caller.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from analytics.money import from_cents
from analytics.service import _f, _lineage

KYC_MAX_AGE_DAYS = 730


def _client_value_cents(adapters, client_id: str) -> int:
    crm = adapters.crm
    v = sum(p["market_value_cents"] for p in crm.positions(client_id))
    for pf in crm.portfolios_for(client_id):
        v += adapters.portfolio.valuations(pf["id"])[-1]["mv_close_cents"]
    return v


def _retention(clients: list[dict], start: date, end: date) -> float | None:
    """Same definition as the semantic metric clients.retention."""
    active = [c for c in clients if c["onboarding_date"] < start and (c["closed_date"] is None or c["closed_date"] >= start)]
    closed = [c for c in active if c["closed_date"] is not None and c["closed_date"] <= end]
    return round(1 - len(closed) / len(active), 4) if active else None


def advisor_productivity(adapters) -> dict:
    ms = adapters.market.months()
    as_of, start = ms[-1], ms[-12]
    clients = adapters.crm.clients()
    by_adv: dict[str, list[dict]] = defaultdict(list)
    for c in clients:
        by_adv[c["advisor_id"]].append(c)
    inter = defaultdict(list)
    for i in adapters.crm.interactions():
        if i["ts"].date() >= start:
            inter[i["advisor_id"]].append(i)
    rows = []
    for a in adapters.crm.advisors():
        book = by_adv.get(a["id"], [])
        active = [c for c in book if c["status"] == "active"]
        aum = sum(_client_value_cents(adapters, c["id"]) for c in active)
        it = inter.get(a["id"], [])
        rows.append({"advisor_id": a["id"], "advisor": a["name"], "region": a["region"], "team": a["team"],
                     "active_clients": len(active), "book_aum": _f(from_cents(aum)),
                     "aum_per_client": _f(from_cents(aum // len(active))) if active else 0.0,
                     "interactions_12m": len(it), "interactions_per_client": round(len(it) / len(active), 2) if active else 0.0,
                     "follow_ups_flagged_12m": sum(1 for i in it if i["follow_up_required"]),
                     "negative_share": round(sum(1 for i in it if i["sentiment"] == "negative") / len(it), 4) if it else 0.0,
                     "new_clients_12m": sum(1 for c in book if start <= c["onboarding_date"] <= as_of),
                     "closed_12m": sum(1 for c in book if c["closed_date"] is not None and start <= c["closed_date"] <= as_of),
                     "kyc_stale": sum(1 for c in active if (as_of - c["kyc_last_review"]).days > KYC_MAX_AGE_DAYS),
                     "retention_12m": _retention(book, start, as_of)})
    rows.sort(key=lambda r: -r["book_aum"])
    aums = [r["book_aum"] for r in rows]
    q = max(1, len(rows) // 4)
    top_q, bottom_q = sum(aums[:q]) / q, sum(aums[-q:]) / q
    summary = {"advisors": len(rows), "as_of": as_of.isoformat(), "window_start": start.isoformat(),
               "total_book_aum": round(sum(aums), 2), "median_book_aum": round(median(aums), 2) if aums else 0.0,
               "median_active_clients": median([r["active_clients"] for r in rows]) if rows else 0,
               "top_quartile_avg_aum": round(top_q, 2), "bottom_quartile_avg_aum": round(bottom_q, 2),
               "top_to_bottom_quartile_ratio": round(top_q / bottom_q, 2) if bottom_q else None,
               "median_interactions_per_client": median([r["interactions_per_client"] for r in rows]) if rows else 0,
               "kyc_stale_total": sum(r["kyc_stale"] for r in rows), "follow_ups_flagged_total": sum(r["follow_ups_flagged_12m"] for r in rows)}
    return {"data": {"summary": summary, "advisors": rows},
            "lineage": _lineage(adapters, ["advisor.book_aum", "advisor.active_clients", "advisor.interactions", "clients.retention"],
                                ["crm", "advisor_analytics", "portfolio_management"],
                                "Per-advisor aggregates at the latest month-end; interactions over the trailing 12 months. Quartiles split advisors "
                                "ranked by book AUM. Activity counts describe workload, not advisor quality.")}


def book_health(adapters, advisor_id: str | None, kyc_max_age_days: int = KYC_MAX_AGE_DAYS) -> dict:
    ms = adapters.market.months()
    as_of, start = ms[-1], ms[-12]
    book = adapters.crm.clients(advisor_id) if advisor_id else []
    active = [c for c in book if c["status"] == "active"]
    trend = []
    for m in ms:
        trend.append({"month": m.isoformat(),
                      "active_clients": sum(1 for c in book if c["onboarding_date"] <= m and (c["closed_date"] is None or c["closed_date"] > m)),
                      "closures": sum(1 for c in book if c["closed_date"] == m)})
    at_risk, seg = [], defaultdict(lambda: [0, 0])
    retirement = []
    for c in active:
        it = adapters.crm.interactions(c["id"])
        signals = []
        if any(i["sentiment"] == "negative" and i["ts"].date() >= as_of - timedelta(days=182) for i in it):
            signals.append("negative_sentiment_6m")
        if any(i["follow_up_required"] and i["ts"].date() >= as_of - timedelta(days=90) for i in it):
            signals.append("follow_up_flagged_90d")
        kyc_age = (as_of - c["kyc_last_review"]).days
        if kyc_age > kyc_max_age_days:
            signals.append("kyc_stale")
        value = _client_value_cents(adapters, c["id"])
        seg[c["segment"]][0] += 1
        seg[c["segment"]][1] += value
        if signals:
            at_risk.append({"client_id": c["id"], "segment": c["segment"], "signals": signals, "signal_count": len(signals),
                            "client_value": _f(from_cents(value)), "kyc_age_days": kyc_age})
        if any(g["goal_type"] == "retirement" for g in adapters.crm.goals(c["id"])):
            retirement.append({"client_id": c["id"], "segment": c["segment"], "client_value": _f(from_cents(value))})
    at_risk.sort(key=lambda r: (-r["signal_count"], -r["client_value"]))
    retirement.sort(key=lambda r: -r["client_value"])
    counts = Counter(s for r in at_risk for s in r["signals"])
    data = {"advisor_id": advisor_id, "as_of": as_of.isoformat(), "active_clients": len(active),
            "book_value": _f(from_cents(sum(v[1] for v in seg.values()))),
            "closed_12m": sum(1 for c in book if c["closed_date"] is not None and start <= c["closed_date"] <= as_of),
            "retention_12m": _retention(book, start, as_of), "trend": trend,
            "segments": [{"segment": k, "clients": v[0], "value": _f(from_cents(v[1]))} for k, v in sorted(seg.items())],
            "signal_counts": {k: counts.get(k, 0) for k in ("negative_sentiment_6m", "follow_up_flagged_90d", "kyc_stale")},
            "at_risk_clients": at_risk[:15], "at_risk_total": len(at_risk), "retirement_goal_clients": retirement[:8],
            "kyc_max_age_days": kyc_max_age_days}
    return {"data": data, "lineage": _lineage(adapters, ["advisor.book_aum", "advisor.active_clients", "clients.retention", "clients.at_risk_signals"],
                                              ["crm", "portfolio_management"],
                                              "The requesting advisor's own book only. Signals are observable review prompts, not attrition predictions.")}


def retention_overview(adapters) -> dict:
    ms = adapters.market.months()
    as_of, start = ms[-1], ms[-12]
    clients = adapters.crm.clients()
    trend = []
    for m in ms:
        trend.append({"month": m.isoformat(),
                      "active_clients": sum(1 for c in clients if c["onboarding_date"] <= m and (c["closed_date"] is None or c["closed_date"] > m)),
                      "closures": sum(1 for c in clients if c["closed_date"] == m)})
    segs = sorted({c["segment"] for c in clients})
    by_segment = [{"segment": s, "retention_12m": _retention([c for c in clients if c["segment"] == s], start, as_of),
                   "closed_12m": sum(1 for c in clients if c["segment"] == s and c["closed_date"] is not None and start <= c["closed_date"] <= as_of)}
                  for s in segs]
    prior_start, prior_end = ms[0], ms[11]
    return {"data": {"as_of": as_of.isoformat(), "retention_12m": _retention(clients, start, as_of),
                     "retention_prior_12m": _retention(clients, prior_start, prior_end), "trend": trend, "by_segment": by_segment,
                     "closed_12m": sum(1 for c in clients if c["closed_date"] is not None and start <= c["closed_date"] <= as_of)},
            "lineage": _lineage(adapters, ["clients.retention"], ["crm"],
                                "Retention = 1 - closures in window / clients active at window start; prior window = the 12 months before.")}
