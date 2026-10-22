"""Financial Intelligence services: deterministic computations over integration adapters.

Every public function returns {"data": ..., "lineage": {...}}. The LLM layer consumes these outputs; it never
calculates financial figures itself.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from analytics import aum as aum_mod
from analytics import profitability, returns, revenue, risk
from analytics.money import from_cents
from analytics.semantic import SEMANTIC_LAYER_VERSION, describe
from integrations.mock.adapters import Adapters

CONC_LIMIT = 0.10


def _lineage(adapters: Adapters, metric_ids: list[str], systems: list[str], methodology: str, as_of: date | None = None) -> dict:
    infos = {a["category"]: a for a in adapters.catalog()}
    return {
        "metrics": describe(*metric_ids),
        "sources": [infos[s] for s in systems if s in infos],
        "methodology": methodology,
        "as_of": (as_of or adapters.market.months()[-1]).isoformat(),
        "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": adapters.store.version,
        "semantic_layer_version": SEMANTIC_LAYER_VERSION,
        "synthetic": True,
    }


def window_months(adapters: Adapters, months: int = 24, end: date | None = None) -> list[date]:
    all_m = adapters.market.months()
    if end is not None:
        all_m = [m for m in all_m if m <= end]
    months = max(1, min(months, len(all_m)))
    return all_m[-months:]


def _product_filter(adapters: Adapters, filters: dict | None) -> dict[str, dict]:
    f = {k: v for k, v in (filters or {}).items() if v}
    out = {}
    for p in adapters.accounting.products():
        if any(str(p.get(k)) != str(v) for k, v in f.items() if k in ("asset_class", "vehicle", "region", "strategy")):
            continue
        out[p["id"]] = p
    return out


def _pm_rows(adapters: Adapters, products: dict[str, dict], ms: list[date]) -> list[dict]:
    mset = set(ms)
    return [r for r in adapters.accounting.product_monthly() if r["product_id"] in products and r["month"] in mset]


def _fin(adapters: Adapters, ms: list[date]) -> dict[date, dict[str, dict]]:
    out: dict[date, dict[str, dict]] = defaultdict(dict)
    mset = set(ms)
    for r in adapters.erp.finance_monthly():
        if r["month"] in mset:
            out[r["month"]][r["line"]] = r
    return out


def _f(x: Decimal | float, nd: int = 2) -> float:
    return round(float(x), nd)


# ---------------------------------------------------------------------------------------------- executive
def executive_kpis(adapters: Adapters, months: int = 12) -> dict:
    ms = window_months(adapters, months)
    products = _product_filter(adapters, None)
    rows = _pm_rows(adapters, products, ms)
    rf = aum_mod.roll_forward_from_rows(rows, ms[0], ms[-1])
    last = [r for r in rows if r["month"] == ms[-1]]
    fea = from_cents(sum(r["aum_close_cents"] for r in last if r["fee_bps"] > 0))
    rev = from_cents(sum(r["revenue_cents"] for r in rows))
    fin = _fin(adapters, ms)
    opex = from_cents(sum(v["actual_cents"] for m in ms for k, v in fin[m].items() if k.startswith("expense_")))
    ledger_rev = from_cents(sum(fin[m]["revenue_management_fees"]["actual_cents"] for m in ms))
    avg_aum = sum((from_cents(r["aum_open_cents"] + r["aum_close_cents"]) / 2 for r in rows), Decimal(0)) / len(ms)
    margin = profitability.operating_margin(ledger_rev, opex)
    # prior window for comparison
    prior_ms = [m for m in adapters.market.months() if m < ms[0]][-len(ms):]
    prior = None
    if len(prior_ms) == len(ms):
        prow = _pm_rows(adapters, products, prior_ms)
        pfin = _fin(adapters, prior_ms)
        p_rev = from_cents(sum(pfin[m]["revenue_management_fees"]["actual_cents"] for m in prior_ms))
        p_opex = from_cents(sum(v["actual_cents"] for m in prior_ms for k, v in pfin[m].items() if k.startswith("expense_")))
        p_avg = sum((from_cents(r["aum_open_cents"] + r["aum_close_cents"]) / 2 for r in prow), Decimal(0)) / len(prior_ms)
        prior = {"revenue": _f(p_rev), "operating_expenses": _f(p_opex),
                 "operating_margin": _f(profitability.operating_margin(p_rev, p_opex), 4),
                 "revenue_yield_bps": _f(revenue.revenue_yield_bps(p_rev, p_avg, len(prior_ms))),
                 "aum_close": _f(from_cents(sum(r["aum_close_cents"] for r in prow if r["month"] == prior_ms[-1])))}
    clients = adapters.crm.clients()
    start_cut = ms[0]
    active_at_start = [c for c in clients if c["onboarding_date"] < start_cut and (c["closed_date"] is None or c["closed_date"] >= start_cut)]
    closed_in = [c for c in active_at_start if c["closed_date"] is not None and c["closed_date"] <= ms[-1]]
    retention = 1 - len(closed_in) / len(active_at_start) if active_at_start else None
    inits = adapters.warehouse.table("initiatives")
    risks = adapters.warehouse.table("risk_register")
    ce = adapters.warehouse.table("compliance_events")
    data = {
        "period": {"start": ms[0].isoformat(), "end": ms[-1].isoformat(), "months": len(ms), "currency": "CAD"},
        "total_aum": _f(rf.close), "aum_open": _f(rf.open), "aum_growth": _f(rf.close / rf.open - 1, 4),
        "net_flows": _f(rf.net_flows), "subscriptions": _f(rf.subscriptions), "redemptions": _f(rf.redemptions),
        "market_movement": _f(rf.market), "fee_earning_assets": _f(fea),
        "management_fee_revenue": _f(ledger_rev), "operating_expenses": _f(opex), "operating_income": _f(ledger_rev - opex),
        "operating_margin": _f(margin, 4), "revenue_yield_bps": _f(revenue.revenue_yield_bps(rev, avg_aum, len(ms))),
        "client_retention": round(retention, 4) if retention is not None else None,
        "initiatives": {"count": len(inits), "behind": sum(1 for i in inits if i["status"] == "behind"),
                        "avg_progress": round(sum(i["progress_pct"] for i in inits) / max(1, len(inits)), 1)},
        "enterprise_risk": {"high_risks": sum(1 for r in risks if r["likelihood"] * r["impact"] >= 12),
                            "open_critical_compliance": sum(1 for e in ce if e["severity"] in ("high", "critical") and e["status"] != "closed")},
        "prior_period": prior,
        "revenue_reconciliation": {"product_level_revenue": _f(rev), "ledger_revenue": _f(ledger_rev),
                                   "difference": _f(ledger_rev - rev), "balanced": ledger_rev == rev},
    }
    return {"data": data, "lineage": _lineage(adapters, ["aum.total", "aum.growth", "flows.net", "aum.fee_earning",
                                                          "revenue.management_fees", "expenses.operating", "margin.operating",
                                                          "revenue.yield_bps", "clients.retention", "strategy.initiative_progress",
                                                          "risk.enterprise_score"],
                                              ["portfolio_accounting", "erp", "crm", "data_warehouse"],
                                              f"Trailing {len(ms)} month-ends ending {ms[-1]}; prior period = the preceding {len(ms)} months.", ms[-1])}


def aum_trend(adapters: Adapters, months: int = 24, filters: dict | None = None, group_by: str = "asset_class") -> dict:
    ms = window_months(adapters, months)
    products = _product_filter(adapters, filters)
    series: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for r in _pm_rows(adapters, products, ms):
        series[products[r["product_id"]][group_by]][r["month"]] += r["aum_close_cents"]
    total = [_f(from_cents(sum(series[k][m] for k in series))) for m in ms]
    return {"data": {"months": [m.isoformat() for m in ms], "group_by": group_by,
                     "series": [{"name": k, "values": [_f(from_cents(v[m])) for m in ms]} for k, v in sorted(series.items())],
                     "total": total},
            "lineage": _lineage(adapters, ["aum.total"], ["portfolio_accounting"], f"Month-end AUM grouped by {group_by}.")}


def aum_waterfall(adapters: Adapters, months: int = 12, filters: dict | None = None) -> dict:
    ms = window_months(adapters, months)
    products = _product_filter(adapters, filters)
    rows = _pm_rows(adapters, products, ms)
    rf = aum_mod.roll_forward_from_rows(rows, ms[0], ms[-1])
    recon = aum_mod.reconcile("enterprise", rf)
    breaks = []
    for r in rows:
        prf = aum_mod.RollForward(from_cents(r["aum_open_cents"]), from_cents(r["subscriptions_cents"]),
                                  from_cents(r["redemptions_cents"]), from_cents(r["market_cents"]), from_cents(r["aum_close_cents"]))
        res = aum_mod.reconcile(f"{r['product_id']}:{r['month']}", prf)
        if not res.balanced:
            breaks.append({"key": res.key, "difference": str(res.difference)})
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_class[products[r["product_id"]]["asset_class"]].append(r)
    drill = []
    for ac, rr in sorted(by_class.items()):
        x = aum_mod.roll_forward_from_rows(rr, ms[0], ms[-1])
        drill.append({"asset_class": ac, **{k: _f(getattr(x, k)) for k in ("open", "subscriptions", "redemptions", "market", "close")},
                      "net_flows": _f(x.net_flows)})
    return {"data": {"period": [ms[0].isoformat(), ms[-1].isoformat()], "steps": aum_mod.waterfall(rf),
                     "reconciliation": {"balanced": recon.balanced, "difference": str(recon.difference),
                                        "product_month_breaks": breaks, "checked_rows": len(rows)},
                     "organic_growth_annualized": _f(aum_mod.organic_growth_rate(rf, len(ms)), 4), "by_asset_class": drill},
            "lineage": _lineage(adapters, ["aum.total", "flows.net", "aum.market_movement"], ["portfolio_accounting"],
                                "Opening AUM + subscriptions - redemptions + market movement = closing AUM; every product-month reconciled to the cent.")}


def revenue_expenses(adapters: Adapters, months: int = 24) -> dict:
    ms = window_months(adapters, months)
    fin = _fin(adapters, ms)
    lines = sorted({k for m in ms for k in fin[m] if k.startswith("expense_")})
    rev = [_f(from_cents(fin[m]["revenue_management_fees"]["actual_cents"])) for m in ms]
    exp = {ln: [_f(from_cents(fin[m][ln]["actual_cents"])) for m in ms] for ln in lines}
    tot = [round(sum(exp[ln][i] for ln in lines), 2) for i in range(len(ms))]
    return {"data": {"months": [m.isoformat() for m in ms], "revenue": rev, "expenses": exp, "total_expenses": tot,
                     "operating_income": [round(r - e, 2) for r, e in zip(rev, tot)]},
            "lineage": _lineage(adapters, ["revenue.management_fees", "expenses.operating"], ["erp"], "General-ledger actuals by month.")}


def net_flows(adapters: Adapters, months: int = 24, filters: dict | None = None, group_by: str = "vehicle") -> dict:
    ms = window_months(adapters, months)
    products = _product_filter(adapters, filters)
    acc: dict[str, dict[date, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in _pm_rows(adapters, products, ms):
        a = acc[products[r["product_id"]][group_by]][r["month"]]
        a[0] += r["subscriptions_cents"]
        a[1] += r["redemptions_cents"]
    series = [{"name": k, "subscriptions": [_f(from_cents(v[m][0])) for m in ms],
               "redemptions": [_f(from_cents(v[m][1])) for m in ms],
               "net": [_f(from_cents(v[m][0] - v[m][1])) for m in ms]} for k, v in sorted(acc.items())]
    totals = {s["name"]: round(sum(s["net"]), 2) for s in series}
    return {"data": {"months": [m.isoformat() for m in ms], "group_by": group_by, "series": series, "net_by_group": totals},
            "lineage": _lineage(adapters, ["flows.subscriptions", "flows.redemptions", "flows.net"], ["portfolio_accounting"],
                                f"Monthly gross and net flows grouped by {group_by}.")}


def product_profitability(adapters: Adapters, months: int = 12) -> dict:
    ms = window_months(adapters, months)
    products = _product_filter(adapters, None)
    rows = _pm_rows(adapters, products, ms)
    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["product_id"], {"revenue": Decimal(0), "aum": Decimal(0)})
        a["revenue"] += from_cents(r["revenue_cents"])
        a["aum"] += from_cents(r["aum_open_cents"] + r["aum_close_cents"]) / 2 / len(ms)
    fin = _fin(adapters, ms)
    total_exp = from_cents(sum(v["actual_cents"] for m in ms for k, v in fin[m].items() if k.startswith("expense_")))
    dist = from_cents(sum(fin[m]["expense_distribution"]["actual_cents"] for m in ms))
    plist = [dict(id=pid, name=products[pid]["name"], vehicle=products[pid]["vehicle"], asset_class=products[pid]["asset_class"],
                  revenue=a["revenue"], avg_aum=a["aum"]) for pid, a in agg.items()]
    contrib = profitability.product_contribution(plist, total_exp, dist, len(ms))
    tree: dict[str, list] = defaultdict(list)
    for c, p in zip(contrib, plist):
        tree[c["asset_class"]].append({"id": c["id"], "name": c["name"], "vehicle": c["vehicle"], "revenue": _f(c["revenue"]),
                                       "contribution": _f(c["contribution"]), "margin": _f(c["margin"], 4) if c["margin"] is not None else None,
                                       "avg_aum": _f(p["avg_aum"]), "fee_bps": products[c["id"]]["mgmt_fee_bps"]})
    return {"data": {"period": [ms[0].isoformat(), ms[-1].isoformat()],
                     "tree": [{"name": k, "children": sorted(v, key=lambda x: -x["revenue"])} for k, v in sorted(tree.items())]},
            "lineage": _lineage(adapters, ["product.contribution"], ["portfolio_accounting", "erp"],
                                "Illustrative management allocation: revenue - 40 bp trailer (mutual funds) - shared costs by revenue share.")}


def margin_trend(adapters: Adapters, months: int = 24) -> dict:
    ms = window_months(adapters, months)
    fin = _fin(adapters, ms)
    rows = _pm_rows(adapters, _product_filter(adapters, None), ms)
    avg_aum: dict[date, Decimal] = defaultdict(Decimal)
    for r in rows:
        avg_aum[r["month"]] += from_cents(r["aum_open_cents"] + r["aum_close_cents"]) / 2
    out_m, out_y = [], []
    for m in ms:
        rv = from_cents(fin[m]["revenue_management_fees"]["actual_cents"])
        ex = from_cents(sum(v["actual_cents"] for k, v in fin[m].items() if k.startswith("expense_")))
        out_m.append(_f(profitability.operating_margin(rv, ex), 4))
        out_y.append(_f(revenue.revenue_yield_bps(rv, avg_aum[m], 1)))
    return {"data": {"months": [m.isoformat() for m in ms], "operating_margin": out_m, "revenue_yield_bps": out_y},
            "lineage": _lineage(adapters, ["margin.operating", "revenue.yield_bps"], ["erp", "portfolio_accounting"], "Monthly operating margin and annualized revenue yield.")}


def revenue_attribution(adapters: Adapters, months: int = 12) -> dict:
    """Compare the trailing window with the preceding window of equal length (volume / mix / fee-change effects)."""
    all_m = adapters.market.months()
    months = min(months, len(all_m) // 2)
    p1m, p0m = all_m[-months:], all_m[-2 * months:-months]
    products = _product_filter(adapters, None)

    def agg(ms):
        out = {}
        for r in _pm_rows(adapters, products, ms):
            a = out.setdefault(r["product_id"], [Decimal(0), Decimal(0)])
            a[0] += from_cents(r["aum_open_cents"] + r["aum_close_cents"]) / 2 / len(ms)
            a[1] += from_cents(r["revenue_cents"])
        return {k: (v[0], v[1]) for k, v in out.items()}

    res = revenue.attribution(agg(p0m), agg(p1m), len(p0m), len(p1m))
    by_vehicle = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
    a0, a1 = agg(p0m), agg(p1m)
    for pid in products:
        v = by_vehicle[products[pid]["vehicle"]]
        v[0] += a0.get(pid, (0, 0))[0]
        v[1] += a1.get(pid, (0, 0))[0]
        v[2] += a0.get(pid, (0, 0))[1]
        v[3] += a1.get(pid, (0, 0))[1]
    tot0 = sum(v[0] for v in by_vehicle.values())
    tot1 = sum(v[1] for v in by_vehicle.values())
    mix = [{"vehicle": k, "aum_share_0": _f(v[0] / tot0, 4), "aum_share_1": _f(v[1] / tot1, 4),
            "yield_bps_0": _f(v[2] * 12 / len(p0m) / v[0] * 10000) if v[0] else None,
            "yield_bps_1": _f(v[3] * 12 / len(p1m) / v[1] * 10000) if v[1] else None} for k, v in sorted(by_vehicle.items())]
    return {"data": {"period_0": [p0m[0].isoformat(), p0m[-1].isoformat()], "period_1": [p1m[0].isoformat(), p1m[-1].isoformat()],
                     **{k: (str(v) if isinstance(v, Decimal) else v) for k, v in res.items()}, "mix_by_vehicle": mix},
            "lineage": _lineage(adapters, ["revenue.management_fees", "revenue.yield_bps"], ["portfolio_accounting"],
                                "Exact additive decomposition: change = volume + rate; rate = mix + fee change (see docs/FINANCIAL_METHODOLOGY.md).")}


def risk_heatmap(adapters: Adapters) -> dict:
    risks = adapters.warehouse.table("risk_register")
    grid = [[0] * 5 for _ in range(5)]
    for r in risks:
        grid[r["impact"] - 1][r["likelihood"] - 1] += 1
    return {"data": {"grid": grid, "items": [{**r, "score": r["likelihood"] * r["impact"]} for r in sorted(risks, key=lambda r: -r["likelihood"] * r["impact"])]},
            "lineage": _lineage(adapters, ["risk.enterprise_score"], ["data_warehouse"], "Risk register likelihood (1-5) x impact (1-5).")}


def geographic_exposure(adapters: Adapters, scope: str = "enterprise", portfolio_id: str | None = None) -> dict:
    secs = {s["id"]: s for s in adapters.market.securities()}
    ms = adapters.market.months()
    exp: dict[str, Decimal] = defaultdict(Decimal)
    if scope in ("enterprise", "products"):
        last = {r["product_id"]: r for r in adapters.accounting.product_monthly() if r["month"] == ms[-1]}
        for p in adapters.accounting.products():
            aum = from_cents(last[p["id"]]["aum_close_cents"])
            for h in adapters.accounting.product_holdings(p["id"]):
                exp[secs[h["security_id"]]["country"]] += aum * Decimal(str(h["weight"]))
    if scope in ("enterprise", "portfolios", "portfolio"):
        ports = [adapters.portfolio.portfolio(portfolio_id)] if scope == "portfolio" else adapters.portfolio.portfolios()
        for p in ports:
            if p is None:
                continue
            mv = from_cents(adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"])
            for h in adapters.portfolio.holdings(p["id"]):
                exp[secs[h["security_id"]]["country"]] += mv * Decimal(str(h["current_weight"]))
    total = sum(exp.values()) or Decimal(1)
    from data.synthetic.generator import COUNTRIES
    rows = [{"country": c, "region": COUNTRIES[c][2], "lat": COUNTRIES[c][0], "lon": COUNTRIES[c][1], "value": _f(v),
             "weight": _f(v / total, 4)} for c, v in sorted(exp.items(), key=lambda kv: -kv[1])]
    return {"data": {"scope": scope, "countries": rows, "total": _f(total)},
            "lineage": _lineage(adapters, ["exposure.geographic"], ["portfolio_accounting", "portfolio_management", "market_data"],
                                "Look-through by issuer country of domicile at the latest month-end.")}


def actual_vs_budget(adapters: Adapters, months: int = 12) -> dict:
    ms = window_months(adapters, months)
    fin = _fin(adapters, ms)
    lines = sorted({k for m in ms for k in fin[m] if k != "aum_close"})
    out = []
    for ln in lines:
        a = from_cents(sum(fin[m][ln]["actual_cents"] for m in ms))
        b = from_cents(sum(fin[m][ln]["budget_cents"] for m in ms))
        fav = (a - b) >= 0 if ln.startswith("revenue") else (a - b) <= 0
        out.append({"line": ln, "actual": _f(a), "budget": _f(b), "variance": _f(a - b), "variance_pct": _f((a - b) / b, 4) if b else None,
                    "favourable": fav})
    aum = {"actual": _f(from_cents(fin[ms[-1]]["aum_close"]["actual_cents"])), "budget": _f(from_cents(fin[ms[-1]]["aum_close"]["budget_cents"]))}
    return {"data": {"period": [ms[0].isoformat(), ms[-1].isoformat()], "lines": out, "aum_close": aum},
            "lineage": _lineage(adapters, ["budget.variance"], ["erp"], "Sum of monthly actual vs budget per ledger line.")}


def initiative_scorecard(adapters: Adapters) -> dict:
    inits = adapters.warehouse.table("initiatives")
    rows = [{**{k: i[k] for k in ("id", "name", "owner", "domain", "progress_pct", "planned_progress_pct", "status", "target_kpi",
                                    "target_value", "observed_value")},
             "budget": _f(from_cents(i["budget_cents"])), "spent": _f(from_cents(i["spent_cents"])),
             "start_date": i["start_date"].isoformat(), "end_date": i["end_date"].isoformat(),
             "schedule_variance_pp": i["progress_pct"] - i["planned_progress_pct"]} for i in inits]
    return {"data": {"initiatives": rows}, "lineage": _lineage(adapters, ["strategy.initiative_progress"], ["data_warehouse"],
                                                                 "Self-reported progress vs time-elapsed plan (synthetic strategy office data).")}


def retention_trend(adapters: Adapters) -> dict:
    ms = adapters.market.months()
    clients = adapters.crm.clients()
    out = []
    for m in ms:
        active = sum(1 for c in clients if c["onboarding_date"] <= m and (c["closed_date"] is None or c["closed_date"] > m))
        closed = sum(1 for c in clients if c["closed_date"] == m)
        out.append({"month": m.isoformat(), "active_clients": active, "closures": closed})
    return {"data": {"series": out}, "lineage": _lineage(adapters, ["clients.retention"], ["crm"], "Active clients at month-end and closures in month.")}


# ---------------------------------------------------------------------------------------------- investment
def _port_returns(adapters: Adapters, pid: str) -> tuple[list[float], list[dict]]:
    vals = adapters.portfolio.valuations(pid)
    return [returns.sub_period_return(v["mv_open_cents"], v["net_external_flow_cents"], v["mv_close_cents"]) for v in vals], vals


def portfolio_metrics(adapters: Adapters, pid: str, rf: list[float] | None = None) -> dict:
    p = adapters.portfolio.portfolio(pid)
    if p is None:
        raise KeyError(pid)
    r, vals = _port_returns(adapters, pid)
    rf = rf or adapters.market.benchmark_returns("B-MM")
    b = adapters.market.benchmark_returns(p["benchmark_id"])
    w = [h["current_weight"] for h in adapters.portfolio.holdings(pid)]
    holds = adapters.portfolio.holdings(pid)
    drift = risk.allocation_drift({h["security_id"]: h["target_weight"] for h in holds}, {h["security_id"]: h["current_weight"] for h in holds})
    tw = returns.twr([(v["mv_open_cents"], v["net_external_flow_cents"], v["mv_close_cents"]) for v in vals])
    bt = returns.link(b)
    return {"id": pid, "name": p["name"], "client_id": p["client_id"], "mandate": p["mandate"], "risk_profile": p["model_risk_profile"],
            "benchmark_id": p["benchmark_id"], "market_value": _f(from_cents(vals[-1]["mv_close_cents"])),
            "twr_cumulative": round(tw, 6), "twr_annualized": round(returns.annualize(tw, len(r)), 6),
            "benchmark_cumulative": round(bt, 6), "excess_annualized": round(returns.annualize(tw, len(r)) - returns.annualize(bt, len(r)), 6),
            "volatility": round(risk.volatility(r), 6), "sharpe": round(risk.sharpe(r, rf) or 0, 4),
            "max_drawdown": round(risk.max_drawdown(r)["max_drawdown"], 6), "hhi": round(risk.hhi(w), 6),
            "effective_n": round(risk.effective_n(w), 2), "top_weight": round(max(w), 6),
            "concentration_breach": max(w) > CONC_LIMIT, "drift": round(drift["total_drift"], 6)}


def portfolio_list(adapters: Adapters, allowed_ids: set[str] | None = None, filters: dict | None = None) -> dict:
    rf = adapters.market.benchmark_returns("B-MM")
    f = {k: v for k, v in (filters or {}).items() if v}
    out = []
    for p in adapters.portfolio.portfolios():
        if allowed_ids is not None and p["id"] not in allowed_ids:
            continue
        if f.get("mandate") and p["mandate"] != f["mandate"]:
            continue
        if f.get("risk_profile") and p["model_risk_profile"] != f["risk_profile"]:
            continue
        out.append(portfolio_metrics(adapters, p["id"], rf))
    return {"data": {"portfolios": out, "count": len(out)},
            "lineage": _lineage(adapters, ["perf.twr", "risk.volatility", "risk.sharpe", "risk.max_drawdown", "risk.hhi", "risk.drift"],
                                ["portfolio_management", "market_data"], "24 monthly sub-period returns per portfolio; flows at month-end.")}


def portfolio_detail(adapters: Adapters, pid: str) -> dict:
    p = adapters.portfolio.portfolio(pid)
    if p is None:
        raise KeyError(pid)
    ms = adapters.market.months()
    r, vals = _port_returns(adapters, pid)
    b = adapters.market.benchmark_returns(p["benchmark_id"])
    secs = {s["id"]: s for s in adapters.market.securities()}
    sret = adapters.market.security_returns()
    holds = adapters.portfolio.holdings(pid)
    metrics = portfolio_metrics(adapters, pid)
    flows = [(v["month"], from_cents(v["net_external_flow_cents"])) for v in vals if v["net_external_flow_cents"]]
    try:
        mw = returns.mwr(ms[0].replace(day=1) - timedelta(days=1), float(from_cents(vals[0]["mv_open_cents"])),
                         [(d, float(a)) for d, a in flows], ms[-1], float(from_cents(vals[-1]["mv_close_cents"])))
    except ValueError:
        mw = None
    alloc: dict[str, dict[str, float]] = {"asset_class": defaultdict(float), "sector": defaultdict(float), "country": defaultdict(float)}
    for h in holds:
        s = secs[h["security_id"]]
        for k in alloc:
            alloc[k][s[k]] += h["current_weight"]
    # arithmetic contribution by sector over the last 12 months using start-of-month drifted weights
    w = {h["security_id"]: h["target_weight"] for h in holds}
    contrib: dict[str, float] = defaultdict(float)
    for t in range(len(ms)):
        R = sum(wt * sret[sid][t] for sid, wt in w.items())
        if t >= len(ms) - 12:
            for sid, wt in w.items():
                contrib[secs[sid]["sector"]] += wt * sret[sid][t]
        w = {sid: wt * (1 + sret[sid][t]) / (1 + R) for sid, wt in w.items()}
    bench12 = sum(b[-12:])
    holdings = sorted([{"security_id": h["security_id"], "name": secs[h["security_id"]]["name"], "ticker": secs[h["security_id"]]["ticker"],
                        "sector": secs[h["security_id"]]["sector"], "country": secs[h["security_id"]]["country"],
                        "asset_class": secs[h["security_id"]]["asset_class"], "target_weight": h["target_weight"],
                        "current_weight": h["current_weight"], "drift": round(h["current_weight"] - h["target_weight"], 6),
                        "market_value": _f(from_cents(vals[-1]["mv_close_cents"]) * Decimal(str(h["current_weight"])))} for h in holds],
                      key=lambda x: -x["current_weight"])
    return {"data": {
        "portfolio": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items()}, "metrics": metrics,
        "mwr_annualized": round(mw, 6) if mw is not None else None,
        "months": [m.isoformat() for m in ms], "returns": [round(x, 6) for x in r], "benchmark_returns": b,
        "cumulative": [round(x, 6) for x in returns.cumulative_series(r)], "benchmark_cumulative": [round(x, 6) for x in returns.cumulative_series(b)],
        "relative": [round(x, 6) for x in returns.relative_cumulative(r, b)], "drawdown": [round(x, 6) for x in risk.drawdown_series(r)],
        "market_values": [_f(from_cents(v["mv_close_cents"])) for v in vals], "flows": [_f(from_cents(v["net_external_flow_cents"])) for v in vals],
        "allocation": {k: dict(sorted(((kk, round(vv, 6)) for kk, vv in v.items()), key=lambda kv: -kv[1])) for k, v in alloc.items()},
        "holdings": holdings,
        "contribution_12m": {"by_sector": dict(sorted(((k, round(v, 6)) for k, v in contrib.items()), key=lambda kv: -kv[1])),
                             "portfolio_sum": round(sum(contrib.values()), 6), "benchmark_sum": round(bench12, 6),
                             "method": "Arithmetic sum of monthly weight x return by sector (contribution analysis, not Brinson attribution)."},
        "concentration": {"limit": CONC_LIMIT, "breaches": risk.limit_breaches({h["security_id"]: h["current_weight"] for h in holds}, CONC_LIMIT)},
    }, "lineage": _lineage(adapters, ["perf.twr", "perf.mwr", "risk.volatility", "risk.sharpe", "risk.max_drawdown", "risk.hhi", "risk.drift", "risk.single_issuer"],
                           ["portfolio_management", "market_data"], "Month-end valuations; external flows at month-end; MWR solves the IRR of opening value, flows and closing value.")}


def fund_list(adapters: Adapters, filters: dict | None = None) -> dict:
    products = _product_filter(adapters, filters)
    ms = adapters.market.months()
    rf = adapters.market.benchmark_returns("B-MM")
    by: dict[str, list[dict]] = defaultdict(list)
    for r in adapters.accounting.product_monthly():
        if r["product_id"] in products:
            by[r["product_id"]].append(r)
    out = []
    for pid, rows in by.items():
        rows.sort(key=lambda x: x["month"])
        rr = [x["ret"] for x in rows]
        b = adapters.market.benchmark_returns(products[pid]["benchmark_id"])
        p = products[pid]
        out.append({"id": pid, "name": p["name"], "asset_class": p["asset_class"], "vehicle": p["vehicle"], "strategy": p["strategy"],
                    "region": p["region"], "fee_bps": rows[-1]["fee_bps"], "risk_rating": p["risk_rating"],
                    "aum": _f(from_cents(rows[-1]["aum_close_cents"])), "return_12m": round(returns.link(rr[-12:]), 6),
                    "return_24m_ann": round(returns.annualize(returns.link(rr), len(rr)), 6),
                    "benchmark_12m": round(returns.link(b[-12:]), 6), "volatility": round(risk.volatility(rr), 6),
                    "sharpe": round(risk.sharpe(rr, rf) or 0, 4), "max_drawdown": round(risk.max_drawdown(rr)["max_drawdown"], 6),
                    "net_flows_12m": _f(from_cents(sum(x["subscriptions_cents"] - x["redemptions_cents"] for x in rows[-12:])))})
    out.sort(key=lambda x: -x["aum"])
    return {"data": {"funds": out, "as_of": ms[-1].isoformat()},
            "lineage": _lineage(adapters, ["aum.total", "perf.twr", "risk.volatility", "risk.sharpe"], ["portfolio_accounting", "market_data"],
                                "Gross-of-fee monthly fund returns from fund accounting (synthetic).")}


def fund_detail(adapters: Adapters, product_id: str) -> dict:
    products = _product_filter(adapters, None)
    if product_id not in products:
        raise KeyError(product_id)
    p = products[product_id]
    rows = sorted([r for r in adapters.accounting.product_monthly() if r["product_id"] == product_id], key=lambda x: x["month"])
    rr = [x["ret"] for x in rows]
    b = adapters.market.benchmark_returns(p["benchmark_id"])
    secs = {s["id"]: s for s in adapters.market.securities()}
    holds = sorted(adapters.accounting.product_holdings(product_id), key=lambda h: -h["weight"])
    sector: dict[str, float] = defaultdict(float)
    for h in holds:
        sector[secs[h["security_id"]]["sector"]] += h["weight"]
    return {"data": {"product": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items()},
                     "months": [r["month"].isoformat() for r in rows], "aum": [_f(from_cents(r["aum_close_cents"])) for r in rows],
                     "net_flows": [_f(from_cents(r["subscriptions_cents"] - r["redemptions_cents"])) for r in rows],
                     "returns": rr, "benchmark_returns": b, "cumulative": returns.cumulative_series(rr), "benchmark_cumulative": returns.cumulative_series(b),
                     "fee_bps": [r["fee_bps"] for r in rows], "drawdown": risk.drawdown_series(rr),
                     "top_holdings": [{"name": secs[h["security_id"]]["name"], "weight": h["weight"], "sector": secs[h["security_id"]]["sector"]} for h in holds[:10]],
                     "sector_weights": dict(sorted(sector.items(), key=lambda kv: -kv[1])),
                     "fee_impact_100k_10y": {k: str(v) for k, v in revenue.fee_impact(Decimal(100000), Decimal("0.06"), rows[-1]["fee_bps"], 10).items()}},
            "lineage": _lineage(adapters, ["aum.total", "perf.twr", "risk.max_drawdown"], ["portfolio_accounting", "market_data"],
                                "Fund accounting month-end NAV and flows; fee impact assumes 6% gross annual return (illustrative).")}


def enterprise_concentration(adapters: Adapters, top: int = 15) -> dict:
    secs = {s["id"]: s for s in adapters.market.securities()}
    exp: dict[str, Decimal] = defaultdict(Decimal)
    n_ports: dict[str, int] = defaultdict(int)
    breaches = 0
    for p in adapters.portfolio.portfolios():
        mv = from_cents(adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"])
        hs = adapters.portfolio.holdings(p["id"])
        if max(h["current_weight"] for h in hs) > CONC_LIMIT:
            breaches += 1
        for h in hs:
            exp[h["security_id"]] += mv * Decimal(str(h["current_weight"]))
            n_ports[h["security_id"]] += 1
    total = sum(exp.values())
    w = {k: float(v / total) for k, v in exp.items()}
    eq_total = sum(v for k, v in exp.items() if secs[k]["asset_class"] == "Equity")
    sector: dict[str, Decimal] = defaultdict(Decimal)
    for k, v in exp.items():
        sector[secs[k]["sector"]] += v
    top_rows = [{"security_id": k, "name": secs[k]["name"], "sector": secs[k]["sector"], "country": secs[k]["country"],
                 "exposure": _f(exp[k]), "weight": round(w[k], 6), "share_of_equity": _f(exp[k] / eq_total, 4) if secs[k]["asset_class"] == "Equity" else None,
                 "portfolios_holding": n_ports[k]} for k in sorted(w, key=lambda k: -w[k])[:top]]
    return {"data": {"total_portfolio_aum": _f(total), "hhi": round(risk.hhi(list(w.values())), 6), "effective_n": round(risk.effective_n(list(w.values())), 1),
                     "top_holdings": top_rows, "top10_weight": round(risk.top_n_weight(list(w.values()), 10), 6),
                     "portfolios_breaching_single_issuer_limit": breaches, "portfolio_count": len(adapters.portfolio.portfolios()),
                     "sector_exposure": [{"sector": k, "value": _f(v), "weight": _f(v / total, 4)} for k, v in sorted(sector.items(), key=lambda kv: -kv[1])],
                     "limit": CONC_LIMIT},
            "lineage": _lineage(adapters, ["risk.hhi", "risk.single_issuer"], ["portfolio_management", "market_data"],
                                "Aggregates current holdings across all managed portfolios in the tenant at the latest month-end.")}


def sector_correlation(adapters: Adapters) -> dict:
    secs = adapters.market.securities()
    sret = adapters.market.security_returns()
    n = len(adapters.market.months())
    by: dict[str, list[list[float]]] = defaultdict(list)
    for s in secs:
        if s["asset_class"] == "Equity":
            by[s["sector"]].append(sret[s["id"]])
    idx = {k: [sum(v[i] for v in vs) / len(vs) for i in range(n)] for k, vs in sorted(by.items())}
    idx["Canada Bonds (index)"] = adapters.market.benchmark_returns("B-CABD")
    return {"data": risk.correlation_matrix(idx), "lineage": _lineage(adapters, ["risk.volatility"], ["market_data"],
                                                                       "Pearson correlation of equal-weighted sector indices (24 monthly returns).")}


def risk_return_scatter(adapters: Adapters, universe: str = "funds") -> dict:
    if universe == "funds":
        pts = [{"id": f["id"], "name": f["name"], "group": f["asset_class"], "volatility": f["volatility"],
                "return": f["return_24m_ann"], "size": f["aum"]} for f in fund_list(adapters)["data"]["funds"]]
    else:
        pts = [{"id": p["id"], "name": p["name"], "group": p["mandate"], "volatility": p["volatility"], "return": p["twr_annualized"],
                "size": p["market_value"]} for p in portfolio_list(adapters)["data"]["portfolios"]]
    return {"data": {"universe": universe, "points": pts}, "lineage": _lineage(adapters, ["risk.volatility", "perf.twr"], ["portfolio_accounting", "market_data"],
                                                                                "Annualized 24-month return vs annualized volatility.")}


def market_intelligence(adapters: Adapters) -> dict:
    ms = adapters.market.months()
    bms = []
    for b in adapters.market.benchmarks():
        r = adapters.market.benchmark_returns(b["id"])
        bms.append({"id": b["id"], "name": b["name"], "asset_class": b["asset_class"], "last_month": round(r[-1], 6),
                    "three_month": round(returns.link(r[-3:]), 6), "twelve_month": round(returns.link(r[-12:]), 6),
                    "ytd": round(returns.link([x for x, m in zip(r, ms) if m.year == ms[-1].year]), 6), "volatility": round(risk.volatility(r), 6),
                    "series": returns.cumulative_series(r)})
    secs = adapters.market.securities()
    sret = adapters.market.security_returns()
    movers = sorted(({"name": s["name"], "sector": s["sector"], "country": s["country"], "last_month": round(sret[s["id"]][-1], 6)}
                     for s in secs if s["asset_class"] == "Equity"), key=lambda x: x["last_month"])
    sector_last: dict[str, list[float]] = defaultdict(list)
    for s in secs:
        if s["asset_class"] == "Equity":
            sector_last[s["sector"]].append(sret[s["id"]][-1])
    return {"data": {"months": [m.isoformat() for m in ms], "benchmarks": bms, "top_gainers": movers[-5:][::-1], "top_losers": movers[:5],
                     "sector_last_month": {k: round(sum(v) / len(v), 6) for k, v in sorted(sector_last.items())}},
            "lineage": _lineage(adapters, ["perf.twr"], ["market_data"], "Synthetic market data provider (mock adapter); month-end returns.")}
