"""Monetary conventions.

* Reporting currency: CAD. All stored amounts are integer cents.
* Monetary results are Decimal, quantized to the cent with ROUND_HALF_EVEN (banker's rounding), applied once at the
  end of a calculation, never on intermediate values.
* Rates (bps, %) are Decimal quantized to 2 dp for presentation only.
* Statistical measures (volatility, Sharpe, correlation) are float: they are estimates, not ledger amounts.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 34
CURRENCY = "CAD"
CENT = Decimal("0.01")
BP = Decimal("10000")


def from_cents(cents: int) -> Decimal:
    return Decimal(int(cents)) / 100


def money(x: Decimal | int | float | str) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def to_cents(x: Decimal) -> int:
    return int((Decimal(x) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def rate2(x: Decimal | float) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_EVEN)


def safe_div(a: Decimal, b: Decimal) -> Decimal:
    if b == 0:
        raise ZeroDivisionError("denominator is zero")
    return Decimal(a) / Decimal(b)
