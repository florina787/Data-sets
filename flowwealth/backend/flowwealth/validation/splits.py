"""Chronological, purged and embargoed splits. Rows are never shuffled across time."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Split:
    name: str
    train_idx: np.ndarray
    test_idx: np.ndarray
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _purge(df: pd.DataFrame, train_mask: np.ndarray, test_start: pd.Timestamp, label_end_col: str) -> np.ndarray:
    """Drop training rows whose label window reaches into the test period.

    Rows with an unknown label end (NaN) are dropped too: their outcome is not
    known, so they cannot be used for training.
    """
    end = pd.to_datetime(df[label_end_col], utc=True)
    ts = pd.Timestamp(test_start)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return train_mask & (end < ts).fillna(False).to_numpy()


def chronological_split(df: pd.DataFrame, label_end_col: str, fractions=(0.6, 0.2, 0.2),
                        embargo_days: int = 5) -> dict[str, np.ndarray]:
    """Train / validation / holdout by event time, with purging and an embargo gap."""
    assert abs(sum(fractions) - 1) < 1e-9
    dates = pd.DatetimeIndex(df["ts"].dt.normalize().unique()).sort_values()
    n = len(dates)
    c1, c2 = int(n * fractions[0]), int(n * (fractions[0] + fractions[1]))
    d = df["ts"].dt.normalize()
    val_start, hold_start = pd.Timestamp(dates[c1]), pd.Timestamp(dates[c2])
    emb = pd.Timedelta(days=embargo_days)
    train = (d < dates[c1]).to_numpy()
    train = _purge(df, train, val_start, label_end_col)
    val = ((d >= val_start + emb) & (d < dates[c2])).to_numpy()
    val = _purge(df, val, hold_start, label_end_col)
    hold = (d >= hold_start + emb).to_numpy()
    return {"train": np.flatnonzero(train), "validation": np.flatnonzero(val), "holdout": np.flatnonzero(hold)}


def walk_forward(df: pd.DataFrame, label_end_col: str, n_folds: int = 5, min_train_frac: float = 0.4,
                 embargo_days: int = 5, expanding: bool = True, end_frac: float = 1.0) -> Iterator[Split]:
    """Expanding (or rolling) walk-forward folds over the first ``end_frac`` of time."""
    dates = pd.DatetimeIndex(df["ts"].dt.normalize().unique()).sort_values()
    dates = dates[: int(len(dates) * end_frac)]
    n = len(dates)
    first = int(n * min_train_frac)
    step = (n - first) // n_folds
    d = df["ts"].dt.normalize()
    emb = pd.Timedelta(days=embargo_days)
    for k in range(n_folds):
        ts0 = pd.Timestamp(dates[first + k * step])
        te = pd.Timestamp(dates[min(first + (k + 1) * step, n - 1)])
        tr_lo = dates[0] if expanding else dates[k * step]
        train = ((d >= tr_lo) & (d < ts0)).to_numpy()
        train = _purge(df, train, ts0, label_end_col)
        test = ((d >= ts0 + emb) & (d < te)).to_numpy()
        yield Split(f"wf{k}", np.flatnonzero(train), np.flatnonzero(test),
                    pd.Timestamp(dates[first + k * step - 1]), ts0 + emb, te)
