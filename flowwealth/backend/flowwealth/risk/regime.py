"""Market regime and crash-risk level from transparent indicators.

Levels are estimated *conditions*, not crash predictions. ``evaluate_alarm``
scores them against subsequent drawdowns (precision, recall, false alarms),
which is what the dashboard shows next to the meter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LEVELS = ["Normal", "Elevated", "High", "Critical"]


def market_index(bars: pd.DataFrame) -> pd.Series:
    """Equal-weight daily index from point-in-time bars (survivors and delisted alike)."""
    df = bars[bars.get("quality_flag", "ok") == "ok"] if "quality_flag" in bars else bars
    r = np.log(df["adj_close"]).groupby(df["ticker"]).diff()
    daily = r.groupby(df["ts"].dt.normalize()).mean()
    return daily.fillna(0)


def indicators(index_ret: pd.Series, bars: pd.DataFrame | None = None, lookback: int = 252) -> pd.DataFrame:
    lvl = np.exp(index_ret.cumsum())
    out = pd.DataFrame(index=index_ret.index)
    out["vol_20"] = index_ret.rolling(20).std() * np.sqrt(252)
    out["vol_pctile"] = out["vol_20"].rolling(lookback, min_periods=60).rank(pct=True)
    out["trend_200"] = lvl / lvl.rolling(200, min_periods=100).mean() - 1
    # drawdown from the rolling 1-year peak; an all-time peak keeps the flag on for years after one crash
    out["drawdown"] = lvl / lvl.rolling(lookback, min_periods=1).max() - 1
    if bars is not None:
        df = bars.sort_values(["ticker", "ts"])
        ma50 = df.groupby("ticker")["adj_close"].transform(lambda s: s.rolling(50, min_periods=40).mean())
        above = (df["adj_close"] > ma50).groupby(df["ts"].dt.normalize()).mean()
        out["breadth_above_ma50"] = above.reindex(out.index)
        r = np.log(df["adj_close"]).groupby(df["ticker"]).diff()
        disp = r.groupby(df["ts"].dt.normalize()).std()
        out["dispersion"] = disp.reindex(out.index)
    return out


def classify(ind: pd.DataFrame) -> pd.DataFrame:
    """Score 0-4 from independent stress signals -> level; plus a trend/vol regime label."""
    s = (ind["vol_pctile"] > 0.80).astype(int) + (ind["vol_pctile"] > 0.95).astype(int) \
        + (ind["drawdown"] < -0.10).astype(int) + (ind["trend_200"] < 0).astype(int)
    if "breadth_above_ma50" in ind:
        s = s + (ind["breadth_above_ma50"] < 0.30).astype(int)
    level_idx = np.select([s >= 4, s >= 3, s >= 2], [3, 2, 1], 0)
    regime = np.where(ind["vol_pctile"] > 0.9, "high_volatility",
                      np.where(ind["trend_200"] > 0.02, "bull_trend",
                               np.where(ind["trend_200"] < -0.02, "bear_trend", "sideways")))
    return pd.DataFrame({"score": s, "level": [LEVELS[i] for i in level_idx], "regime": regime}, index=ind.index)


def evaluate_alarm(levels: pd.Series, index_ret: pd.Series, horizon: int = 20, crash_dd: float = -0.10,
                   alarm_from: str = "High") -> dict:
    """Did High/Critical precede a >=10% drawdown within `horizon` days? Precision/recall on daily obs."""
    lvl = np.exp(index_ret.cumsum())
    fwd_min = lvl[::-1].rolling(horizon, min_periods=1).min()[::-1].shift(-1)
    event = (fwd_min / lvl - 1) <= crash_dd
    alarm = levels.map({l: i for i, l in enumerate(LEVELS)}) >= LEVELS.index(alarm_from)
    m = event.notna() & alarm.notna()
    e, a = event[m].astype(bool), alarm[m].astype(bool)
    tp, fp, fn = int((a & e).sum()), int((a & ~e).sum()), int((~a & e).sum())
    return {"definition": f"index drawdown <= {crash_dd:.0%} within {horizon} days", "alarm_level": alarm_from,
            "days": int(m.sum()), "event_days": int(e.sum()), "alarm_days": int(a.sum()),
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "false_alarm_days": fp, "missed_event_days": fn}
