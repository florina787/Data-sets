import json
from datetime import timedelta

import httpx
import pandas as pd
import pytest

from flowwealth.contracts import DataStatus, PredictionIn, utcnow
from flowwealth.data.calendar import close_timestamps_utc
from flowwealth.data.providers.base import MarketDataProvider, ProviderError, RateLimiter
from flowwealth.data.providers.http_providers import AlphaVantageDaily, FredSeries, StooqDaily


def test_quality_catches_every_injected_defect(small_universe, clean_small):
    raw, _, meta = small_universe
    _, _, rep = clean_small
    inj = meta["injected"]
    assert rep.duplicates_removed == inj["duplicates"]
    assert rep.outliers_flagged == inj["bad_ticks"]
    # a duplicate of a row that a gap later removed re-fills that gap, so allow a small shortfall
    assert 0.98 * inj["gaps"] <= rep.missing_sessions <= inj["gaps"]
    assert rep.ohlc_violations == 0
    assert 0 < rep.score <= 100


def test_split_is_adjusted_in_adj_close(clean_small):
    bars, _, _ = clean_small
    s = bars[bars.ticker == "SYN0003"].sort_values("ts")
    raw_jump = (s.close / s.close.shift()).min()
    adj_jump = (s.adj_close / s.adj_close.shift()).min()
    assert raw_jump < 0.6 and adj_jump > 0.8  # raw halves at the split, adjusted does not


def test_exchange_timezones_align_to_utc():
    d = pd.DatetimeIndex(["2024-07-01"])
    ny = close_timestamps_utc(d, "XNYS").iloc[0]
    tk = close_timestamps_utc(d, "XTKS").iloc[0]
    assert ny.hour == 20 and tk.hour == 6  # 16:00 EDT, 15:00 JST
    assert tk < ny


def test_lake_versions_are_immutable(lake, clean_small):
    bars, master, rep = clean_small
    with pytest.raises(FileExistsError):
        lake.write_version("t1", bars, master, {}, {})
    m = lake.manifest("t1")
    assert m["rows"] == len(bars) and m["status_counts"] == {"SYNTHETIC": len(bars)}


def test_as_of_query_never_returns_future_data(lake):
    as_of = pd.Timestamp("2021-06-15 20:10", tz="UTC")  # 10 min after NY close: NY bar not yet available
    df = lake.bars_as_of("t1", as_of)
    assert (pd.to_datetime(df.available_at, utc=True) <= as_of).all()
    ny_today = df[(df.exchange == "XNYS") & (pd.to_datetime(df.ts, utc=True).dt.date == as_of.date())]
    assert ny_today.empty


def test_universe_as_of_includes_later_delisted(lake, clean_small):
    _, master, _ = clean_small
    delisted = master.dropna(subset=["delisted"])
    assert len(delisted) > 0
    row = delisted.iloc[0]
    before = row.delisted - pd.Timedelta(days=30)
    assert row.ticker in lake.universe_as_of("t1", before.tz_localize("UTC"))
    assert row.ticker not in lake.universe_as_of("t1", (row.delisted + pd.Timedelta(days=5)).tz_localize("UTC"))


def test_stooq_and_alphavantage_parsers():
    df = StooqDaily().parse("spy.us", "Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,1.5,100\n")
    assert list(df.columns)[:2] == ["date", "open"] and df.ticker.iloc[0] == "SPY.US"
    with pytest.raises(ProviderError):
        StooqDaily().parse("x", "")
    av = AlphaVantageDaily().parse("IBM", {"Time Series (Daily)": {"2024-01-02": {
        "1. open": "1", "2. high": "2", "3. low": "0.5", "4. close": "1.5", "5. adjusted close": "1.4", "6. volume": "10"}}})
    assert av.adj_close.iloc[0] == 1.4
    with pytest.raises(ProviderError):
        AlphaVantageDaily().parse("IBM", {"Note": "rate limited"})


def test_fred_uses_realtime_vintage_as_available_at():
    df = FredSeries().parse({"observations": [
        {"date": "2024-01-01", "value": "3.1", "realtime_start": "2024-02-13"},
        {"date": "2024-02-01", "value": ".", "realtime_start": "2024-03-12"}]})
    assert len(df) == 1 and df.available_at.iloc[0].date().isoformat() == "2024-02-13"


class _Fake(MarketDataProvider):
    calls = 0

    def _fetch(self, ticker, start, end):
        _Fake.calls += 1
        if _Fake.calls == 1:
            raise httpx.ConnectError("boom")
        return pd.DataFrame({"ticker": [ticker], "date": [pd.Timestamp(start)], "open": [1.0], "high": [1.0],
                             "low": [1.0], "close": [1.0], "adj_close": [1.0], "volume": [1.0]})


def test_provider_retries_caches_and_labels_stale_cache(tmp_path):
    p = _Fake(name="fake", license_note="test", cache_dir=tmp_path, backoff_s=0, freshness=timedelta(hours=1))
    r1 = p.get_daily("AAA", "2024-01-01", "2024-01-02")
    assert _Fake.calls == 2 and r1.provenance.status == DataStatus.HISTORICAL
    r2 = p.get_daily("AAA", "2024-01-01", "2024-01-02")
    assert _Fake.calls == 2 and "cache" in r2.provenance.source
    meta = next(tmp_path.rglob("*.json"))
    meta.write_text(json.dumps({"retrieved_at": (utcnow() - timedelta(days=3)).isoformat(), "status": "HISTORICAL"}))
    assert p.get_daily("AAA", "2024-01-01", "2024-01-02").provenance.status == DataStatus.CACHED


def test_rate_limiter_blocks_when_bucket_empty():
    t = [0.0]
    slept = []
    rl = RateLimiter(2, 10, clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    rl.acquire(); rl.acquire(); rl.acquire()
    assert slept and sum(slept) >= 4.9


def test_contracts_reject_naive_timestamps():
    from datetime import datetime
    with pytest.raises(ValueError):
        PredictionIn(model_version="m", strategy_id="s", ticker="X", horizon="swing", horizon_bars=5,
                     input_cutoff=datetime(2024, 1, 1), target_time=datetime(2024, 1, 8), data_status="SYNTHETIC")
