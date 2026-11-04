"""Explainable, deterministic job matching (no LLM needed)."""
from __future__ import annotations

from typing import Any

SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "lead", "staff", "principal", "manager", "director"]
YEARS_FOR_LEVEL = {"intern": 0, "junior": 0, "mid": 2, "senior": 5, "lead": 6, "staff": 8, "principal": 10,
                   "manager": 6, "director": 10}

METHODOLOGY = (
    "Score = weighted average of: required-skill coverage (55%), preferred-skill coverage (15%), "
    "seniority fit from your verified years of experience (10%), location / work-arrangement fit (10%) and "
    "published-salary fit against your target (10%). Components with no data (e.g. no published salary) are "
    "left out and the remaining weights are re-normalised. Only skills found in your resume or added to your "
    "profile count as verified.")


def match_job(candidate: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """candidate: {skills: [...], years_experience: float|None, location: str|None, target_salary_min, target_currency,
    preferred_arrangement}; job: normalised job dict."""
    cskills = {s.lower(): s for s in candidate.get("skills") or []}
    req = job.get("required_skills") or []
    pref = job.get("preferred_skills") or []
    req_hit = [s for s in req if s.lower() in cskills]
    pref_hit = [s for s in pref if s.lower() in cskills]
    comps: dict[str, tuple[float, float, str]] = {}
    if req:
        comps["required_skills"] = (len(req_hit) / len(req), 0.55, f"{len(req_hit)}/{len(req)} required skills verified")
    if pref:
        comps["preferred_skills"] = (len(pref_hit) / len(pref), 0.15, f"{len(pref_hit)}/{len(pref)} preferred skills")
    yrs = candidate.get("years_experience")
    level = (job.get("seniority") or "mid").lower()
    if yrs is not None:
        need = YEARS_FOR_LEVEL.get(level, 2)
        fit = 1.0 if yrs >= need else max(0.0, yrs / need) if need else 1.0
        if yrs > need + 8 and level in ("junior", "intern"):
            fit = 0.6
        comps["seniority"] = (fit, 0.10, f"{yrs:.1f} verified years vs ~{need}+ typical for {level}")
    loc = (candidate.get("location") or "").lower().split(",")[0].strip()
    arrangement = job.get("work_arrangement")
    if loc or candidate.get("preferred_arrangement"):
        jloc = f"{job.get('city') or ''} {job.get('location') or ''}".lower()
        if arrangement == "remote":
            lf, why = 1.0, "remote role"
        elif loc and loc in jloc:
            lf, why = 1.0, f"located in {loc.title()}"
        else:
            lf, why = 0.3, "different city (relocation or commute needed)"
        pa = candidate.get("preferred_arrangement")
        if pa and arrangement and pa != arrangement:
            lf, why = lf * 0.6, why + f"; {arrangement} vs preferred {pa}"
        comps["location"] = (lf, 0.10, why)
    target = candidate.get("target_salary_min")
    top = job.get("salary_max") or job.get("salary_min")
    if target and top and job.get("salary_verified"):
        same_cur = not candidate.get("target_currency") or not job.get("salary_currency") or \
            candidate["target_currency"].upper() == job["salary_currency"].upper()
        if same_cur:
            comps["salary"] = (min(1.0, top / target), 0.10,
                               f"published up to {job.get('salary_currency') or ''} {top:,.0f} vs target {target:,.0f}")
    total_w = sum(w for _, w, _ in comps.values()) or 1.0
    score = round(100 * sum(v * w for v, w, _ in comps.values()) / total_w, 1)
    missing = [s for s in req if s.lower() not in cskills]
    return {
        "score": score,
        "grade": "excellent" if score >= 80 else "strong" if score >= 65 else "partial" if score >= 45 else "weak",
        "components": {k: {"score": round(v * 100, 1), "weight": w, "explanation": e} for k, (v, w, e) in comps.items()},
        "matched_required": req_hit, "matched_preferred": pref_hit, "missing_required": missing,
        "missing_preferred": [s for s in pref if s.lower() not in cskills],
        "methodology": METHODOLOGY,
    }


def rank_jobs(candidate: dict[str, Any], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for j in jobs:
        m = match_job(candidate, j)
        ranked.append({"job": j, "match": m})
    ranked.sort(key=lambda x: x["match"]["score"], reverse=True)
    return ranked
