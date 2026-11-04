"""Job provider adapters. Each returns ``NormalizedJob`` objects with source attribution.

Terms: JSearch (RapidAPI) and Adzuna are licensed aggregators that require API keys and have
their own quota and commercial-use terms; Greenhouse, Lever and Ashby expose *public* job-board
APIs per employer (a board token is required; there is no cross-employer search). Indeed- and
LinkedIn-origin postings are only obtained through JSearch's aggregation (``job_publisher``), never
by scraping those sites.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel

from ..config import get_settings
from .normalize import NormalizedJob, enrich

UA = {"User-Agent": "CareerFloAI/0.1 (+job discovery; contact via app)"}
COUNTRY_CURRENCY = {"ca": "CAD", "us": "USD", "gb": "GBP", "de": "EUR", "fr": "EUR", "au": "AUD", "in": "INR"}


class SearchFilters(BaseModel):
    query: str = ""
    company: str | None = None
    city: str | None = None
    country: str | None = "ca"  # ISO-3166 alpha-2, lower-case
    work_arrangement: str | None = None  # remote | hybrid | onsite
    salary_min: float | None = None
    currency: str | None = None
    seniority: str | None = None
    industry: str | None = None
    skills: list[str] = []
    posted_within_days: int | None = None
    employment_type: str | None = None
    origin: str | None = None  # indeed | linkedin (aggregated-origin searches)
    limit: int = 50


class ProviderNotConfigured(Exception):
    pass


def _dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


async def _get(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float = 15) -> Any:
    async with httpx.AsyncClient(timeout=timeout, headers=UA | (headers or {}), follow_redirects=True) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------- JSearch (incl. Indeed/LinkedIn origin)
def jsearch_to_job(d: dict[str, Any]) -> NormalizedJob | None:
    if not d.get("job_id") or not d.get("job_title"):
        return None
    loc = ", ".join(x for x in [d.get("job_city"), d.get("job_state"), d.get("job_country")] if x) or d.get("job_location")
    period = (d.get("job_salary_period") or "").lower() or None
    has_salary = d.get("job_min_salary") is not None or d.get("job_max_salary") is not None
    return enrich(NormalizedJob(
        source="jsearch", source_job_id=str(d["job_id"]), origin_publisher=d.get("job_publisher"),
        company=d.get("employer_name") or "Unknown employer", title=d["job_title"], location=loc,
        city=d.get("job_city"), country=d.get("job_country"),
        work_arrangement="remote" if d.get("job_is_remote") else None,
        employment_type=d.get("job_employment_type"),
        salary_min=d.get("job_min_salary"), salary_max=d.get("job_max_salary"),
        salary_currency=d.get("job_salary_currency"), salary_period=period, salary_verified=has_salary,
        description=d.get("job_description") or "", posted_at=_dt(d.get("job_posted_at_datetime_utc") or d.get("job_posted_at_timestamp")),
        apply_url=d.get("job_apply_link"), verification_status="aggregator"))


async def search_jsearch(f: SearchFilters) -> list[NormalizedJob]:
    s = get_settings()
    if not s.jsearch_api_key:
        raise ProviderNotConfigured("JSEARCH_API_KEY is not set")
    q = " ".join(x for x in [f.query, f.company, f"in {f.city}" if f.city else None] if x) or "software engineer"
    params: dict[str, Any] = {"query": q, "page": 1, "num_pages": 1, "country": (f.country or "ca").lower()}
    if f.posted_within_days:
        params["date_posted"] = "today" if f.posted_within_days <= 1 else "3days" if f.posted_within_days <= 3 else "week" if f.posted_within_days <= 7 else "month"
    if f.work_arrangement == "remote":
        params["work_from_home"] = "true"
    data = await _get(f"https://{s.jsearch_host}/search", params=params,
                      headers={"X-RapidAPI-Key": s.jsearch_api_key, "X-RapidAPI-Host": s.jsearch_host})
    jobs = [j for j in (jsearch_to_job(d) for d in data.get("data") or []) if j]
    if f.origin:
        jobs = [j for j in jobs if f.origin.lower() in (j.origin_publisher or "").lower()]
    return jobs


# ---------------------------------------------------------------- Adzuna
def adzuna_to_job(d: dict[str, Any], country: str) -> NormalizedJob | None:
    if not d.get("id"):
        return None
    predicted = str(d.get("salary_is_predicted", "0")) == "1"
    loc = (d.get("location") or {}).get("display_name")
    area = (d.get("location") or {}).get("area") or []
    return enrich(NormalizedJob(
        source="adzuna", source_job_id=str(d["id"]), company=(d.get("company") or {}).get("display_name") or "Unknown employer",
        title=d.get("title") or "", location=loc, city=area[-1] if area else None, country=country.upper(),
        employment_type=d.get("contract_time"), industry=(d.get("category") or {}).get("label"),
        # Adzuna "predicted" salaries are estimates, not published figures: never presented as verified.
        salary_min=None if predicted else d.get("salary_min"), salary_max=None if predicted else d.get("salary_max"),
        salary_currency=None if predicted else COUNTRY_CURRENCY.get(country.lower()),
        salary_period=None if predicted else "year", salary_verified=not predicted and d.get("salary_min") is not None,
        description=d.get("description") or "", posted_at=_dt(d.get("created")), apply_url=d.get("redirect_url"),
        verification_status="aggregator"))


async def search_adzuna(f: SearchFilters) -> list[NormalizedJob]:
    s = get_settings()
    if not (s.adzuna_app_id and s.adzuna_app_key):
        raise ProviderNotConfigured("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
    country = (f.country or "ca").lower()
    params: dict[str, Any] = {"app_id": s.adzuna_app_id, "app_key": s.adzuna_app_key, "results_per_page": min(f.limit, 50),
                              "what": f.query or "engineer", "content-type": "application/json"}
    if f.city:
        params["where"] = f.city
    if f.salary_min:
        params["salary_min"] = int(f.salary_min)
    if f.posted_within_days:
        params["max_days_old"] = f.posted_within_days
    if f.company:
        params["company"] = f.company
    data = await _get(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1", params=params)
    return [j for j in (adzuna_to_job(d, country) for d in data.get("results") or []) if j]


# ---------------------------------------------------------------- Employer boards
def greenhouse_to_job(d: dict[str, Any], board: str, company: str | None) -> NormalizedJob:
    import html

    return enrich(NormalizedJob(
        source="greenhouse", source_job_id=f"{board}:{d['id']}", company=d.get("company_name") or company or board,
        title=d.get("title", ""), location=(d.get("location") or {}).get("name"),
        description=html.unescape(d.get("content") or ""), posted_at=_dt(d.get("first_published") or d.get("updated_at")),
        apply_url=d.get("absolute_url"), verification_status="employer_board"))


async def fetch_greenhouse(board: str, company: str | None = None) -> list[NormalizedJob]:
    data = await _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
    return [greenhouse_to_job(d, board, company) for d in data.get("jobs") or []]


def lever_to_job(d: dict[str, Any], site: str, company: str | None) -> NormalizedJob:
    cats = d.get("categories") or {}
    lists = "\n".join(f"{x.get('text', '')}\n{x.get('content', '')}" for x in d.get("lists") or [])
    sal = d.get("salaryRange") or {}
    interval = (sal.get("interval") or "").lower()
    yearly = "year" in interval or "annual" in interval
    return enrich(NormalizedJob(
        source="lever", source_job_id=f"{site}:{d['id']}", company=company or site, title=d.get("text", ""),
        location=cats.get("location"), employment_type=cats.get("commitment"), industry=cats.get("team"),
        work_arrangement={"remote": "remote", "hybrid": "hybrid", "on-site": "onsite"}.get((d.get("workplaceType") or "").lower()),
        salary_min=sal.get("min") if yearly else None, salary_max=sal.get("max") if yearly else None,
        salary_currency=sal.get("currency") if yearly else None, salary_period="year" if yearly else None,
        salary_verified=bool(yearly and sal.get("min")),
        description=f"{d.get('descriptionPlain') or ''}\n{lists}\n{d.get('additionalPlain') or ''}",
        posted_at=_dt(d.get("createdAt")), apply_url=d.get("hostedUrl") or d.get("applyUrl"),
        verification_status="employer_board"))


async def fetch_lever(site: str, company: str | None = None) -> list[NormalizedJob]:
    data = await _get(f"https://api.lever.co/v0/postings/{site}", params={"mode": "json"})
    return [lever_to_job(d, site, company) for d in data or []]


def ashby_to_job(d: dict[str, Any], board: str, company: str | None) -> NormalizedJob:
    smin = smax = cur = None
    for comp in ((d.get("compensation") or {}).get("summaryComponents") or []):
        if comp.get("compensationType") == "Salary" and "YEAR" in (comp.get("interval") or "").upper():
            smin, smax, cur = comp.get("minValue"), comp.get("maxValue"), comp.get("currencyCode")
    wt = (d.get("workplaceType") or "").lower()
    return enrich(NormalizedJob(
        source="ashby", source_job_id=f"{board}:{d['id']}", company=company or board, title=d.get("title", ""),
        location=d.get("location"), employment_type=d.get("employmentType"), industry=d.get("department"),
        work_arrangement="remote" if d.get("isRemote") or wt == "remote" else ("hybrid" if wt == "hybrid" else ("onsite" if wt == "onsite" else None)),
        salary_min=smin, salary_max=smax, salary_currency=cur, salary_period="year" if smin else None,
        salary_verified=smin is not None, description=d.get("descriptionPlain") or d.get("descriptionHtml") or "",
        posted_at=_dt(d.get("publishedAt")), apply_url=d.get("jobUrl") or d.get("applyUrl"),
        verification_status="employer_board"))


async def fetch_ashby(board: str, company: str | None = None) -> list[NormalizedJob]:
    data = await _get(f"https://api.ashbyhq.com/posting-api/job-board/{board}", params={"includeCompensation": "true"})
    return [ashby_to_job(d, board, company) for d in data.get("jobs") or []]


BOARD_FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


async def verify_url(url: str) -> dict[str, Any]:
    """HEAD/GET the apply URL to confirm the posting is still reachable."""
    if not url.startswith(("http://", "https://")):
        return {"url": url, "reachable": False, "reason": "not an http(s) URL"}
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost",) or host.startswith(("127.", "10.", "192.168.", "169.254.")) or host.endswith(".internal"):
        return {"url": url, "reachable": False, "reason": "private address refused"}
    try:
        async with httpx.AsyncClient(timeout=8, headers=UA, follow_redirects=True) as c:
            r = await c.head(url)
            if r.status_code in (405, 403):
                r = await c.get(url)
            return {"url": url, "reachable": r.status_code < 400, "status": r.status_code, "final_url": str(r.url)}
    except httpx.HTTPError as exc:
        return {"url": url, "reachable": False, "reason": type(exc).__name__}


async def gather_safe(coros: dict[str, Any]) -> tuple[dict[str, list[NormalizedJob]], dict[str, str]]:
    names = list(coros)
    results = await asyncio.gather(*coros.values(), return_exceptions=True)
    ok: dict[str, list[NormalizedJob]] = {}
    errors: dict[str, str] = {}
    for name, res in zip(names, results, strict=True):
        if isinstance(res, ProviderNotConfigured):
            errors[name] = f"not configured: {res}"
        elif isinstance(res, Exception):
            errors[name] = f"{type(res).__name__}: {str(res)[:160]}"
        else:
            ok[name] = res
    return ok, errors
