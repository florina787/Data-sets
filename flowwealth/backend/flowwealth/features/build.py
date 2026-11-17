"""Leakage-safe features and horizon-specific labels.

Rules enforced here (and tested in tests/test_leakage.py):
* a feature at bar t uses only bars <= t (rolling windows, never centred, never shifted negative);
* bars flagged as outliers are excluded from feature inputs;
* labels use bars t+1..t+h and carry ``label_end_ts`` so splits can purge overlaps;
* a ticker that delists inside the horizon gets its delisting return (last price),
  not a dropped row -- dropping it would be survivorship bias;
* cross-sectional ranks are computed per *availability cohort* (bars sharing one
  ``available_at``), never per calendar date: exchanges close at different UTC
  times, and a per-date rank would let an Asian close "see" New York bars that
  only exist ~15 hours later.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Feature lineage registry: name -> (inputs, lookback bars, description)
FEATURES: dict[str, tuple[str, int, str]] = {
    "ret_1": ("adj_close", 1, "1-bar log return"),
    "ret_5": ("adj_close", 5, "5-bar log return"),
    "ret_20": ("adj_close", 20, "20-bar log return (short momentum)"),
    "ret_60_skip5": ("adj_close", 60, "60-bar return excluding last 5 (medium momentum)"),
    "vol_20": ("adj_close", 20, "20-bar realized volatility"),
    "vol_ratio": ("adj_close", 60, "vol_20 / vol_60 (volatility expansion)"),
    "dist_ma50": ("adj_close", 50, "log distance from 50-bar mean"),
    "dd_60": ("adj_close", 60, "drawdown from 60-bar high"),
    "volu_z20": ("volume", 20, "log volume z-score vs 20 bars"),
    "range_20": ("high,low,close", 20, "mean (high-low)/close over 20 bars"),
}


def build_features(bars: pd.DataFrame, horizons: tuple[int, ...] = (5,), rank: bool = True) -> pd.DataFrame:
    df = bars.sort_values(["ticker", "ts"]).reset_index(drop=True).copy()
    px = df["adj_close"].where(df.get("quality_flag", "ok") == "ok")
    g = px.groupby(df["ticker"])
    lp = np.log(px)
    lr = lp.groupby(df["ticker"]).diff()
    by = lr.groupby(df["ticker"])

    f = pd.DataFrame(index=df.index)
    f["ret_1"] = lr
    f["ret_5"] = lp - lp.groupby(df.ticker).shift(5)
    f["ret_20"] = lp - lp.groupby(df.ticker).shift(20)
    f["ret_60_skip5"] = lp.groupby(df.ticker).shift(5) - lp.groupby(df.ticker).shift(60)
    v20 = by.transform(lambda s: s.rolling(20, min_periods=15).std())
    v60 = by.transform(lambda s: s.rolling(60, min_periods=45).std())
    f["vol_20"] = v20
    f["vol_ratio"] = v20 / v60
    f["dist_ma50"] = lp - lp.groupby(df.ticker).transform(lambda s: s.rolling(50, min_periods=40).mean())
    f["dd_60"] = px / g.transform(lambda s: s.rolling(60, min_periods=40).max()) - 1
    lv = np.log1p(df["volume"])
    lvg = lv.groupby(df.ticker)
    f["volu_z20"] = (lv - lvg.transform(lambda s: s.rolling(20, min_periods=15).mean())) / \
        lvg.transform(lambda s: s.rolling(20, min_periods=15).std())
    rng = (df["high"] - df["low"]) / df["close"]
    f["range_20"] = rng.groupby(df.ticker).transform(lambda s: s.rolling(20, min_periods=15).mean())

    cohort = df["available_at"]
    if rank:
        for c in list(FEATURES):
            f[f"{c}_rk"] = f[c].groupby(cohort).rank(pct=True) - 0.5

    out = pd.concat([df[["ticker", "ts", "available_at", "adj_close"]], f], axis=1)

    # Labels
    delisted_last = df.groupby("ticker")["ts"].transform("max")
    dataset_end = df["ts"].max()
    for h in horizons:
        fwd_px = g.shift(-h)
        fwd_ts = df.groupby("ticker")["ts"].shift(-h)
        # delisted inside horizon: realize at last available price
        last_px = g.transform("last")
        delisted = delisted_last < dataset_end
        fill = fwd_px.isna() & delisted & (df["ts"] < delisted_last)  # last bar itself: no tradable future
        fwd_px = fwd_px.where(~fill, last_px)
        fwd_ts = fwd_ts.where(~fill, delisted_last)
        out[f"fwd_ret_{h}"] = np.log(fwd_px / px)
        out[f"label_end_{h}"] = fwd_ts
        xs = out[f"fwd_ret_{h}"].groupby(cohort)
        out[f"fwd_xs_{h}"] = out[f"fwd_ret_{h}"] - xs.transform("mean")  # cross-sectional (market-neutral) target
        out[f"fwd_up_{h}"] = (out[f"fwd_ret_{h}"] > 0).astype(float).where(out[f"fwd_ret_{h}"].notna())
    return out


def feature_columns(ranked: bool = True) -> list[str]:
    return [f"{c}_rk" for c in FEATURES] if ranked else list(FEATURES)
