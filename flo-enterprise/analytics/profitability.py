"""Profitability.

* Operating income = Revenue - Operating expenses;  Operating margin = Operating income / Revenue.
* Product profitability (illustrative allocation, documented, not a statutory measure):
    product contribution = product revenue - direct distribution cost - allocated shared cost
    direct distribution cost: trailing commission of 40 bps p.a. on average AUM for Mutual Fund vehicles only
    allocated shared cost: (total expenses - total distribution expense) * product revenue share
"""
from __future__ import annotations

from decimal import Decimal

from analytics.money import money

TRAILER_BPS = Decimal(40)


def operating_margin(revenue: Decimal, expenses: Decimal) -> Decimal:
    if revenue == 0:
        raise ZeroDivisionError("revenue is zero")
    return (Decimal(revenue) - Decimal(expenses)) / Decimal(revenue)


def product_contribution(products: list[dict], total_expenses: Decimal, distribution_expense: Decimal,
                         months: int) -> list[dict]:
    """products: dicts with id, name, vehicle, asset_class, revenue (Decimal), avg_aum (Decimal)."""
    total_rev = sum((p["revenue"] for p in products), Decimal(0))
    shared = Decimal(total_expenses) - Decimal(distribution_expense)
    out = []
    for p in products:
        direct = p["avg_aum"] * TRAILER_BPS / Decimal(10000) * months / 12 if p["vehicle"] == "Mutual Fund" else Decimal(0)
        alloc = shared * (p["revenue"] / total_rev) if total_rev else Decimal(0)
        contrib = p["revenue"] - direct - alloc
        out.append({**{k: p[k] for k in ("id", "name", "vehicle", "asset_class")}, "revenue": money(p["revenue"]),
                    "direct_cost": money(direct), "allocated_cost": money(alloc), "contribution": money(contrib),
                    "margin": (contrib / p["revenue"]).quantize(Decimal("0.0001")) if p["revenue"] else None})
    return out
