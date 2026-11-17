"""Transaction cost model. Backtests always report gross AND net."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 1.0       # per side
    half_spread_bps: float = 5.0      # per side, at normal volatility
    slippage_bps: float = 2.0         # execution delay / adverse selection
    impact_bps_at_1pct_adv: float = 10.0  # square-root impact: bps at 1% of ADV
    borrow_bps_annual: float = 50.0   # short borrow
    max_participation: float = 0.05   # liquidity constraint: order <= 5% ADV

    def per_side_bps(self, participation: np.ndarray | float, vol_mult: np.ndarray | float = 1.0) -> np.ndarray:
        """Cost in bps of traded notional for one side of a trade."""
        p = np.clip(np.asarray(participation, dtype=float), 0, None)
        impact = self.impact_bps_at_1pct_adv * np.sqrt(p / 0.01)
        return self.commission_bps + self.half_spread_bps * np.asarray(vol_mult) + self.slippage_bps + impact

    def borrow_bps(self, days: float) -> float:
        return self.borrow_bps_annual * days / 252
