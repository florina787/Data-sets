"""Salary intelligence from *published* salaries only. No estimates are presented as data."""
from __future__ import annotations

import statistics
from typing import Any


def _pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def salary_distribution(jobs: list[dict[str, Any]], currency: str | None = None) -> dict[str, Any]:
    pts = []
    for j in jobs:
        if not j.get("salary_verified") or (j.get("salary_period") not in (None, "year")):
            continue
        if currency and (j.get("salary_currency") or "").upper() != currency.upper():
            continue
        lo, hi = j.get("salary_min"), j.get("salary_max")
        mid = (lo + hi) / 2 if lo and hi else (lo or hi)
        if mid:
            pts.append({"mid": mid, "min": lo, "max": hi, "title": j.get("title"), "company": j.get("company"),
                        "source": j.get("source"), "is_synthetic": j.get("is_synthetic", False)})
    mids = [p["mid"] for p in pts]
    if not mids:
        return {"count": 0, "currency": currency, "message": "No published salaries match these filters."}
    lo_b = int(min(mids) // 10000 * 10000)
    hi_b = int(max(mids) // 10000 * 10000) + 10000
    buckets = [{"range": f"{b // 1000}k–{(b + 10000) // 1000}k", "count": sum(1 for m in mids if b <= m < b + 10000)}
               for b in range(lo_b, hi_b, 10000)]
    return {"count": len(mids), "currency": currency or (jobs[0].get("salary_currency") if jobs else None),
            "p25": round(_pct(mids, .25)), "p50": round(_pct(mids, .5)), "p75": round(_pct(mids, .75)),
            "p90": round(_pct(mids, .9)), "mean": round(statistics.mean(mids)), "histogram": buckets,
            "samples": pts[:50], "synthetic_share": round(sum(p["is_synthetic"] for p in pts) / len(pts), 2)}


def negotiation_scenarios(offer: float, dist: dict[str, Any], target: float | None = None) -> dict[str, Any]:
    if not dist.get("count"):
        return {"message": "Not enough published salary data to benchmark this offer."}
    p50, p75, p90 = dist["p50"], dist["p75"], dist["p90"]
    position = "below median" if offer < p50 else "between median and 75th percentile" if offer < p75 else "above 75th percentile"
    anchor = round(max(offer * 1.08, min(p75, offer * 1.15)), -3)
    return {
        "offer": offer, "position": position, "market": {"p50": p50, "p75": p75, "p90": p90, "n": dist["count"]},
        "scenarios": [
            {"name": "Conservative", "ask": round(offer * 1.05, -3), "rationale": "Small ask focused on closing quickly."},
            {"name": "Market-anchored", "ask": anchor, "rationale": f"Anchors toward the published 75th percentile ({p75:,})."},
            {"name": "Ambitious", "ask": round(max(anchor, min(p90, offer * 1.25)), -3), "rationale": "Use only with competing offers or rare skills."},
        ] + ([{"name": "Your target", "ask": target, "rationale": "Your stated target."}] if target else []),
        "tips": ["Negotiate total compensation (base, bonus, equity, signing, PTO, learning budget).",
                 "Quote published ranges and your verified impact, not personal needs.",
                 "Get the final offer in writing."],
        "disclaimer": f"Benchmarks come from {dist['count']} published salaries in your search results; they are not a guarantee of any employer's pay.",
    }
