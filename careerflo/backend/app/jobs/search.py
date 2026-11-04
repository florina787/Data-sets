"""Job discovery orchestration: provider fan-out, quotas, caching, persistence, dedupe and filters."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import EmployerBoard, Job, ProviderUsage, SearchCache, utcnow
from . import providers as P
from .normalize import NormalizedJob, deduplicate, to_dict
from .synthetic import synthetic_jobs

SOURCES = {
    "jsearch": {"name": "JSearch (RapidAPI) — Google for Jobs aggregation incl. LinkedIn/Indeed origin", "kind": "aggregator",
                "terms_url": "https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch"},
    "adzuna": {"name": "Adzuna", "kind": "aggregator", "terms_url": "https://developer.adzuna.com/docs/terms_of_service"},
    "greenhouse": {"name": "Greenhouse Job Board API", "kind": "ats_board", "terms_url": "https://developers.greenhouse.io/job-board.html"},
    "lever": {"name": "Lever Postings API", "kind": "ats_board", "terms_url": "https://github.com/lever/postings-api"},
    "ashby": {"name": "Ashby Job Posting API", "kind": "ats_board", "terms_url": "https://developers.ashbyhq.com/docs/public-job-posting-api"},
    "synthetic": {"name": "Synthetic demo data", "kind": "synthetic", "terms_url": None},
}


def _ins(db: Session):
    return pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert


def take_quota(db: Session, source: str) -> bool:
    """Atomically count one request against the provider's daily quota."""
    if source == "synthetic":
        return True
    day = utcnow().strftime("%Y-%m-%d")
    quota = get_settings().provider_daily_quota
    db.execute(_ins(db)(ProviderUsage).values(source_id=source, day=day, requests=0).on_conflict_do_nothing())
    res = db.execute(update(ProviderUsage).where(ProviderUsage.source_id == source, ProviderUsage.day == day,
                                                 ProviderUsage.requests < quota).values(requests=ProviderUsage.requests + 1))
    db.commit()
    return res.rowcount == 1


def cache_key(source: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((source + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()


def upsert_jobs(db: Session, jobs: list[NormalizedJob]) -> list[Job]:
    rows: list[Job] = []
    for j in jobs:
        existing = db.scalar(select(Job).where(Job.source == j.source, Job.source_job_id == j.source_job_id))
        data = j.model_dump()
        data["dedupe_key"] = j.dedupe_key
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            rows.append(existing)
        else:
            row = Job(**data)
            db.add(row)
            rows.append(row)
    db.commit()
    return rows


async def _provider_jobs(db: Session, source: str, f: P.SearchFilters, board: tuple[str, str | None] | None = None
                         ) -> tuple[list[Job], str]:
    payload = f.model_dump(exclude={"limit"}) if board is None else {"board": board[0]}
    key = cache_key(source, payload)
    now = utcnow()
    cached = db.get(SearchCache, key)
    if cached is not None:
        exp = cached.expires_at if cached.expires_at.tzinfo else cached.expires_at.replace(tzinfo=timezone.utc)
        if exp > now:
            ids = cached.job_ids
            import uuid as _u

            jobs = db.scalars(select(Job).where(Job.id.in_([_u.UUID(i) for i in ids]))).all() if ids else []
            return list(jobs), "cached"
    if not take_quota(db, source):
        return [], "quota_exhausted"
    if source == "jsearch":
        normalized = await P.search_jsearch(f)
    elif source == "adzuna":
        normalized = await P.search_adzuna(f)
    elif source in P.BOARD_FETCHERS and board:
        normalized = await P.BOARD_FETCHERS[source](board[0], board[1])
    elif source == "synthetic":
        normalized = synthetic_jobs()
    else:
        return [], "unknown"
    rows = upsert_jobs(db, normalized)
    ttl = get_settings().job_cache_ttl_seconds
    db.merge(SearchCache(key=key, source_id=source, job_ids=[str(r.id) for r in rows],
                         expires_at=now + timedelta(seconds=ttl)))
    db.commit()
    return rows, "live" if source != "synthetic" else "synthetic"


def apply_filters(jobs: list[Job], f: P.SearchFilters) -> tuple[list[Job], dict[str, int]]:
    stats = {"excluded_no_salary": 0, "excluded_currency": 0}
    out = []
    q_words = [w for w in (f.query or "").lower().replace(",", " ").split() if len(w) > 2 and w not in {"jobs", "job", "the", "and", "for", "with", "role", "roles"}]
    now = datetime.now(timezone.utc)
    for j in jobs:
        hay = f"{j.title} {j.company}".lower()
        if q_words and not all(w in hay for w in q_words if w not in {"senior", "junior", "staff", "principal", "lead"}):
            continue
        if f.company and f.company.lower() not in j.company.lower():
            continue
        if f.city and f.city.lower() not in f"{j.city or ''} {j.location or ''}".lower() and j.work_arrangement != "remote":
            continue
        if f.country and j.country and len(j.country) == 2 and j.country.lower() != f.country.lower() and j.work_arrangement != "remote":
            continue
        if f.work_arrangement and j.work_arrangement != f.work_arrangement:
            continue
        if f.seniority and (j.seniority or "") != f.seniority.lower():
            continue
        if f.industry and f.industry.lower() not in (j.industry or "").lower():
            continue
        if f.employment_type and f.employment_type.lower().replace("-", "") not in (j.employment_type or "").lower().replace("-", ""):
            continue
        if f.skills:
            js = {s.lower() for s in (j.required_skills or []) + (j.preferred_skills or [])}
            if not all(s.lower() in js for s in f.skills):
                continue
        if f.posted_within_days and j.posted_at:
            pa = j.posted_at if j.posted_at.tzinfo else j.posted_at.replace(tzinfo=timezone.utc)
            if pa < now - timedelta(days=f.posted_within_days):
                continue
        if f.salary_min:
            top = j.salary_max or j.salary_min
            if top is None or not j.salary_verified:
                stats["excluded_no_salary"] += 1
                continue
            if f.currency and j.salary_currency and j.salary_currency.upper() != f.currency.upper():
                stats["excluded_currency"] += 1  # no FX conversion: we never invent converted salaries
                continue
            if top < f.salary_min:
                continue
        out.append(j)
    return out, stats


def configured_sources() -> dict[str, bool]:
    s = get_settings()
    return {"jsearch": bool(s.jsearch_api_key), "adzuna": bool(s.adzuna_app_id and s.adzuna_app_key),
            "greenhouse": True, "lever": True, "ashby": True, "synthetic": s.enable_synthetic_jobs}


async def search_jobs(db: Session, f: P.SearchFilters, *, include_synthetic: bool | None = None) -> dict[str, Any]:
    conf = configured_sources()
    status: dict[str, str] = {}
    collected: list[Job] = []
    plan: list[tuple[str, tuple[str, str | None] | None]] = []
    if f.origin:
        plan.append(("jsearch", None))
    else:
        plan += [("jsearch", None), ("adzuna", None)]
        boards = db.scalars(select(EmployerBoard)).all()
        for b in boards:
            if not f.company or f.company.lower() in b.company_name.lower():
                plan.append((b.source_id, (b.board_token, b.company_name)))
        if include_synthetic if include_synthetic is not None else conf["synthetic"]:
            plan.append(("synthetic", None))
    for source, board in plan:
        label = source if board is None else f"{source}:{board[0]}"
        if not conf.get(source, False):
            status[label] = "not_configured"
            continue
        try:
            rows, st = await _provider_jobs(db, source, f, board)
            collected.extend(rows)
            status[label] = st
        except P.ProviderNotConfigured:
            status[label] = "not_configured"
        except Exception as exc:  # noqa: BLE001 - one provider failing must not fail the search
            db.rollback()
            status[label] = f"error: {type(exc).__name__}"
    # cross-provider dedupe on stored rows
    best: dict[str, Job] = {}
    prio = {"greenhouse": 0, "lever": 0, "ashby": 0, "jsearch": 1, "adzuna": 2, "synthetic": 5}
    for j in collected:
        cur = best.get(j.dedupe_key)
        if cur is None or (prio.get(j.source, 3), j.salary_min is None) < (prio.get(cur.source, 3), cur.salary_min is None):
            best[j.dedupe_key] = j
    filtered, stats = apply_filters(list(best.values()), f)
    filtered.sort(key=lambda j: (j.posted_at or datetime(1970, 1, 1, tzinfo=timezone.utc)).timestamp() if (j.posted_at and j.posted_at.tzinfo) else (j.posted_at.replace(tzinfo=timezone.utc).timestamp() if j.posted_at else 0), reverse=True)
    return {"jobs": [to_dict(j) for j in filtered[: f.limit]], "total": len(filtered), "providers": status,
            "deduplicated_from": len(collected), "filter_stats": stats,
            "synthetic_included": any(j.is_synthetic for j in filtered[: f.limit])}


__all__ = ["search_jobs", "upsert_jobs", "apply_filters", "SOURCES", "deduplicate", "configured_sources"]
