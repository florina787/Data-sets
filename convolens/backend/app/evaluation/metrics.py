"""Plain-Python evaluation metrics: classification (accuracy, P/R/F1, confusion) and ranking (P@k, MRR, nDCG@k).

No metric here invents a score: empty inputs return None, and every report carries its sample size.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict


def classification_report(pairs: list[tuple[str, str]]) -> dict:
    """``pairs`` = [(gold, predicted), ...]. Classes = every label seen in either column ('unknown' included)."""
    n = len(pairs)
    if not n:
        return {"n": 0, "accuracy": None, "per_class": {}, "macro_f1": None, "weighted_f1": None, "confusion": {}}
    labels = sorted({g for g, _ in pairs} | {p for _, p in pairs})
    confusion: dict[str, Counter] = defaultdict(Counter)
    for g, p in pairs:
        confusion[g][p] += 1
    per_class = {}
    for c in labels:
        tp = confusion[c][c]
        fp = sum(confusion[g][c] for g in labels if g != c)
        fn = sum(confusion[c][p] for p in labels if p != c)
        support = tp + fn
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / support if support else None
        f1 = (2 * prec * rec / (prec + rec)) if prec and rec else (0.0 if support or tp + fp else None)
        per_class[c] = {"precision": _r(prec), "recall": _r(rec), "f1": _r(f1), "support": support}
    scored = [v for v in per_class.values() if v["f1"] is not None and v["support"]]
    macro = sum(v["f1"] for v in scored) / len(scored) if scored else None
    total_support = sum(v["support"] for v in scored)
    weighted = sum(v["f1"] * v["support"] for v in scored) / total_support if total_support else None
    return {"n": n, "accuracy": _r(sum(g == p for g, p in pairs) / n), "per_class": per_class,
            "macro_f1": _r(macro), "weighted_f1": _r(weighted),
            "confusion": {g: dict(confusion[g]) for g in labels if confusion[g]}}


def precision_at_k(rels: list[bool], k: int) -> float | None:
    top = rels[:k]
    return sum(top) / len(top) if top else None


def reciprocal_rank(rels: list[bool]) -> float:
    return next((1 / (i + 1) for i, r in enumerate(rels) if r), 0.0)


def ndcg_at_k(rels: list[bool], k: int, total_relevant: int | None = None) -> float | None:
    """Binary-gain nDCG. The ideal ranking uses min(k, total_relevant) relevant items (all known relevant items when
    ``total_relevant`` is given, otherwise only those retrieved, which overstates nDCG and is labelled so by callers)."""
    top = rels[:k]
    if not top:
        return None
    dcg = sum(1 / math.log2(i + 2) for i, r in enumerate(top) if r)
    ideal_n = min(k, total_relevant if total_relevant is not None else sum(top))
    idcg = sum(1 / math.log2(i + 2) for i in range(ideal_n))
    return dcg / idcg if idcg else 0.0


def ranking_report(runs: list[list[bool]], k: int = 5, total_relevant: list[int] | None = None) -> dict:
    """``runs`` = one relevance list (in rank order) per query."""
    if not runs:
        return {"queries": 0}
    p = [precision_at_k(r, k) for r in runs]
    nd = [ndcg_at_k(r, k, total_relevant[i] if total_relevant else None) for i, r in enumerate(runs)]
    hits = sum(len(r[:k]) for r in runs)
    irrelevant = sum(1 for r in runs for x in r[:k] if not x)
    rec = None
    if total_relevant:
        rec = _mean([sum(r[:k]) / t for r, t in zip(runs, total_relevant) if t])
    return {"queries": len(runs), f"precision@{k}": _r(_mean([x for x in p if x is not None])),
            f"recall@{k}": _r(rec), "mrr": _r(_mean([reciprocal_rank(r) for r in runs])),
            f"ndcg@{k}": _r(_mean([x for x in nd if x is not None])),
            "irrelevant_evidence_rate": _r(irrelevant / hits) if hits else None, "hits_judged": hits}


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)
