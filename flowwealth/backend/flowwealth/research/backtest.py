"""Cross-sectional long/short and long-only backtests with costs and liquidity limits.

Rebalances every ``horizon`` bars on non-overlapping windows, so each period's
return is realised before the next decision. Signals at date t are formed from
data available at t's close; trades are assumed filled at that close plus costs
(execution-delay cost is in ``slippage_bps``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .costs import CostModel
from .metrics import perf_stats


@dataclass
class BacktestResult:
    gross: pd.Series
    net: pd.Series
    turnover: pd.Series
    stats_gross: dict
    stats_net: dict

    def summary(self) -> dict:
        return {"gross": self.stats_gross, "net": self.stats_net,
                "avg_turnover": float(self.turnover.mean()), "cost_drag_total": float(self.gross.sum() - self.net.sum())}


def run_backtest(frame: pd.DataFrame, signal_col: str, ret_col: str, horizon: int,
                 quantile: float = 0.1, long_only: bool = False, capital: float = 1e7,
                 costs: CostModel = CostModel()) -> BacktestResult:
    """frame: ticker, ts, <signal_col>, <ret_col> (log fwd return over horizon), adv_usd, vol_20."""
    df = frame.dropna(subset=[signal_col, ret_col]).copy()
    df["date"] = df["ts"].dt.normalize()
    dates = np.sort(df["date"].unique())[::horizon]
    prev_w = pd.Series(dtype=float)
    gross, net, turn = {}, {}, {}
    for d in dates:
        g = df[df["date"] == d].set_index("ticker")
        if len(g) < 20:
            continue
        q_hi = g[signal_col].quantile(1 - quantile)
        q_lo = g[signal_col].quantile(quantile)
        longs = g.index[g[signal_col] >= q_hi]
        shorts = g.index[g[signal_col] <= q_lo] if not long_only else []
        w = pd.Series(0.0, index=g.index)
        w[longs] = (1.0 if long_only else 0.5) / max(len(longs), 1)
        if len(shorts):
            w[shorts] = -0.5 / len(shorts)
        # liquidity cap: position notional <= max_participation * ADV
        if "adv_usd" in g:
            cap = costs.max_participation * g["adv_usd"] / capital
            w = np.sign(w) * np.minimum(w.abs(), cap.fillna(0))
        simple = np.expm1(g[ret_col])
        period_gross = float((w * simple).sum())
        idx = w.index.union(prev_w.index)
        dw = w.reindex(idx, fill_value=0.0) - prev_w.reindex(idx, fill_value=0.0)  # exits included
        adv = g["adv_usd"].reindex(idx) if "adv_usd" in g else pd.Series(np.nan, index=idx)
        part = (dw.abs() * capital / adv).fillna(0.01)
        vm = (g["vol_20"].reindex(idx) / g["vol_20"].median()).clip(0.5, 4).fillna(1) if "vol_20" in g else 1.0
        cost = float((dw.abs() * costs.per_side_bps(part, vm)).sum()) / 1e4
        cost += float(w[w < 0].abs().sum()) * costs.borrow_bps(horizon) / 1e4
        gross[d], net[d], turn[d] = period_gross, period_gross - cost, float(dw.abs().sum())
        # drift weights by realised returns before next rebalance
        prev_w = w * (1 + simple) / (1 + period_gross)
    ppy = 252 / horizon
    g_s, n_s = pd.Series(gross), pd.Series(net)
    return BacktestResult(g_s, n_s, pd.Series(turn), perf_stats(g_s, ppy), perf_stats(n_s, ppy))
