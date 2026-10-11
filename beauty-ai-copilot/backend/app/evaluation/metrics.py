"""Deterministic metric computation (NumPy). No language model participates here.

Conventions
* Abstentions stay in the denominator: top-1/top-3 accuracy = correct / eligible samples.
* coverage = answered / eligible; conditional accuracy = correct / answered (reported separately).
* Deltas are percentage points (pp): candidate% − baseline%. Relative change is reported separately
  and labelled as such.
* Uncertainty: Wilson 95% intervals for proportions; paired percentile bootstrap for cell deltas.
"""
from __future__ import annotations

import math

import numpy as np

FAMILY_BY_ORDINAL = {**{i: "Light" for i in range(1, 11)}, **{i: "Medium" for i in range(11, 21)},
                     **{i: "Tan" for i in range(21, 31)}, **{i: "Deep" for i in range(31, 41)}}
FAMILIES = ["Light", "Medium", "Tan", "Deep"]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half) * 100, 2), round(min(1.0, centre + half) * 100, 2)


def indicators(expected: list[str], preds: list[dict]) -> dict[str, np.ndarray]:
    top1 = np.array([(not p["abstained"]) and p["top3"][0] == e for e, p in zip(expected, preds)], dtype=bool)
    top3 = np.array([(not p["abstained"]) and e in p["top3"] for e, p in zip(expected, preds)], dtype=bool)
    answered = np.array([not p["abstained"] for p in preds], dtype=bool)
    return {"top1": top1, "top3": top3, "answered": answered}


def summarize(ind: dict[str, np.ndarray]) -> dict:
    n = int(ind["top1"].size)
    k1, k3, ans = int(ind["top1"].sum()), int(ind["top3"].sum()), int(ind["answered"].sum())
    pct = lambda a, b: round(100 * a / b, 2) if b else None  # noqa: E731
    return {
        "n_eligible": n, "top1_correct": k1, "top3_correct": k3, "answered": ans, "abstained": n - ans,
        "top1_accuracy_pct": pct(k1, n), "top1_wilson95": wilson(k1, n),
        "top3_accuracy_pct": pct(k3, n), "top3_wilson95": wilson(k3, n),
        "coverage_pct": pct(ans, n), "abstention_rate_pct": pct(n - ans, n),
        "conditional_top1_accuracy_pct": pct(k1, ans),
    }


def paired_bootstrap_delta(base: np.ndarray, cand: np.ndarray, resamples: int, seed: int, confidence: float) -> tuple[float | None, float | None]:
    """Percentile CI of (cand − base) top-1 accuracy in pp, resampling matched sample IDs."""
    n = base.size
    if n == 0:
        return None, None
    rng = np.random.default_rng(seed)
    diff = cand.astype(np.int8) - base.astype(np.int8)
    idx = rng.integers(0, n, size=(resamples, n))
    deltas = diff[idx].mean(axis=1) * 100
    lo, hi = np.percentile(deltas, [(1 - confidence) / 2 * 100, (1 + confidence) / 2 * 100])
    return round(float(lo), 2), round(float(hi), 2)


def delta(base: dict, cand: dict) -> dict:
    def d(key):
        a, b = base.get(key), cand.get(key)
        return None if a is None or b is None else round(b - a, 2)
    rel = None
    if base["top1_accuracy_pct"]:
        rel = round((cand["top1_accuracy_pct"] - base["top1_accuracy_pct"]) / base["top1_accuracy_pct"] * 100, 2)
    return {
        "top1_delta_pp": d("top1_accuracy_pct"), "top3_delta_pp": d("top3_accuracy_pct"),
        "coverage_delta_pp": d("coverage_pct"), "conditional_top1_delta_pp": d("conditional_top1_accuracy_pct"),
        "top1_relative_change_pct": rel,
    }


def family_confusion(expected: list[str], preds: list[dict]) -> dict:
    """Confusion at shade-FAMILY level (rows = reference family, cols = predicted family or ABSTAIN).
    Shade IDs are catalogue identifiers; this is not a colour-difference metric."""
    cols = FAMILIES + ["ABSTAIN"]
    m = {r: {c: 0 for c in cols} for r in FAMILIES}
    for e, p in zip(expected, preds):
        r = FAMILY_BY_ORDINAL[int(e[3:])]
        c = "ABSTAIN" if p["abstained"] else FAMILY_BY_ORDINAL[int(p["top3"][0][3:])]
        m[r][c] += 1
    return {"rows": FAMILIES, "cols": cols, "counts": m}
