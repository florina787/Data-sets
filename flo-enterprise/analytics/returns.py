"""Return calculations.

Valuation convention: month-end valuations; external cash flows are assumed to occur at the END of the period
in which they are recorded (the synthetic data settles external flows on the month-end date).

* Sub-period return (end-of-period flows):  r_t = (MV_close - F_t) / MV_open - 1
* Time-weighted return (TWR):  TWR = prod(1 + r_t) - 1   (geometric linking; neutralizes flow timing/size)
* Annualized:  (1 + R)^(12 / n_months) - 1   (only when n_months >= 12; otherwise reported un-annualized)
* Money-weighted return (MWR): the IRR solving  sum CF_k / (1 + irr)^(t_k / 365) = 0  with investor-perspective
  signs: opening value and contributions are negative, withdrawals and the closing value are positive.
  Solved by bisection on [-0.99, 10] to 1e-10; returns an annual effective rate.
* Modified Dietz is provided for cross-checks only.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date


def sub_period_return(mv_open: float, flow_end: float, mv_close: float) -> float:
    if mv_open <= 0:
        raise ValueError("opening market value must be positive")
    return (mv_close - flow_end) / mv_open - 1.0


def link(returns: Sequence[float]) -> float:
    acc = 1.0
    for r in returns:
        acc *= 1.0 + r
    return acc - 1.0


def twr(valuations: Sequence[tuple[float, float, float]]) -> float:
    """valuations: sequence of (mv_open, external_flow_at_end, mv_close)."""
    return link([sub_period_return(o, f, c) for o, f, c in valuations])


def annualize(total_return: float, months: int) -> float:
    if months < 12:
        return total_return
    return (1.0 + total_return) ** (12.0 / months) - 1.0


def cumulative_series(returns: Sequence[float]) -> list[float]:
    out, acc = [], 1.0
    for r in returns:
        acc *= 1.0 + r
        out.append(acc - 1.0)
    return out


def _npv(rate: float, flows: Sequence[tuple[date, float]]) -> float:
    t0 = flows[0][0]
    return sum(cf / (1.0 + rate) ** ((d - t0).days / 365.0) for d, cf in flows)


def xirr(flows: Sequence[tuple[date, float]], lo: float = -0.99, hi: float = 10.0, tol: float = 1e-10) -> float:
    flows = sorted(flows, key=lambda x: x[0])
    if not (any(cf < 0 for _, cf in flows) and any(cf > 0 for _, cf in flows)):
        raise ValueError("cash flows must contain both signs")
    f_lo, f_hi = _npv(lo, flows), _npv(hi, flows)
    if f_lo * f_hi > 0:
        raise ValueError("IRR not bracketed")
    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, flows)
        if abs(f_mid) < tol or (hi - lo) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def mwr(start: date, mv_start: float, flows: Sequence[tuple[date, float]], end: date, mv_end: float) -> float:
    """flows: external flows from the portfolio's perspective (+contribution, -withdrawal)."""
    cfs = [(start, -mv_start)] + [(d, -f) for d, f in flows] + [(end, mv_end)]
    return xirr(cfs)


def modified_dietz(mv_start: float, mv_end: float, flows: Sequence[tuple[float, float]]) -> float:
    """flows: (weight_of_period_remaining in [0,1], amount)."""
    net = sum(a for _, a in flows)
    denom = mv_start + sum(w * a for w, a in flows)
    return (mv_end - mv_start - net) / denom


def excess_returns(port: Sequence[float], bench: Sequence[float]) -> list[float]:
    if len(port) != len(bench):
        raise ValueError("series length mismatch")
    return [p - b for p, b in zip(port, bench)]


def relative_cumulative(port: Sequence[float], bench: Sequence[float]) -> list[float]:
    """Geometric relative performance: (1+Rp_cum)/(1+Rb_cum) - 1 per period."""
    cp, cb = cumulative_series(port), cumulative_series(bench)
    return [(1 + a) / (1 + b) - 1 for a, b in zip(cp, cb)]
