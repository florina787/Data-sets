"""Wealth advisor analytics: retirement projection, goal progress, cash-flow forecast and rule-based suitability.

Retirement projection (deterministic, nominal and real):
  accumulation:  B_{y+1} = B_y * (1 + r) + 12 * c * (1 + g)^y      (contributions at year end, growing at g = inflation)
  decumulation:  level real withdrawal W that exhausts the balance over the retirement period:
                 W_nominal_first_year = B_R * (r - i) / (1 - ((1 + i) / (1 + r))^N)   (growing annuity; r != i)
                 where r = expected return, i = inflation, N = retirement years.
Planning assumptions come from policies/suitability.yaml (illustrative; not advice). Suitability checks apply only the
approved rules in that file; any recommendation derived from them requires human review (approval workflow).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal


from analytics.money import from_cents, money


def retirement_projection(current_savings: Decimal, monthly_contribution: Decimal, years_to_retirement: int, expected_return: float,
                          inflation: float, retirement_years: int = 25) -> dict:
    if years_to_retirement < 0 or retirement_years <= 0:
        raise ValueError("invalid horizon")
    r, i = Decimal(str(expected_return)), Decimal(str(inflation))
    bal = Decimal(current_savings)
    path = [{"year": 0, "balance": money(bal), "real_balance": money(bal), "phase": "accumulation"}]
    for y in range(years_to_retirement):
        bal = bal * (1 + r) + 12 * Decimal(monthly_contribution) * (1 + i) ** y
        path.append({"year": y + 1, "balance": money(bal), "real_balance": money(bal / (1 + i) ** (y + 1)), "phase": "accumulation"})
    at_ret = bal
    n = retirement_years
    if r == i:
        w = at_ret / n
    else:
        w = at_ret * (r - i) / (1 - ((1 + i) / (1 + r)) ** n)
    for y in range(n):
        wy = w * (1 + i) ** y
        bal = bal * (1 + r) - wy
        yr = years_to_retirement + y + 1
        path.append({"year": yr, "balance": money(max(bal, Decimal(0))), "real_balance": money(max(bal, Decimal(0)) / (1 + i) ** yr),
                     "withdrawal": money(wy), "phase": "decumulation"})
    return {"balance_at_retirement": money(at_ret), "real_balance_at_retirement": money(at_ret / (1 + i) ** years_to_retirement),
            "sustainable_first_year_withdrawal": money(w), "sustainable_real_annual_income": money(w / (1 + i) ** years_to_retirement),
            "path": path, "assumptions": {"expected_return": expected_return, "inflation": inflation, "retirement_years": retirement_years,
                                          "contribution_growth": "inflation", "timing": "annual, end of year"}}


def goal_progress(goal: dict, expected_return: float, as_of: date) -> dict:
    years = max(0.0, (goal["target_date"] - as_of).days / 365.25)
    cur, target = from_cents(goal["current_amount_cents"]), from_cents(goal["target_amount_cents"])
    c = from_cents(goal["monthly_contribution_cents"])
    r = Decimal(str(expected_return))
    yrs = int(years)
    proj = cur * (1 + r) ** yrs + (sum((12 * c * (1 + r) ** k for k in range(yrs)), Decimal(0)))
    return {"goal_id": goal["id"], "goal_type": goal["goal_type"], "target_amount": money(target), "current_amount": money(cur),
            "funded_pct": round(float(cur / target), 4) if target else None, "projected_at_target": money(proj),
            "projected_funded_pct": round(float(proj / target), 4) if target else None, "years_remaining": round(years, 1),
            "target_date": goal["target_date"].isoformat(), "on_track": bool(target and proj >= target)}


def suitability_check(client: dict, portfolio_metrics: list[dict], rules: dict, as_of: date) -> dict:
    band = rules["volatility_bands"][client["risk_profile"]]
    findings = []
    for pm in portfolio_metrics:
        if pm["volatility"] > band:
            findings.append({"rule": "SUIT-VOL-BAND", "severity": "high", "portfolio_id": pm["id"],
                             "detail": {"volatility": pm["volatility"], "max_for_profile": band, "risk_profile": client["risk_profile"]}})
        if pm["top_weight"] > rules["single_issuer_limit"]:
            findings.append({"rule": "SUIT-SINGLE-ISSUER", "severity": "medium", "portfolio_id": pm["id"],
                             "detail": {"top_weight": pm["top_weight"], "limit": rules["single_issuer_limit"]}})
    age = (as_of - client["kyc_last_review"]).days
    if age > rules["kyc_max_age_days"]:
        findings.append({"rule": "SUIT-KYC-STALE", "severity": "high", "detail": {"kyc_age_days": age, "max_days": rules["kyc_max_age_days"]}})
    return {"rules_version": rules["version"], "risk_profile": client["risk_profile"], "volatility_band": band,
            "status": "exceptions_found" if findings else "no_exceptions", "findings": findings,
            "disclaimer": "Rule-based screen using approved synthetic rules; not a suitability determination. Requires advisor and compliance review."}


def cash_flow_forecast(goals: list[dict], transactions: list[dict], months: int = 12) -> dict:
    contrib = sum((from_cents(g["monthly_contribution_cents"]) for g in goals), Decimal(0))
    ext = [t for t in transactions if t["tx_type"] in ("CONTRIBUTION", "WITHDRAWAL")]
    hist_months = max(1, len({(t["tx_date"].year, t["tx_date"].month) for t in transactions}) if transactions else 1)
    wd = sum((from_cents(t["amount_cents"]) for t in ext if t["tx_type"] == "WITHDRAWAL"), Decimal(0))  # negative
    dep = sum((from_cents(t["amount_cents"]) for t in ext if t["tx_type"] == "CONTRIBUTION"), Decimal(0))
    avg_w = wd / 24 if ext else Decimal(0)
    avg_d = dep / 24 if ext else Decimal(0)
    rows = [{"month": k + 1, "planned_goal_contributions": money(contrib), "expected_portfolio_contributions": money(avg_d),
             "expected_withdrawals": money(avg_w), "net": money(contrib + avg_d + avg_w)} for k in range(months)]
    return {"months": rows, "basis": "goal contribution plans + 24-month average of historical external portfolio flows",
            "history_months_observed": hist_months}


def risk_return_for_client(portfolio_metrics: list[dict]) -> list[dict]:
    return [{"id": p["id"], "volatility": p["volatility"], "return": p["twr_annualized"], "mandate": p["mandate"]} for p in portfolio_metrics]



