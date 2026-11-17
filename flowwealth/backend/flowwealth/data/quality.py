"""Data-quality checks and a 0-100 quality score per ticker and overall."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class QualityReport:
    rows_in: int
    rows_out: int
    duplicates_removed: int
    ohlc_violations: int
    outliers_flagged: int
    missing_sessions: int
    nonpositive_prices: int
    score: float
    per_ticker_min_score: float

    def to_dict(self) -> dict:
        return asdict(self)


def clean_bars(bars: pd.DataFrame, outlier_z: float = 8.0) -> tuple[pd.DataFrame, QualityReport]:
    """Deduplicate, validate OHLC, flag (do not delete) outliers, count gaps.

    Outliers are flagged via ``quality_flag`` and excluded from features by the
    feature layer; deleting them would hide provider problems.
    """
    n0 = len(bars)
    df = bars.drop_duplicates(subset=["ticker", "date"], keep="first").sort_values(["ticker", "date"])
    dups = n0 - len(df)
    df = df.reset_index(drop=True)

    nonpos = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    ohlc_bad = (df.high < df[["open", "close"]].max(axis=1) - 1e-9) | (df.low > df[["open", "close"]].min(axis=1) + 1e-9)

    # Robust outlier test on log returns of adj_close, per ticker (MAD z-score).
    lr = np.log(df.adj_close).groupby(df.ticker).diff()
    med = lr.groupby(df.ticker).transform("median")
    mad = (lr - med).abs().groupby(df.ticker).transform("median") * 1.4826
    z = (lr - med) / mad.replace(0, np.nan)
    # a bad tick produces a spike and a reversal; flag the bar whose return in and out are both extreme
    z_next = z.groupby(df.ticker).shift(-1)
    spike = (z.abs() > outlier_z) & (z_next.abs() > outlier_z) & (np.sign(z) != np.sign(z_next))
    df["quality_flag"] = np.where(spike, "outlier", np.where(ohlc_bad, "ohlc_violation", "ok"))

    # Missing sessions: expected weekdays between first and last bar minus observed.
    span = df.groupby("ticker").date.agg(["min", "max", "count"])
    expected = np.array([np.busday_count(a.date(), b.date()) + 1 for a, b in zip(span["min"], span["max"])])
    missing_per = np.maximum(expected - span["count"].to_numpy(), 0)

    per_score = 100 - 100 * (missing_per + df.groupby("ticker").quality_flag.apply(lambda s: (s != "ok").sum()).to_numpy() * 5) / span["count"].to_numpy()
    per_score = np.clip(per_score, 0, 100)
    total_bad = int((df.quality_flag != "ok").sum())
    score = float(np.clip(100 - 100 * (dups + total_bad * 5 + missing_per.sum() + nonpos * 10) / max(n0, 1), 0, 100))
    rep = QualityReport(n0, len(df), dups, int(ohlc_bad.sum()), int(spike.sum()),
                        int(missing_per.sum()), nonpos, round(score, 3), round(float(per_score.min()), 3))
    return df, rep
