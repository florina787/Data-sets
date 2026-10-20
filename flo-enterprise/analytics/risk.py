"""Risk and concentration statistics (float estimates; monthly data, 12 periods per year).

* Volatility (annualized): sample standard deviation (n-1) of periodic returns * sqrt(12)
* Sharpe ratio: mean(r - rf) * 12 / (stdev(r - rf) * sqrt(12)); rf is the periodic risk-free return series
  (synthetic T-bill index). Returns None when stdev is zero or fewer than 3 observations.
* Maximum drawdown: min over t of (W_t / max_{s<=t} W_s - 1), W = cumulative wealth index starting at 1.
* Tracking error: stdev(r_p - r_b) * sqrt(12); Information ratio: mean(r_p - r_b) * 12 / tracking error.
* Beta: cov(r_p, r_b) / var(r_b).
* Concentration: Herfindahl-Hirschman index HHI = sum w_i^2; effective number of holdings = 1 / HHI.
* Allocation drift: per-asset (current - target); total drift = 0.5 * sum |current - target| (one-way turnover
  needed to rebalance).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

PPY = 12


def mean(x: Sequence[float]) -> float:
    return sum(x) / len(x)


def stdev(x: Sequence[float]) -> float:
    if len(x) < 2:
        raise ValueError("need at least two observations")
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def volatility(returns: Sequence[float], ppy: int = PPY) -> float:
    return stdev(returns) * math.sqrt(ppy)


def sharpe(returns: Sequence[float], rf: Sequence[float], ppy: int = PPY) -> float | None:
    if len(returns) < 3:
        return None
    ex = [r - f for r, f in zip(returns, rf, strict=True)]
    sd = stdev(ex)
    if sd == 0:
        return None
    return mean(ex) * ppy / (sd * math.sqrt(ppy))


def wealth_index(returns: Sequence[float]) -> list[float]:
    w, out = 1.0, []
    for r in returns:
        w *= 1 + r
        out.append(w)
    return out


def drawdown_series(returns: Sequence[float]) -> list[float]:
    peak, out = 1.0, []
    for w in wealth_index(returns):
        peak = max(peak, w)
        out.append(w / peak - 1)
    return out


def max_drawdown(returns: Sequence[float]) -> dict:
    dd = drawdown_series(returns)
    trough = min(range(len(dd)), key=lambda i: dd[i]) if dd else 0
    w = wealth_index(returns)
    peak_idx = -1
    peak_val = 1.0
    for i in range(trough + 1):
        if w[i] >= peak_val:
            peak_val, peak_idx = w[i], i
    recovery = next((i for i in range(trough + 1, len(w)) if w[i] >= peak_val), None)
    return {"max_drawdown": min(dd) if dd else 0.0, "peak_index": peak_idx, "trough_index": trough,
            "recovery_index": recovery}


def tracking_error(port: Sequence[float], bench: Sequence[float], ppy: int = PPY) -> float:
    return stdev([p - b for p, b in zip(port, bench, strict=True)]) * math.sqrt(ppy)


def information_ratio(port: Sequence[float], bench: Sequence[float], ppy: int = PPY) -> float | None:
    te = tracking_error(port, bench, ppy)
    if te == 0:
        return None
    return mean([p - b for p, b in zip(port, bench)]) * ppy / te


def beta(port: Sequence[float], bench: Sequence[float]) -> float:
    mp, mb = mean(port), mean(bench)
    cov = sum((p - mp) * (b - mb) for p, b in zip(port, bench, strict=True)) / (len(port) - 1)
    var = sum((b - mb) ** 2 for b in bench) / (len(bench) - 1)
    return cov / var


def correlation(x: Sequence[float], y: Sequence[float]) -> float:
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


def correlation_matrix(series: Mapping[str, Sequence[float]]) -> dict:
    keys = list(series)
    return {"labels": keys, "matrix": [[round(correlation(series[a], series[b]), 4) for b in keys] for a in keys]}


def hhi(weights: Sequence[float]) -> float:
    tot = sum(weights)
    if tot <= 0:
        raise ValueError("weights must sum to a positive value")
    return sum((w / tot) ** 2 for w in weights)


def effective_n(weights: Sequence[float]) -> float:
    return 1.0 / hhi(weights)


def top_n_weight(weights: Sequence[float], n: int = 5) -> float:
    tot = sum(weights)
    return sum(sorted((w / tot for w in weights), reverse=True)[:n])


def limit_breaches(weights: Mapping[str, float], limit: float) -> list[dict]:
    return [{"id": k, "weight": w, "excess": w - limit} for k, w in sorted(weights.items(), key=lambda kv: -kv[1])
            if w > limit]


def allocation_drift(target: Mapping[str, float], current: Mapping[str, float]) -> dict:
    keys = sorted(set(target) | set(current))
    per = {k: current.get(k, 0.0) - target.get(k, 0.0) for k in keys}
    return {"per_asset": per, "total_drift": 0.5 * sum(abs(v) for v in per.values()),
            "max_abs_drift": max((abs(v) for v in per.values()), default=0.0)}
