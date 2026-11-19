"""Current market data adapter and the forward-research scheduler gate.

Historical Kaggle data trains and evaluates models; it is not a current feed. Forward testing (recording predictions at
the real clock, resolving them later) needs a licensed, fresh daily feed for the WHOLE research universe (~1,000 names)
because the model ranks names against each other.

The adapter below supports Alpha Vantage (key from FLO_ALPHAVANTAGE_API_KEY, never logged or sent to the browser). Its free
tier allows 25 requests/day, which cannot cover the universe, so the scheduler stays DISABLED with that reason unless a
plan with enough capacity is declared (FLO_MARKET_FEED_DAILY_CAPACITY). Nothing here ever fabricates a price.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable

UNIVERSE_SIZE = 1000
FRESHNESS = timedelta(hours=30)  # an EOD bar older than this is stale for forward use


class FeedError(RuntimeError):
    pass


@dataclass
class Quote:
    ticker: str
    trade_date: date
    adj_close: float
    volume: int
    source: str
    retrieved_at: datetime

    def is_fresh(self, now: datetime, session_close: datetime) -> bool:
        return self.retrieved_at >= session_close and now - session_close <= FRESHNESS


def _http_get(url: str, params: dict) -> dict:
    import httpx
    r = httpx.get(url, params=params, timeout=15, headers={"User-Agent": "flo-research/1.0"})
    r.raise_for_status()
    return r.json()


class AlphaVantageDaily:
    name = "alphavantage"

    def __init__(self, api_key: str | None = None, transport: Callable[[str, dict], dict] = _http_get):
        self.api_key = api_key if api_key is not None else os.environ.get("FLO_ALPHAVANTAGE_API_KEY")
        self.transport = transport

    def latest(self, ticker: str, now: datetime | None = None) -> Quote:
        if not self.api_key:
            raise FeedError("FLO_ALPHAVANTAGE_API_KEY is not set")
        data = self.transport("https://www.alphavantage.co/query", {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": ticker,
                                                                    "outputsize": "compact", "apikey": self.api_key})
        series = data.get("Time Series (Daily)")
        if not series:
            raise FeedError(data.get("Note") or data.get("Information") or data.get("Error Message") or "no series returned")
        d = max(series)
        v = series[d]
        return Quote(ticker.upper(), date.fromisoformat(d), float(v.get("5. adjusted close", v["4. close"])), int(float(v.get("6. volume", 0))),
                     self.name, now or datetime.now(timezone.utc))


def status() -> dict:
    key = bool(os.environ.get("FLO_ALPHAVANTAGE_API_KEY"))
    cap = int(os.environ.get("FLO_MARKET_FEED_DAILY_CAPACITY", "25" if key else "0"))
    reasons = []
    if not key:
        reasons.append("No current market-data credential is configured (FLO_ALPHAVANTAGE_API_KEY).")
    if cap < UNIVERSE_SIZE:
        reasons.append(f"Daily feed capacity {cap} requests is below the {UNIVERSE_SIZE}-name universe the model ranks; "
                       "partial cross-sections would bias forward predictions.")
    enabled = not reasons
    return {"provider": AlphaVantageDaily.name, "credential_configured": key, "daily_capacity": cap, "required_capacity": UNIVERSE_SIZE,
            "scheduler_enabled": enabled, "reasons": reasons,
            "what_runs_when_enabled": ["fetch EOD bars after 16:30 New York", "reject stale or partial data", "compute features",
                                       "load the approved (promoted) model only", "record forecasts with mode=forward",
                                       "resolve outcomes after the horizon", "refresh evaluation views"],
            "approved_model_required": True,
            "note": "Without an enabled feed FLO shows historical research only and never presents prices as current."}


def forward_job(now: datetime | None = None) -> dict:
    """Entry point for the scheduler. Refuses to run unless every precondition holds; never invents data."""
    st = status()
    if not st["scheduler_enabled"]:
        return {"ran": False, "reasons": st["reasons"]}
    from markets.service import model_report
    rep = model_report()
    if not any(d["status"] == "promoted" for h in rep["horizons"].values() for d in h["decisions"]):
        return {"ran": False, "reasons": ["No model has been promoted; forward predictions require an approved model."]}
    return {"ran": False, "reasons": ["Forward job body requires a configured universe feed implementation."]}
