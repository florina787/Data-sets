"""Performance and forecast metrics. Accuracy is never reported alone."""
from __future__ import annotations

import numpy as np
import pandas as pd


def perf_stats(returns: pd.Series, periods_per_year: float) -> dict:
    r = returns.dropna()
    if len(r) < 2:
        return {"n_periods": int(len(r))}
    eq = (1 + r).cumprod()
    years = len(r) / periods_per_year
    dd = eq / eq.cummax() - 1
    down = r[r < 0]
    wins, losses = r[r > 0], r[r < 0]
    return {
        "n_periods": int(len(r)),
        "total_return": float(eq.iloc[-1] - 1),
        "cagr": float(eq.iloc[-1] ** (1 / years) - 1) if eq.iloc[-1] > 0 else -1.0,
        "volatility": float(r.std() * np.sqrt(periods_per_year)),
        "sharpe": float(r.mean() / r.std() * np.sqrt(periods_per_year)) if r.std() > 0 else 0.0,
        "sortino": float(r.mean() / down.std() * np.sqrt(periods_per_year)) if len(down) > 1 and down.std() > 0 else None,
        "max_drawdown": float(dd.min()),
        "win_rate": float((r > 0).mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else None,
        "expectancy": float(r.mean()),
    }


def information_coefficient(pred: pd.Series, actual: pd.Series, dates: pd.Series) -> dict:
    """Mean per-date Spearman rank correlation and its t-stat (dates are the unit of evidence)."""
    df = pd.DataFrame({"p": pred.values, "a": actual.values, "d": dates.values}).dropna()
    ics = df.groupby("d").apply(lambda g: g["p"].rank().corr(g["a"].rank()) if len(g) > 5 else np.nan,
                                include_groups=False).dropna()
    if len(ics) < 2:
        return {"ic_mean": None, "ic_t": None, "n_dates": int(len(ics))}
    return {"ic_mean": float(ics.mean()), "ic_std": float(ics.std()),
            "ic_t": float(ics.mean() / ics.std() * np.sqrt(len(ics))), "n_dates": int(len(ics)),
            "ic_positive_frac": float((ics > 0).mean())}


def directional_accuracy(pred: pd.Series, actual: pd.Series) -> float:
    m = pred.notna() & actual.notna() & (actual != 0)
    return float((np.sign(pred[m]) == np.sign(actual[m])).mean())


def brier(prob: np.ndarray, outcome: np.ndarray) -> float:
    return float(np.mean((np.asarray(prob) - np.asarray(outcome)) ** 2))


def calibration(prob: np.ndarray, outcome: np.ndarray, bins: int = 10) -> dict:
    """Expected calibration error plus the reliability table."""
    prob, outcome = np.asarray(prob, float), np.asarray(outcome, float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(prob, edges) - 1, 0, bins - 1)
    table, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            conf, acc = prob[m].mean(), outcome[m].mean()
            ece += m.mean() * abs(conf - acc)
            table.append({"bin": b, "n": int(m.sum()), "mean_prob": float(conf), "freq": float(acc)})
    return {"ece": float(ece), "table": table}
