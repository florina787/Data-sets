"""Tiny generated market fixture for SOFTWARE tests only (labelled synthetic; never usable for research).

It mimics the normalised Kaggle layouts so the real lake/feature/ledger code paths run in CI without redistributing
licensed data. It plants known defects: a bad tick, an OHLC violation, an unadjusted spin-off and a missing session.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from markets import catalog

FIXTURE_TICKERS = [f"T{i:02d}" for i in range(40)]


def build(root: Path, n_days: int = 700, seed: int = 3) -> dict:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2005-02-25", periods=n_days)
    rows = []
    spy = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n_days)))
    for d, c in zip(days, spy):
        rows.append(("SPY", "etf", d.date(), c, c * 1.002, c * 0.998, c, 1_000_000))
    for i, t in enumerate(FIXTURE_TICKERS):
        px = (20 + i) * np.exp(np.cumsum(rng.normal(0.0002, 0.02, n_days)))
        vol = rng.integers(10_000, 2_000_000, n_days)
        for k, (d, c, v) in enumerate(zip(days, px, vol)):
            if t == "T05" and k == 400:
                continue  # missing session
            o, hi, lo = c * 1.001, c * 1.01, c * 0.99
            if t == "T01" and k == 300:
                c = c * 3; o, hi, lo = c, c * 1.01, c * 0.99  # bad tick that reverses next day
            if t == "T02" and k == 310:
                hi = min(o, c) * 0.9  # OHLC violation
            rows.append((t, "stock", d.date(), o, hi, lo, c, int(v)))
    bars = pd.DataFrame(rows, columns=["ticker", "asset_type", "date", "open", "high", "low", "adj_close", "volume"])
    # unadjusted spin-off on T03 at day 500: primary drops 30%, secondary records the adjustment step
    m = (bars.ticker == "T03") & (bars.date >= days[500].date())
    bars.loc[m, ["open", "high", "low", "adj_close"]] *= 0.7
    bars["dataset_id"] = catalog.PRIMARY
    p = root / "lake" / catalog.PRIMARY
    p.mkdir(parents=True)
    bars.to_parquet(p / "bars.parquet", index=False)
    s = root / "lake" / catalog.SECONDARY
    s.mkdir(parents=True)
    sec = bars[bars.ticker.isin(["T03", "T04"])].rename(columns={"adj_close": "close"})[["ticker", "date", "open", "high", "low", "close", "volume"]]
    raw = sec.copy()
    adj = sec.copy()
    ts = adj.ticker == "T03"
    adj.loc[ts & (adj.date < days[500].date()), "close"] *= 0.7  # secondary back-adjusts the spin-off
    gone = pd.DataFrame([("GONE", days[0].date(), 1.0, 1.0, 1.0, 1.0, 1)], columns=raw.columns)  # delisted name absent from primary
    pd.concat([raw, gone]).to_parquet(s / "prices_raw.parquet", index=False)
    pd.concat([adj, gone]).to_parquet(s / "prices_split_adjusted.parquet", index=False)
    pd.DataFrame({"ticker": ["T03", "T04"], "name": ["Three Corp", "Four Inc"], "sector": ["Industrials", "Energy"],
                  "sub_industry": ["x", "y"], "headquarters": ["A", "B"], "date_first_added": ["", ""], "cik": ["1", "2"]}
                 ).to_parquet(s / "securities.parquet", index=False)
    return {"days": days, "bars": bars}
