"""Enterprise portfolio performance, sector return contribution and single-sector shocks.

All figures are computed from managed-portfolio valuations, holdings and security returns (synthetic adapters):
* Aggregate monthly return = sum(MV_close - external flow) / sum(MV_open) - 1 (flows at month end, the TWR convention).
* Period returns geometrically link monthly returns; the comparison period is the preceding window of equal length.
* Sector contribution is a holdings-based attribution: sector weight (latest holdings x latest MV) x linked sector return
  over the window. It approximates the actual contribution because holdings weights drift within the window.
* A sector shock applies an instantaneous move to every holding in the sector: impact = MV x sector weight x shock.
"""
from __future__ import annotations

from collections import defaultdict

from analytics.money import from_cents
from analytics.service import _lineage


def _link(rs: list[float]) -> float:
    out = 1.0
    for r in rs:
        out *= 1 + r
    return out - 1


def portfolio_performance(adapters, months: int = 12) -> dict:
    ms = adapters.market.months()
    months = max(1, min(months, len(ms) // 2))
    ports = adapters.portfolio.portfolios()
    opens, nets = [0] * len(ms), [0] * len(ms)
    exposure: dict[str, float] = defaultdict(float)
    secs = {s["id"]: s for s in adapters.market.securities()}
    total_mv = 0.0
    for p in ports:
        vals = adapters.portfolio.valuations(p["id"])
        for i, v in enumerate(vals[-len(ms):]):
            opens[i] += v["mv_open_cents"]
            nets[i] += v["mv_close_cents"] - v["net_external_flow_cents"]
        mv = float(from_cents(vals[-1]["mv_close_cents"]))
        total_mv += mv
        for h in adapters.portfolio.holdings(p["id"]):
            exposure[secs[h["security_id"]]["sector"]] += mv * h["current_weight"]
    monthly = [round(n / o - 1, 6) if o else 0.0 for n, o in zip(nets, opens)]
    cur, prior = monthly[-months:], monthly[-2 * months:-months]
    rets = adapters.market.security_returns()
    by_sector: dict[str, list[str]] = defaultdict(list)
    for s in secs.values():
        by_sector[s["sector"]].append(s["id"])
    contrib = []
    for sector, sids in by_sector.items():
        if exposure.get(sector, 0) <= 0:
            continue
        sr = [_link(rets[sid][-months:]) for sid in sids if sid in rets]
        r = sum(sr) / len(sr) if sr else 0.0
        w = exposure[sector] / total_mv
        contrib.append({"sector": sector, "weight": round(w, 6), "return": round(r, 6), "contribution": round(w * r, 6)})
    contrib.sort(key=lambda x: -x["contribution"])
    cum, run = [], 1.0
    for r in monthly:
        run *= 1 + r
        cum.append(round(run - 1, 6))
    data = {"months": [m.isoformat() for m in ms], "monthly_returns": monthly, "cumulative": cum, "window_months": months,
            "period": {"start": ms[-months].isoformat(), "end": ms[-1].isoformat(), "return": round(_link(cur), 6)},
            "prior_period": {"start": ms[-2 * months].isoformat(), "end": ms[-months - 1].isoformat(), "return": round(_link(prior), 6)},
            "portfolios": len(ports), "market_value": round(total_mv, 2), "sector_contribution": contrib,
            "top_sector": contrib[0]["sector"] if contrib else None, "bottom_sector": contrib[-1]["sector"] if contrib else None}
    return {"data": data, "lineage": _lineage(adapters, ["perf.twr", "exposure.geographic"], ["portfolio_management", "market_data"],
                                              "Aggregate monthly return = sum(MV_close - flows) / sum(MV_open) - 1, linked over the window. "
                                              "Sector contribution = latest sector weight x average linked security return in the sector (holdings-based "
                                              "approximation).")}


def sector_shock(adapters, sector: str, shock: float) -> dict:
    secs = {s["id"]: s for s in adapters.market.securities()}
    if sector not in {s["sector"] for s in secs.values()}:
        raise ValueError(f"unknown sector {sector!r}")
    rows, by_mandate = [], defaultdict(list)
    total_mv = total_imp = 0.0
    for p in adapters.portfolio.portfolios():
        mv = float(from_cents(adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"]))
        w = sum(h["current_weight"] for h in adapters.portfolio.holdings(p["id"]) if secs[h["security_id"]]["sector"] == sector)
        imp = mv * w * shock
        total_mv += mv
        total_imp += imp
        by_mandate[p["mandate"]].append(w * shock)
        rows.append({"portfolio_id": p["id"], "mandate": p["mandate"], "market_value": round(mv, 2), "sector_weight": round(w, 6),
                     "impact_pct": round(w * shock, 6), "impact_value": round(imp, 2)})
    rows.sort(key=lambda r: r["impact_pct"])
    ms = adapters.market.months()
    last = {r["product_id"]: r for r in adapters.accounting.product_monthly() if r["month"] == ms[-1]}
    aum_imp = rev_imp = aum = 0.0
    for prod in adapters.accounting.products():
        a = float(from_cents(last[prod["id"]]["aum_close_cents"]))
        w = sum(h["weight"] for h in adapters.accounting.product_holdings(prod["id"]) if secs[h["security_id"]]["sector"] == sector)
        aum += a
        aum_imp += a * w * shock
        rev_imp += a * w * shock * last[prod["id"]]["fee_bps"] / 10000
    data = {"sector": sector, "shock": shock, "portfolios": len(rows), "portfolio_market_value": round(total_mv, 2),
            "portfolio_impact": round(total_imp, 2), "portfolio_impact_pct": round(total_imp / total_mv, 6) if total_mv else 0.0,
            "product_aum": round(aum, 2), "product_aum_impact": round(aum_imp, 2), "annual_fee_revenue_impact": round(rev_imp, 2),
            "by_mandate": {k: round(sum(v) / len(v), 6) for k, v in sorted(by_mandate.items())}, "most_impacted": rows[:8],
            "method": "Instantaneous shock to every holding in the sector; other holdings unchanged; no second-order effects. "
                      "Revenue impact = AUM impact x product fee rate (annualized). Conditional on the stated shock, not a forecast."}
    return {"data": data, "lineage": _lineage(adapters, ["exposure.geographic"], ["portfolio_management", "portfolio_accounting", "market_data"],
                                              data["method"])}


def sectors(adapters) -> list[str]:
    return sorted({s["sector"] for s in adapters.market.securities()})
