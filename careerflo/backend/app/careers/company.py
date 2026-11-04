"""Company research from verifiable sources: our stored postings and the Wikipedia REST API."""
from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import quote

import httpx

from ..security.sanitize import neutralize

WIKI = "https://en.wikipedia.org/api/rest_v1/page/summary/"


async def wikipedia_summary(name: str) -> dict[str, Any] | None:
    clean = name.replace("(Demo)", "").strip()
    if not clean:
        return None
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "CareerFloAI/0.1 (company research)"}) as c:
            r = await c.get(WIKI + quote(clean.replace(" ", "_")))
            if r.status_code != 200:
                return None
            d = r.json()
            if d.get("type") == "disambiguation":
                return None
            text, flags = neutralize(d.get("extract") or "", 2000)
            return {"title": d.get("title"), "extract": text, "url": (d.get("content_urls") or {}).get("desktop", {}).get("page"),
                    "injection_flags": flags}
    except httpx.HTTPError:
        return None


def summarize_postings(company: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    mine = [j for j in jobs if company.lower() in (j.get("company") or "").lower()]
    skills = Counter(s for j in mine for s in (j.get("required_skills") or []) + (j.get("preferred_skills") or []))
    locs = Counter((j.get("city") or j.get("location") or "Unknown") for j in mine)
    arrangements = Counter(j.get("work_arrangement") or "unspecified" for j in mine)
    salaries = [(j.get("salary_min"), j.get("salary_max"), j.get("salary_currency")) for j in mine if j.get("salary_verified")]
    return {"company": company, "open_roles": len(mine), "titles": sorted({j["title"] for j in mine})[:20],
            "top_skills": skills.most_common(12), "locations": locs.most_common(8), "work_arrangements": dict(arrangements),
            "published_salary_ranges": salaries[:10], "is_synthetic": any(j.get("is_synthetic") for j in mine),
            "sources": sorted({f"{j.get('source')}: {j.get('apply_url')}" for j in mine if j.get("apply_url")})[:10]}


async def research_company(company: str, jobs: list[dict[str, Any]], use_web: bool = True) -> dict[str, Any]:
    postings = summarize_postings(company, jobs)
    wiki = await wikipedia_summary(company) if use_web else None
    citations = []
    if wiki and wiki.get("url"):
        citations.append({"label": f"Wikipedia — {wiki['title']}", "url": wiki["url"]})
    citations += [{"label": s.split(":", 1)[0] + " posting", "url": s.split(": ", 1)[1]} for s in postings["sources"][:5]]
    culture_signals = []
    descs = " ".join((j.get("description_snippet") or "") for j in jobs if company.lower() in (j.get("company") or "").lower()).lower()
    for cue, label in [("remote", "Offers remote work"), ("hybrid", "Hybrid work model"), ("mentor", "Mentorship mentioned"),
                       ("learning", "Learning budget / growth mentioned"), ("customer", "Customer-facing emphasis"),
                       ("diversity", "Diversity & inclusion statement"), ("on-call", "On-call duties mentioned")]:
        if cue in descs:
            culture_signals.append(label)
    return {"company": company, "overview": wiki, "hiring": postings, "culture_signals": culture_signals,
            "citations": citations,
            "note": "Facts come only from the cited sources. Culture signals are keyword cues in postings, not employee reviews."}


def compare_companies(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"company": r["company"], "open_roles": r["hiring"]["open_roles"],
             "top_skills": [s for s, _ in r["hiring"]["top_skills"][:5]],
             "remote_share": round(r["hiring"]["work_arrangements"].get("remote", 0) / max(1, r["hiring"]["open_roles"]), 2),
             "has_overview": bool(r.get("overview"))} for r in reports]
