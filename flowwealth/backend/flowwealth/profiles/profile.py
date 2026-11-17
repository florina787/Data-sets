"""Trader profiles: trading horizon and risk appetite are independent axes.

Fast != aggressive. A conservative scalper and an aggressive long-term investor
are both valid. Changing a profile re-routes to horizon-specific models and
re-parameterises the risk engine; it never retrains a model.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from flowwealth.contracts import Horizon


class Appetite(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class RiskLimits(BaseModel):
    max_loss_per_trade_pct: float = Field(gt=0)       # of equity, at stop (incl. gap scenario)
    max_position_pct: float = Field(gt=0)             # single-name notional / equity
    max_sector_pct: float = Field(gt=0)
    max_gross_leverage: float = Field(gt=0)           # gross notional / equity
    daily_loss_limit_pct: float = Field(gt=0)
    max_drawdown_pct: float = Field(gt=0)             # trading halts beyond this
    max_adv_participation: float = Field(gt=0)


# Core protections: no profile, setting or agent can loosen these.
HARD_LIMITS = RiskLimits(max_loss_per_trade_pct=3.0, max_position_pct=25.0, max_sector_pct=50.0,
                         max_gross_leverage=2.0, daily_loss_limit_pct=6.0, max_drawdown_pct=30.0,
                         max_adv_participation=0.10)

APPETITE_DEFAULTS: dict[Appetite, RiskLimits] = {
    Appetite.CONSERVATIVE: RiskLimits(max_loss_per_trade_pct=0.5, max_position_pct=5, max_sector_pct=20,
                                      max_gross_leverage=1.0, daily_loss_limit_pct=1.5, max_drawdown_pct=10,
                                      max_adv_participation=0.01),
    Appetite.MODERATE: RiskLimits(max_loss_per_trade_pct=1.0, max_position_pct=10, max_sector_pct=30,
                                  max_gross_leverage=1.0, daily_loss_limit_pct=3.0, max_drawdown_pct=18,
                                  max_adv_participation=0.03),
    Appetite.AGGRESSIVE: RiskLimits(max_loss_per_trade_pct=2.0, max_position_pct=20, max_sector_pct=40,
                                    max_gross_leverage=2.0, daily_loss_limit_pct=5.0, max_drawdown_pct=25,
                                    max_adv_participation=0.05),
}

# Data each horizon needs before signals may be shown as actionable.
HORIZON_DATA_REQUIREMENTS = {
    Horizon.SCALP: {"status": ["LIVE"], "max_age_s": 2, "needs": ["licensed tick/L2 feed", "bid/ask"]},
    Horizon.INTRADAY: {"status": ["LIVE", "DELAYED"], "max_age_s": 60 * 15, "needs": ["intraday bars"]},
    Horizon.SWING: {"status": ["LIVE", "DELAYED", "HISTORICAL"], "max_age_s": 3600 * 30, "needs": ["daily bars"]},
    Horizon.POSITION: {"status": ["LIVE", "DELAYED", "HISTORICAL"], "max_age_s": 3600 * 24 * 4, "needs": ["daily bars", "fundamentals"]},
    Horizon.LONG_TERM: {"status": ["LIVE", "DELAYED", "HISTORICAL"], "max_age_s": 3600 * 24 * 7, "needs": ["fundamentals"]},
}


class TraderProfile(BaseModel):
    user_id: str
    horizon: Horizon
    appetite: Appetite
    capital: float = Field(gt=0)
    objectives: str = ""
    preferred_markets: list[str] = Field(default_factory=lambda: ["US"])
    leverage_permitted: bool = False
    experience: str = "beginner"
    quant_mode: bool = False
    overrides: dict[str, float] = Field(default_factory=dict)  # user can tighten (or loosen up to HARD_LIMITS)

    def effective_limits(self) -> RiskLimits:
        base = APPETITE_DEFAULTS[self.appetite].model_dump()
        base.update({k: v for k, v in self.overrides.items() if k in base})
        if not self.leverage_permitted:
            base["max_gross_leverage"] = min(base["max_gross_leverage"], 1.0)
        hard = HARD_LIMITS.model_dump()
        return RiskLimits(**{k: min(v, hard[k]) for k, v in base.items()})

    def model_route(self) -> str:
        return f"champion:{self.horizon.value}"
