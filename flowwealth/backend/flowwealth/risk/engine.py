"""Independent pre-trade risk engine.

It takes an order intent, the portfolio and the profile, and returns
APPROVE / REDUCE / REJECT with reasons. It has no input for agent opinions or
judge decisions: the AI layer cannot override it. Limits come from
``TraderProfile.effective_limits()``, which is clamped by HARD_LIMITS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from flowwealth.contracts import DataStatus, Horizon, utcnow
from flowwealth.profiles.profile import HORIZON_DATA_REQUIREMENTS, TraderProfile


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    REDUCE = "REDUCE"
    REJECT = "REJECT"


@dataclass
class Position:
    ticker: str
    qty: float
    price: float
    sector: str

    @property
    def notional(self) -> float:
        return self.qty * self.price


@dataclass
class PortfolioState:
    equity: float
    peak_equity: float
    day_start_equity: float
    positions: list[Position] = field(default_factory=list)


@dataclass
class OrderIntent:
    ticker: str
    side: str            # "buy" | "sell_short"
    qty: float
    price: float
    stop_price: float
    sector: str
    adv_shares: float    # average daily volume
    daily_vol: float     # daily return volatility (e.g. 0.02)
    data_status: DataStatus
    data_timestamp: datetime
    horizon: Horizon
    gap_sigma: float = 3.0  # overnight gap scenario in daily vols


@dataclass
class RiskDecision:
    verdict: Verdict
    approved_qty: float
    reasons: list[str]
    checks: dict


def assess(order: OrderIntent, pf: PortfolioState, profile: TraderProfile, now: datetime | None = None) -> RiskDecision:
    now = now or utcnow()
    L = profile.effective_limits()
    reasons: list[str] = []
    checks: dict = {}
    hard_reject = False

    # 1. account-level halts
    dd = 1 - pf.equity / pf.peak_equity
    day = 1 - pf.equity / pf.day_start_equity
    checks["drawdown_pct"], checks["daily_loss_pct"] = round(dd * 100, 3), round(day * 100, 3)
    if dd * 100 >= L.max_drawdown_pct:
        hard_reject = True
        reasons.append(f"max drawdown {dd:.1%} reached: new risk halted")
    if day * 100 >= L.daily_loss_limit_pct:
        hard_reject = True
        reasons.append(f"daily loss limit {L.daily_loss_limit_pct}% reached: trading paused for the day")

    # 2. data freshness for the horizon
    req = HORIZON_DATA_REQUIREMENTS[order.horizon]
    age = (now - order.data_timestamp).total_seconds()
    checks["data_age_s"] = age
    if order.data_status.value not in req["status"] or age > req["max_age_s"]:
        hard_reject = True
        reasons.append(f"{order.horizon.value} requires {req['status']} data <= {req['max_age_s']}s old; "
                       f"got {order.data_status.value}, {age:.0f}s")

    if order.stop_price <= 0 or (order.side == "buy" and order.stop_price >= order.price) or \
            (order.side == "sell_short" and order.stop_price <= order.price):
        hard_reject = True
        reasons.append("a valid stop / invalidation level is required")

    if hard_reject:
        return RiskDecision(Verdict.REJECT, 0.0, reasons, checks)

    eq = pf.equity
    max_qty = order.qty
    # 3. loss per trade at stop, stressed by a gap through the stop
    stop_dist = abs(order.price - order.stop_price)
    gap_dist = max(stop_dist, order.price * order.daily_vol * order.gap_sigma)
    q_loss = (L.max_loss_per_trade_pct / 100 * eq) / gap_dist
    checks["loss_at_stop_gap_scenario"] = round(order.qty * gap_dist, 2)
    # 4. position size
    q_pos = (L.max_position_pct / 100 * eq) / order.price
    # 5. sector concentration
    sector_now = sum(abs(p.notional) for p in pf.positions if p.sector == order.sector)
    q_sector = max(0.0, L.max_sector_pct / 100 * eq - sector_now) / order.price
    # 6. gross leverage
    gross_now = sum(abs(p.notional) for p in pf.positions)
    q_lev = max(0.0, L.max_gross_leverage * eq - gross_now) / order.price
    # 7. liquidity
    q_liq = L.max_adv_participation * order.adv_shares
    caps = {"loss_per_trade": q_loss, "position_size": q_pos, "sector": q_sector, "leverage": q_lev, "liquidity": q_liq}
    checks["caps_qty"] = {k: round(v, 2) for k, v in caps.items()}
    binding = min(caps, key=caps.get)
    max_qty = min(order.qty, *caps.values())
    max_qty = float(int(max_qty))  # whole shares

    if max_qty <= 0:
        return RiskDecision(Verdict.REJECT, 0.0, reasons + [f"no capacity under {binding} limit"], checks)
    if max_qty < order.qty:
        return RiskDecision(Verdict.REDUCE, max_qty, reasons + [f"reduced by {binding} limit"], checks)
    return RiskDecision(Verdict.APPROVE, order.qty, reasons, checks)
