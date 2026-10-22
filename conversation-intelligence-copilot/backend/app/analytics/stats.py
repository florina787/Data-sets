"""Small, tested statistical helpers used to express uncertainty honestly."""

from __future__ import annotations

import math

from scipy import stats


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def chi_square_independence(table: list[list[int]]) -> dict:
    """Chi-square test of independence on a contingency table (rows = groups)."""
    rows = [r for r in table if sum(r) > 0]
    if len(rows) < 2 or any(sum(col) == 0 for col in zip(*rows)):
        return {"statistic": None, "p_value": None, "dof": None, "valid": False}
    stat, p, dof, expected = stats.chi2_contingency(rows)
    return {
        "statistic": round(float(stat), 3),
        "p_value": round(float(p), 4),
        "dof": int(dof),
        "valid": bool((expected >= 5).all()),
    }


def two_proportion_test(x1: int, n1: int, x2: int, n2: int) -> dict:
    """Two-sided z-test for a difference in proportions."""
    if min(n1, n2) == 0:
        return {"z": None, "p_value": None}
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": 0.0, "p_value": 1.0}
    z = (p1 - p2) / se
    return {"z": round(z, 3), "p_value": round(float(2 * (1 - stats.norm.cdf(abs(z)))), 4)}


def minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]
