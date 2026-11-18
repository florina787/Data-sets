"""Strategy twin: deterministic scenario engine for AUM, revenue, profitability and portfolio impacts.

Model (documented assumptions, no probabilistic claims, no confidence intervals):
1. Starting point: latest month-end AUM per product (fund accounting) and trailing-12-month expenses (ERP).
2. Instantaneous market shock at t0 by asset class:
     Equity: equity_shock x beta (EM beta 1.2, Global/US/Canada 1.0)
     Fixed Income: bond_shock - duration x rate_shock (duration 6.5 years, rate shock in decimal)
     Balanced: 0.6 x equity + 0.4 x fixed income ; Alternatives: 0.35 x equity ; Cash: 0.
3. Stress redemptions (% of AUM) at t0, then net flows at a constant annual rate (% of opening AUM) spread monthly.
4. After t0, AUM drifts at the scenario's expected annual return per asset class (monthly compounding).
5. Revenue = sum over months of average product AUM x (fee_bps - fee_compression_bps) / 10,000 / 12.
6. Expenses = trailing-12m non-distribution expenses x (1 + opex_growth + inflation) x horizon/12 + technology investment
   + distribution cost (40 bps on mutual fund AUM).
7. Portfolio impacts: each managed portfolio's holdings shocked by asset class (equities x region beta).
All monetary outputs are Decimal-quantized CAD.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from analytics.money import from_cents, money
from integrations.mock.adapters import Adapters

DURATION = 6.5
EXPECTED = {"bull": 0.09, "base": 0.06, "bear": 0.02, "severe_stress": 0.0}


@dataclass
class ScenarioInput:
    name: str = "custom"
    equity_shock: float = 0.0
    bond_shock: float = 0.0
    rate_shock_bps: float = 0.0
    inflation: float = 0.021
    net_flows_pct: float = 0.02
    stress_redemptions_pct: float = 0.0
    fee_compression_bps: float = 0.0
    opex_growth: float = 0.04
    tech_investment: float = 0.0
    expected_equity_return: float = 0.06
    expected_bond_return: float = 0.035
    horizon_months: int = 12
    overrides: list[str] = field(default_factory=list)

    def validate(self) -> None:
        bounds = {"equity_shock": (-0.8, 0.8), "bond_shock": (-0.5, 0.5), "rate_shock_bps": (-500, 500), "inflation": (-0.05, 0.25),
                  "net_flows_pct": (-0.5, 0.5), "stress_redemptions_pct": (0, 0.6), "fee_compression_bps": (0, 100),
                  "opex_growth": (-0.3, 0.5), "tech_investment": (0, 5e8), "horizon_months": (1, 60),
                  "expected_equity_return": (-0.3, 0.3), "expected_bond_return": (-0.2, 0.2)}
        for k, (lo, hi) in bounds.items():
            v = getattr(self, k)
            if not lo <= v <= hi:
                raise ValueError(f"{k}={v} outside allowed range [{lo}, {hi}]")


PRESETS: dict[str, dict] = {
    "base": dict(equity_shock=0.0, bond_shock=0.0, rate_shock_bps=0, inflation=0.021, net_flows_pct=0.02, stress_redemptions_pct=0.0,
                 fee_compression_bps=2, opex_growth=0.04, expected_equity_return=0.06, expected_bond_return=0.035),
    "bull": dict(equity_shock=0.10, bond_shock=0.01, rate_shock_bps=-25, inflation=0.02, net_flows_pct=0.05, stress_redemptions_pct=0.0,
                 fee_compression_bps=1, opex_growth=0.05, expected_equity_return=0.09, expected_bond_return=0.04),
    "bear": dict(equity_shock=-0.15, bond_shock=0.0, rate_shock_bps=50, inflation=0.03, net_flows_pct=-0.03, stress_redemptions_pct=0.02,
                 fee_compression_bps=4, opex_growth=0.04, expected_equity_return=0.02, expected_bond_return=0.03),
    "severe_stress": dict(equity_shock=-0.35, bond_shock=-0.03, rate_shock_bps=150, inflation=0.05, net_flows_pct=-0.08,
                          stress_redemptions_pct=0.06, fee_compression_bps=8, opex_growth=0.03, expected_equity_return=0.0,
                          expected_bond_return=0.02),
}


def preset(name: str, **overrides) -> ScenarioInput:
    if name not in PRESETS:
        raise KeyError(name)
    s = ScenarioInput(name=name, **PRESETS[name])
    for k, v in overrides.items():
        if v is not None and hasattr(s, k) and k not in ("name", "overrides"):
            setattr(s, k, type(getattr(s, k))(v))
            s.overrides.append(k)
    return s


def _shock(asset_class: str, region: str, s: ScenarioInput) -> float:
    fi = s.bond_shock - DURATION * s.rate_shock_bps / 10000
    eq = s.equity_shock * (1.2 if region == "Emerging Markets" else 1.0)
    return {"Equity": eq, "Fixed Income": fi, "Balanced": 0.6 * s.equity_shock + 0.4 * fi, "Alternatives": 0.35 * s.equity_shock,
            "Cash": 0.0}.get(asset_class, 0.0)


def _drift(asset_class: str, s: ScenarioInput) -> float:
    return {"Equity": s.expected_equity_return, "Fixed Income": s.expected_bond_return,
            "Balanced": 0.6 * s.expected_equity_return + 0.4 * s.expected_bond_return, "Alternatives": 0.5 * s.expected_equity_return + 0.02,
            "Cash": max(0.0, 0.03 + s.rate_shock_bps / 10000)}.get(asset_class, 0.0)


def run(adapters: Adapters, s: ScenarioInput, include_portfolios: bool = True) -> dict:
    s.validate()
    ms = adapters.market.months()
    last = {r["product_id"]: r for r in adapters.accounting.product_monthly() if r["month"] == ms[-1]}
    products = adapters.accounting.products()
    fin12 = [r for r in adapters.erp.finance_monthly() if r["month"] in set(ms[-12:])]
    base_exp = from_cents(sum(r["actual_cents"] for r in fin12 if r["line"].startswith("expense_") and r["line"] != "expense_distribution"))
    hz = s.horizon_months
    aum0 = Decimal(0)
    aum_end = Decimal(0)
    revenue = Decimal(0)
    mf_avg = Decimal(0)
    by_class: dict[str, list[Decimal]] = {}
    path = [Decimal(0)] * (hz + 1)
    for p in products:
        a = from_cents(last[p["id"]]["aum_close_cents"])
        fee = max(Decimal(0), Decimal(last[p["id"]]["fee_bps"]) - Decimal(str(s.fee_compression_bps))) if last[p["id"]]["fee_bps"] > 0 else Decimal(0)
        aum0 += a
        path[0] += a
        cur = a * Decimal(str(1 + _shock(p["asset_class"], p["region"], s))) * Decimal(str(1 - s.stress_redemptions_pct))
        monthly_ret = Decimal(str((1 + _drift(p["asset_class"], s)) ** (1 / 12) - 1))
        monthly_flow = a * Decimal(str(s.net_flows_pct)) / 12
        for t in range(1, hz + 1):
            nxt = cur * (1 + monthly_ret) + monthly_flow
            nxt = max(nxt, Decimal(0))
            avg = (cur + nxt) / 2
            revenue += avg * fee / Decimal(10000) / 12
            if p["vehicle"] == "Mutual Fund":
                mf_avg += avg / hz
            cur = nxt
            path[t] += cur
        aum_end += cur
        bc = by_class.setdefault(p["asset_class"], [Decimal(0), Decimal(0)])
        bc[0] += a
        bc[1] += cur
    dist = mf_avg * Decimal(40) / Decimal(10000) * hz / 12
    expenses = base_exp * Decimal(str(1 + s.opex_growth + s.inflation)) * hz / 12 + Decimal(str(s.tech_investment)) + dist
    profit = revenue - expenses
    out = {
        "scenario": s.name, "horizon_months": hz, "currency": "CAD",
        "assumptions": [{"name": k, "value": v, "source": "user override" if k in s.overrides else (f"preset:{s.name}" if s.name in PRESETS else "user input")}
                        for k, v in asdict(s).items() if k not in ("name", "overrides")],
        "fixed_assumptions": {"bond_duration_years": DURATION, "em_equity_beta": 1.2, "balanced_mix": "60/40",
                              "alternatives_equity_beta": 0.35, "distribution_cost_bps_on_mutual_funds": 40,
                              "shock_timing": "instantaneous at t0", "flows_timing": "evenly monthly"},
        "results": {"aum_start": money(aum0), "aum_end": money(aum_end), "aum_change_pct": round(float(aum_end / aum0 - 1), 6),
                    "revenue": money(revenue), "expenses": money(expenses), "operating_income": money(profit),
                    "operating_margin": round(float(profit / revenue), 6) if revenue else None,
                    "revenue_yield_bps": round(float(revenue * 12 / hz / ((aum0 + aum_end) / 2) * 10000), 2)},
        "aum_path": [money(x) for x in path],
        "by_asset_class": [{"asset_class": k, "aum_start": money(v[0]), "aum_end": money(v[1]), "change_pct": round(float(v[1] / v[0] - 1), 6)}
                           for k, v in sorted(by_class.items())],
        "method": "Deterministic scenario arithmetic. Outputs are conditional on the stated assumptions; they are not forecasts and carry no probability.",
    }
    if include_portfolios:
        out["portfolio_impacts"] = portfolio_impacts(adapters, s)
    return out


def portfolio_impacts(adapters: Adapters, s: ScenarioInput, portfolio_ids: list[str] | None = None, top: int = 10) -> dict:
    secs = {x["id"]: x for x in adapters.market.securities()}
    rows = []
    for p in adapters.portfolio.portfolios():
        if portfolio_ids and p["id"] not in portfolio_ids:
            continue
        mv = from_cents(adapters.portfolio.valuations(p["id"])[-1]["mv_close_cents"])
        impact = sum(h["current_weight"] * _shock(secs[h["security_id"]]["asset_class"], secs[h["security_id"]]["region"], s)
                     for h in adapters.portfolio.holdings(p["id"]))
        rows.append({"portfolio_id": p["id"], "mandate": p["mandate"], "market_value": money(mv), "impact_pct": round(impact, 6),
                     "impact_value": money(mv * Decimal(str(impact)))})
    rows.sort(key=lambda r: r["impact_pct"])
    total_mv = sum((r["market_value"] for r in rows), Decimal(0))
    total_imp = sum((r["impact_value"] for r in rows), Decimal(0))
    by_mandate: dict[str, list[float]] = {}
    for r in rows:
        by_mandate.setdefault(r["mandate"], []).append(r["impact_pct"])
    return {"count": len(rows), "total_market_value": money(total_mv), "total_impact": money(total_imp),
            "most_impacted": rows[:top], "by_mandate": {k: round(sum(v) / len(v), 6) for k, v in sorted(by_mandate.items())}}


def compare(adapters: Adapters, names: list[str] | None = None) -> dict:
    names = names or list(PRESETS)
    res = {n: run(adapters, preset(n), include_portfolios=False) for n in names}
    return {"scenarios": [{"scenario": n, **{k: res[n]["results"][k] for k in ("aum_end", "aum_change_pct", "revenue", "expenses", "operating_income", "operating_margin")}}
                          for n in names], "assumptions": {n: res[n]["assumptions"] for n in names}}


def sensitivity(adapters: Adapters, base: ScenarioInput | None = None) -> dict:
    base = base or preset("base")
    b = run(adapters, base, include_portfolios=False)["results"]
    steps = {"equity_shock": 0.10, "rate_shock_bps": 100, "net_flows_pct": 0.02, "fee_compression_bps": 5, "opex_growth": 0.02,
             "tech_investment": 10_000_000}
    rows = []
    for k, d in steps.items():
        lo, hi = ScenarioInput(**{**asdict(base), "overrides": []}), ScenarioInput(**{**asdict(base), "overrides": []})
        setattr(lo, k, getattr(base, k) - d)
        setattr(hi, k, getattr(base, k) + d)
        if k in ("fee_compression_bps", "tech_investment"):
            lo_v = max(0, getattr(base, k) - d)
            setattr(lo, k, type(getattr(base, k))(lo_v))
        rl, rh = run(adapters, lo, False)["results"], run(adapters, hi, False)["results"]
        rows.append({"driver": k, "step": d, "operating_income_low": money(rl["operating_income"] - b["operating_income"]),
                     "operating_income_high": money(rh["operating_income"] - b["operating_income"]),
                     "revenue_low": money(rl["revenue"] - b["revenue"]), "revenue_high": money(rh["revenue"] - b["revenue"])})
    rows.sort(key=lambda r: -abs(r["operating_income_high"] - r["operating_income_low"]))
    return {"base": b, "tornado": rows, "method": "One-at-a-time sensitivity: each driver moved by +/- step holding others at base."}
