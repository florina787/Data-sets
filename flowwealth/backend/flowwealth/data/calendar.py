"""Exchange metadata and session alignment.

Daily bars are stamped at the exchange's local close, converted to UTC, so data
from different time zones lines up on true event time. Holiday calendars are
NOT bundled: trading days are weekdays, and missing weekdays are reported by the
quality checks rather than silently filled. Plug in ``exchange_calendars`` for
production (see DATA_PROVIDER_MATRIX.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd


@dataclass(frozen=True)
class Exchange:
    code: str
    tz: str
    close: time
    country: str
    eod_publication_lag_min: int = 30  # when an EOD bar is reliably available


EXCHANGES: dict[str, Exchange] = {
    e.code: e
    for e in [
        Exchange("XNYS", "America/New_York", time(16, 0), "US"),
        Exchange("XNAS", "America/New_York", time(16, 0), "US"),
        Exchange("XTSE", "America/Toronto", time(16, 0), "CA"),
        Exchange("XLON", "Europe/London", time(16, 30), "GB"),
        Exchange("XETR", "Europe/Berlin", time(17, 30), "DE"),
        Exchange("XPAR", "Europe/Paris", time(17, 30), "FR"),
        Exchange("XTKS", "Asia/Tokyo", time(15, 0), "JP"),
        Exchange("XHKG", "Asia/Hong_Kong", time(16, 0), "HK"),
        Exchange("XNSE", "Asia/Kolkata", time(15, 30), "IN"),
        Exchange("XASX", "Australia/Sydney", time(16, 0), "AU"),
        Exchange("BVMF", "America/Sao_Paulo", time(17, 0), "BR"),
    ]
}


def trading_days(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


def close_timestamps_utc(dates: pd.DatetimeIndex | pd.Series, exchange: str) -> pd.Series:
    """Local session close for each date, as UTC."""
    ex = EXCHANGES[exchange]
    d = pd.to_datetime(pd.Series(dates)).dt.normalize()
    local = d + pd.Timedelta(hours=ex.close.hour, minutes=ex.close.minute)
    return local.dt.tz_localize(ex.tz, nonexistent="shift_forward", ambiguous=False).dt.tz_convert("UTC")


def available_at_utc(close_utc: pd.Series, exchange: str) -> pd.Series:
    return close_utc + pd.Timedelta(minutes=EXCHANGES[exchange].eod_publication_lag_min)
