"""Independent research risk engine and investment-research profiles.

Trading speed and risk appetite are separate settings. Speeds that need data FLO does not have (intraday, swift) are
DISABLED with the reason rather than producing plausible-looking output. Hard limits apply to every profile and an
"aggressive" appetite can only move limits up to, never past, them.

``assess`` takes measured facts about a security and the user's profile. It has no parameter for agent opinions or
judge decisions, so no agent can override it (a test pins the signature). FLO has no trading capability: the output is a
research risk assessment, never an order.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

SPEEDS = {
    "long_term": {"label": "Long-term", "horizon_sessions": 20, "supported": True, "data": "daily EOD (Kaggle, to 2017-11-10)"},
    "position": {"label": "Position", "horizon_sessions": 20, "supported": True, "data": "daily EOD"},
    "swing": {"label": "Swing", "horizon_sessions": 5, "supported": True, "data": "daily EOD"},
    "intraday": {"label": "Intraday", "horizon_sessions": None, "supported": False,
                 "reason": "Requires intraday bars; FLO only has daily end-of-day history. Disabled rather than approximated."},
    "swift": {"label": "Swift / scalping", "horizon_sessions": None, "supported": False,
              "reason": "Requires licensed tick or order-book data and a live feed; none is available. Daily models are not valid for this."},
}


@dataclass(frozen=True)
class Limits:
    max_position_pct: float
    max_loss_per_idea_pct: float
    max_volatility_annual: float
    min_adv_usd: float
    max_drawdown_tolerance: float


HARD = Limits(max_position_pct=20.0, max_loss_per_idea_pct=3.0, max_volatility_annual=1.00, min_adv_usd=1_000_000, max_drawdown_tolerance=0.60)
APPETITE = {
    "conservative": Limits(5.0, 0.5, 0.30, 20_000_000, 0.25),
    "moderate": Limits(10.0, 1.0, 0.45, 10_000_000, 0.40),
    "aggressive": Limits(20.0, 2.0, 0.80, 5_000_000, 0.55),
}


def effective_limits(appetite: str) -> Limits:
    base = APPETITE[appetite]
    return Limits(min(base.max_position_pct, HARD.max_position_pct), min(base.max_loss_per_idea_pct, HARD.max_loss_per_idea_pct),
                  min(base.max_volatility_annual, HARD.max_volatility_annual), max(base.min_adv_usd, HARD.min_adv_usd),
                  min(base.max_drawdown_tolerance, HARD.max_drawdown_tolerance))


def assess(*, ticker: str, volatility_annual: float | None, drawdown_1y: float | None, adv_usd: float | None, data_status: str,
           speed: str = "swing", appetite: str = "moderate") -> dict:
    if speed not in SPEEDS or appetite not in APPETITE:
        raise ValueError("unknown speed or appetite")
    sp = SPEEDS[speed]
    lim = effective_limits(appetite)
    checks, blockers = [], []
    if not sp["supported"]:
        blockers.append(sp["reason"])
    if data_status != "live":
        checks.append({"check": "data_freshness", "status": "research_only",
                       "detail": "Historical data: suitable for research, not for acting today."})
    if volatility_annual is not None:
        ok = volatility_annual <= lim.max_volatility_annual
        checks.append({"check": "volatility", "status": "within" if ok else "exceeds", "value": round(volatility_annual, 4),
                       "limit": lim.max_volatility_annual})
    if drawdown_1y is not None:
        ok = abs(drawdown_1y) <= lim.max_drawdown_tolerance
        checks.append({"check": "drawdown_1y", "status": "within" if ok else "exceeds", "value": round(drawdown_1y, 4),
                       "limit": -lim.max_drawdown_tolerance})
    if adv_usd is not None:
        ok = adv_usd >= lim.min_adv_usd
        checks.append({"check": "liquidity_adv_usd", "status": "within" if ok else "below_minimum", "value": round(adv_usd),
                       "limit": lim.min_adv_usd})
    # A position cap implied by volatility: the size at which a 2-sigma daily move costs max_loss_per_idea.
    if volatility_annual:
        daily = volatility_annual / 252 ** 0.5
        cap = min(lim.max_position_pct, lim.max_loss_per_idea_pct / (2 * daily * 100) * 100)
        checks.append({"check": "volatility_sized_position_cap_pct", "status": "info", "value": round(cap, 2), "limit": lim.max_position_pct})
    exceeded = [c["check"] for c in checks if c["status"] in ("exceeds", "below_minimum")]
    status = "unsupported_mode" if blockers else "outside_profile_limits" if exceeded else "within_profile_limits"
    return {"ticker": ticker, "speed": speed, "appetite": appetite, "status": status, "blockers": blockers, "checks": checks,
            "effective_limits": asdict(lim), "hard_limits": asdict(HARD), "execution": "none: FLO has no trading capability",
            "note": "Aggressive appetite widens limits only up to the hard limits; it never disables them."}


def profiles() -> dict:
    return {"speeds": SPEEDS, "appetites": {k: asdict(effective_limits(k)) for k in APPETITE}, "hard_limits": asdict(HARD),
            "independent": "Speed and appetite are separate settings; changing them never retrains a model."}
