"""HTTP adapters for free/freemium sources. Keys come from the environment only.

None of these were reachable from the build container (see DATA_PROVIDER_MATRIX.md);
they are covered by tests with recorded payloads, not by live calls.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

import httpx
import pandas as pd

from flowwealth.contracts import DataStatus
from .base import MarketDataProvider, ProviderError, RateLimiter


def _client() -> httpx.Client:
    return httpx.Client(timeout=20, headers={"User-Agent": "flowwealth-research/4.0"})


@dataclass
class StooqDaily(MarketDataProvider):
    name: str = "stooq"
    license_note: str = "Stooq free EOD data; personal/research use, check terms before redistribution"

    def parse(self, ticker: str, text: str) -> pd.DataFrame:
        if not text.strip() or text.lstrip().startswith(("No data", "Too Many")):
            raise ProviderError(f"stooq returned no data for {ticker}")
        raw = pd.read_csv(io.StringIO(text))
        df = raw.rename(columns=str.lower)
        df["ticker"] = ticker.upper()
        df["date"] = pd.to_datetime(df["date"])
        df["adj_close"] = df["close"]  # stooq closes are split-adjusted
        return df

    def _fetch(self, ticker, start, end):
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}&i=d&d1={start.replace('-', '')}&d2={end.replace('-', '')}"
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
        return self.parse(ticker, r.text)


@dataclass
class AlphaVantageDaily(MarketDataProvider):
    name: str = "alphavantage"
    license_note: str = "Alpha Vantage free tier (25 req/day); attribution required"
    limiter: RateLimiter = field(default_factory=lambda: RateLimiter(5, 60))

    def parse(self, ticker: str, payload: dict) -> pd.DataFrame:
        series = payload.get("Time Series (Daily)")
        if not series:
            raise ProviderError(payload.get("Note") or payload.get("Information") or "no series")
        rows = [{
            "ticker": ticker.upper(), "date": pd.Timestamp(d),
            "open": float(v["1. open"]), "high": float(v["2. high"]), "low": float(v["3. low"]),
            "close": float(v["4. close"]), "adj_close": float(v.get("5. adjusted close", v["4. close"])),
            "volume": float(v.get("6. volume", v.get("5. volume", 0))),
        } for d, v in series.items()]
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    def _fetch(self, ticker, start, end):
        key = os.environ.get("ALPHAVANTAGE_API_KEY")
        if not key:
            raise ProviderError("ALPHAVANTAGE_API_KEY not set")
        with _client() as c:
            r = c.get("https://www.alphavantage.co/query", params={
                "function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": ticker,
                "outputsize": "full", "apikey": key})
            r.raise_for_status()
        df = self.parse(ticker, r.json())
        return df[(df.date >= start) & (df.date <= end)]


@dataclass
class FredSeries:
    """FRED macro series. Uses ALFRED real-time vintages so values are point-in-time."""

    api_key_env: str = "FRED_API_KEY"
    status: DataStatus = DataStatus.HISTORICAL

    def parse(self, payload: dict) -> pd.DataFrame:
        obs = payload.get("observations")
        if obs is None:
            raise ProviderError(payload.get("error_message", "no observations"))
        df = pd.DataFrame(obs)
        df = df[df["value"] != "."]
        return pd.DataFrame({
            "date": pd.to_datetime(df["date"]),
            "value": df["value"].astype(float),
            # realtime_start = first day this value was publicly known -> available_at
            "available_at": pd.to_datetime(df["realtime_start"]).dt.tz_localize("America/Chicago"),
        })

    def get(self, series_id: str) -> pd.DataFrame:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ProviderError(f"{self.api_key_env} not set")
        with _client() as c:
            r = c.get("https://api.stlouisfed.org/fred/series/observations", params={
                "series_id": series_id, "api_key": key, "file_type": "json",
                "realtime_start": "1776-07-04", "realtime_end": "9999-12-31"})
            r.raise_for_status()
        return self.parse(r.json())
