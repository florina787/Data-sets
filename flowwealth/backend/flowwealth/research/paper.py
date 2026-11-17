"""Paper trading: simulated fills only. There is no brokerage connector in this codebase."""
from __future__ import annotations

from dataclasses import dataclass, field

from flowwealth.contracts import utcnow
from flowwealth.research.costs import CostModel
from flowwealth.risk.engine import OrderIntent, PortfolioState, Position, RiskDecision, Verdict, assess
from flowwealth.profiles.profile import TraderProfile


@dataclass
class PaperAccount:
    profile: TraderProfile
    cash: float
    costs: CostModel = field(default_factory=CostModel)
    positions: dict[str, Position] = field(default_factory=dict)
    peak_equity: float = 0.0
    day_start_equity: float = 0.0
    blotter: list[dict] = field(default_factory=list)
    mode: str = "PAPER"  # never LIVE

    def __post_init__(self):
        self.peak_equity = self.day_start_equity = self.cash

    def equity(self, marks: dict[str, float] | None = None) -> float:
        marks = marks or {}
        return self.cash + sum(p.qty * marks.get(t, p.price) for t, p in self.positions.items())

    def state(self, marks=None) -> PortfolioState:
        eq = self.equity(marks)
        self.peak_equity = max(self.peak_equity, eq)
        return PortfolioState(eq, self.peak_equity, self.day_start_equity, list(self.positions.values()))

    def submit(self, order: OrderIntent, marks=None) -> RiskDecision:
        decision = assess(order, self.state(marks), self.profile)
        rec = {"at": utcnow().isoformat(), "ticker": order.ticker, "side": order.side, "requested": order.qty,
               "verdict": decision.verdict.value, "reasons": decision.reasons, "mode": self.mode}
        if decision.verdict != Verdict.REJECT:
            q = decision.approved_qty * (1 if order.side == "buy" else -1)
            part = decision.approved_qty / max(order.adv_shares, 1)
            fee = abs(q) * order.price * float(self.costs.per_side_bps(part)) / 1e4
            self.cash -= q * order.price + fee
            pos = self.positions.get(order.ticker)
            if pos:
                new_q = pos.qty + q
                pos.price = order.price if new_q and (pos.qty == 0 or (new_q > 0) != (pos.qty > 0)) else \
                    (pos.price * pos.qty + order.price * q) / new_q if new_q else order.price
                pos.qty = new_q
                if pos.qty == 0:
                    del self.positions[order.ticker]
            else:
                self.positions[order.ticker] = Position(order.ticker, q, order.price, order.sector)
            rec.update(filled=abs(q), fill_price=order.price, cost=round(fee, 2))
        self.blotter.append(rec)
        return decision
