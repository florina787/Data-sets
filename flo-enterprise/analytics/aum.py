"""AUM roll-forward, reconciliation and attribution.

Roll-forward identity (per product, per month):
    AUM_close = AUM_open + Subscriptions - Redemptions + MarketMovement
Net flows = Subscriptions - Redemptions.  Organic growth rate = Net flows / AUM_open.
A reconciliation break is any non-zero residual  close - (open + subs - reds + market)  beyond the tolerance (cents).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from analytics.money import from_cents, money


@dataclass(frozen=True)
class RollForward:
    open: Decimal
    subscriptions: Decimal
    redemptions: Decimal
    market: Decimal
    close: Decimal

    @property
    def net_flows(self) -> Decimal:
        return self.subscriptions - self.redemptions

    @property
    def residual(self) -> Decimal:
        return self.close - (self.open + self.subscriptions - self.redemptions + self.market)

    def as_dict(self) -> dict:
        return {k: str(money(getattr(self, k))) for k in ("open", "subscriptions", "redemptions", "market", "close")} | {
            "net_flows": str(money(self.net_flows)), "residual": str(money(self.residual))}


@dataclass(frozen=True)
class ReconciliationResult:
    key: str
    balanced: bool
    difference: Decimal


def reconcile(key: str, rf: RollForward, tolerance: Decimal = Decimal("0.00")) -> ReconciliationResult:
    diff = rf.residual
    return ReconciliationResult(key, abs(diff) <= tolerance, money(diff))


def roll_forward_from_rows(rows: Iterable[dict], first_month, last_month) -> RollForward:
    """Aggregate monthly product rows (cents) into a period roll-forward between two month-ends (inclusive)."""
    rows = [r for r in rows if first_month <= r["month"] <= last_month]
    if not rows:
        raise ValueError("no rows in period")
    opens = sum(r["aum_open_cents"] for r in rows if r["month"] == first_month)
    closes = sum(r["aum_close_cents"] for r in rows if r["month"] == last_month)
    return RollForward(
        open=from_cents(opens),
        subscriptions=from_cents(sum(r["subscriptions_cents"] for r in rows)),
        redemptions=from_cents(sum(r["redemptions_cents"] for r in rows)),
        market=from_cents(sum(r["market_cents"] for r in rows)),
        close=from_cents(closes),
    )


def waterfall(rf: RollForward) -> list[dict]:
    """Steps for an AUM attribution waterfall chart (values in CAD)."""
    return [
        {"step": "Opening AUM", "value": str(money(rf.open)), "kind": "total"},
        {"step": "Subscriptions", "value": str(money(rf.subscriptions)), "kind": "increase"},
        {"step": "Redemptions", "value": str(money(-rf.redemptions)), "kind": "decrease"},
        {"step": "Market movement", "value": str(money(rf.market)), "kind": "increase" if rf.market >= 0 else "decrease"},
        {"step": "Closing AUM", "value": str(money(rf.close)), "kind": "total"},
    ]


def organic_growth_rate(rf: RollForward, months: int) -> Decimal:
    """Annualized organic growth = (net flows / opening AUM) * 12 / months."""
    return rf.net_flows / rf.open * Decimal(12) / Decimal(months)
