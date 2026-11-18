"""Revenue analytics.

* Monthly management-fee revenue (per product):  avg(AUM_open, AUM_close) * fee_bps / 10,000 / 12
  (quantized to the cent, ROUND_HALF_EVEN).  This is the FLO semantic-layer definition `revenue.management_fees`.
* Revenue yield (bps, annualized):  sum(revenue over n months) * 12 / n / average AUM * 10,000, where average
  AUM is the mean of monthly average AUM over the period.
* Revenue change attribution between periods 0 and 1 (exact, additive):
      dRev = Volume effect + Rate effect
      Volume = (AvgAUM_1 - AvgAUM_0) * y_0
      Rate   = (y_1 - y_0) * AvgAUM_1
  and the rate effect splits exactly into product MIX and FEE-CHANGE effects using AUM shares s_i and fee rates f_i:
      y_1 - y_0 = sum_i (s1_i - s0_i) * f0_i  +  sum_i s1_i * (f1_i - f0_i)
  (fee rates measured as each product's realized yield over the period).
* Fee impact: value of an investment compounding at gross return r with annual fee f vs without fee.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from analytics.money import BP, money


def monthly_fee_revenue(aum_open: Decimal, aum_close: Decimal, fee_bps: int) -> Decimal:
    return money((Decimal(aum_open) + Decimal(aum_close)) / 2 * Decimal(fee_bps) / BP / 12)


def revenue_yield_bps(revenue: Decimal, avg_aum: Decimal, months: int) -> Decimal:
    if avg_aum == 0:
        raise ZeroDivisionError("average AUM is zero")
    return Decimal(revenue) * 12 / Decimal(months) / Decimal(avg_aum) * BP


def attribution(p0: Mapping[str, tuple[Decimal, Decimal]], p1: Mapping[str, tuple[Decimal, Decimal]], months0: int,
                months1: int) -> dict:
    """p0/p1: product_id -> (average AUM over period, revenue over period). Returns annualized-revenue attribution."""
    def agg(p, months):
        aum = sum((v[0] for v in p.values()), Decimal(0))
        rev = sum((v[1] for v in p.values()), Decimal(0)) * 12 / months  # annualized
        return aum, rev

    a0, r0 = agg(p0, months0)
    a1, r1 = agg(p1, months1)
    y0, y1 = r0 / a0, r1 / a1
    volume = (a1 - a0) * y0
    rate = (y1 - y0) * a1
    keys = set(p0) | set(p1)

    def fee(p, k, months):
        aum, rev = p.get(k, (Decimal(0), Decimal(0)))
        return (rev * 12 / months / aum) if aum else Decimal(0)

    s0 = {k: (p0[k][0] / a0 if k in p0 else Decimal(0)) for k in keys}
    s1 = {k: (p1[k][0] / a1 if k in p1 else Decimal(0)) for k in keys}
    f0 = {k: fee(p0, k, months0) for k in keys}
    f1 = {k: fee(p1, k, months1) for k in keys}
    # products that did not exist in a period take the other period's rate (no fee-change effect)
    for k in keys:
        if k not in p0:
            f0[k] = f1[k]
        if k not in p1:
            f1[k] = f0[k]
    mix_y = sum(((s1[k] - s0[k]) * f0[k] for k in keys), Decimal(0))
    fee_y = sum((s1[k] * (f1[k] - f0[k]) for k in keys), Decimal(0))
    return {
        "annualized_revenue_0": money(r0), "annualized_revenue_1": money(r1), "change": money(r1 - r0),
        "volume_effect": money(volume), "rate_effect": money(rate),
        "mix_effect": money(mix_y * a1), "fee_change_effect": money(fee_y * a1),
        "yield_bps_0": (y0 * BP).quantize(Decimal("0.01")), "yield_bps_1": (y1 * BP).quantize(Decimal("0.01")),
        "avg_aum_0": money(a0), "avg_aum_1": money(a1),
        "check_residual": money((r1 - r0) - volume - rate),
    }


def fee_impact(amount: Decimal, gross_return: Decimal, fee_bps: int, years: int) -> dict:
    amount, g = Decimal(amount), Decimal(gross_return)
    f = Decimal(fee_bps) / BP
    no_fee = amount * (1 + g) ** years
    with_fee = amount * (1 + g - f) ** years
    return {"ending_no_fee": money(no_fee), "ending_with_fee": money(with_fee), "fee_drag": money(no_fee - with_fee),
            "fee_drag_pct_of_no_fee": ((no_fee - with_fee) / no_fee * 100).quantize(Decimal("0.01"))}
