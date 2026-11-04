"""Normalise postings from every provider into one schema, then de-duplicate across providers."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .skills import split_required_preferred


class NormalizedJob(BaseModel):
    source: str
    source_job_id: str
    origin_publisher: str | None = None
    company: str
    title: str
    location: str | None = None
    city: str | None = None
    country: str | None = None
    work_arrangement: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    industry: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_verified: bool = False
    description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    apply_url: str | None = None
    verification_status: str = "unverified"
    is_synthetic: bool = False

    @property
    def dedupe_key(self) -> str:
        return dedupe_key(self.company, self.title, self.city or self.location or "")


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_COMPANY_SUFFIX = re.compile(r"\b(inc|inc\.|ltd|ltd\.|llc|corp|corporation|co|company|limited|gmbh|plc)\b\.?", re.I)


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    import html

    text = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*li\s*>", "\n- ", text, flags=re.I)
    text = html.unescape(_TAG_RE.sub("", text))
    text = _WS_RE.sub(" ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _norm(s: str) -> str:
    s = _COMPANY_SUFFIX.sub("", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


TITLE_SYNONYMS = {"sr": "senior", "jr": "junior", "eng": "engineer", "swe": "software engineer", "ml": "machine learning"}


def _norm_title(t: str) -> str:
    words = [TITLE_SYNONYMS.get(w, w) for w in _norm(t).split()]
    return " ".join(words)


def dedupe_key(company: str, title: str, city: str) -> str:
    raw = "|".join([_norm(company), _norm_title(title), _norm(city.split(",")[0] if city else "")])
    return hashlib.sha256(raw.encode()).hexdigest()


SENIORITY_CUES = [("principal", "principal"), ("staff", "staff"), ("lead", "lead"), ("senior", "senior"),
                  ("sr.", "senior"), ("sr ", "senior"), ("junior", "junior"), ("jr", "junior"), ("intern", "intern"),
                  ("director", "director"), ("head of", "director"), ("manager", "manager")]


def infer_seniority(title: str) -> str:
    t = (title or "").lower() + " "
    for cue, level in SENIORITY_CUES:
        if cue in t:
            return level
    return "mid"


def infer_arrangement(*texts: str | None, remote_flag: bool | None = None) -> str | None:
    if remote_flag:
        return "remote"
    blob = " ".join(t or "" for t in texts).lower()
    if "hybrid" in blob:
        return "hybrid"
    if re.search(r"\bremote\b", blob):
        return "remote"
    if any(w in blob for w in ("on-site", "onsite", "in office", "in-office")):
        return "onsite"
    return None


SALARY_RE = re.compile(
    r"(?P<cur>CAD|USD|EUR|GBP|C\$|US\$|\$|£|€)\s?(?P<a>\d{2,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s?(?P<ak>[kK])?"
    r"\s?(?:-|–|to)\s?(?:CAD|USD|EUR|GBP|C\$|US\$|\$|£|€)?\s?(?P<b>\d{2,3}(?:[,.]?\d{3})*(?:\.\d+)?)\s?(?P<bk>[kK])?")
CUR_MAP = {"C$": "CAD", "US$": "USD", "£": "GBP", "€": "EUR"}


def parse_salary_text(text: str, default_currency: str | None = None) -> tuple[float, float, str] | None:
    """Extract a published salary range from free text. Returns None if none is clearly published."""
    m = SALARY_RE.search(text or "")
    if not m:
        return None

    def num(v: str, k: str | None) -> float:
        v = v.replace(",", "")
        x = float(v)
        return x * 1000 if k else x

    a, b = num(m.group("a"), m.group("ak")), num(m.group("b"), m.group("bk"))
    if a < 1000 or b < a or b > 5_000_000:  # hourly or nonsense: do not guess
        return None
    cur = m.group("cur")
    cur = CUR_MAP.get(cur, cur)
    if cur == "$":
        cur = default_currency or "USD"
    return a, b, cur


def enrich(job: NormalizedJob) -> NormalizedJob:
    job.description = strip_html(job.description)[:20000]
    if not job.required_skills and not job.preferred_skills:
        job.required_skills, job.preferred_skills = split_required_preferred(f"{job.title}\n{job.description}")
    job.seniority = job.seniority or infer_seniority(job.title)
    job.work_arrangement = job.work_arrangement or infer_arrangement(job.title, job.location, job.description[:3000])
    if job.salary_min is None and job.salary_max is None:
        parsed = parse_salary_text(job.description)
        if parsed:
            job.salary_min, job.salary_max, job.salary_currency = parsed
            job.salary_period, job.salary_verified = "year", True
    if job.city is None and job.location:
        job.city = job.location.split(",")[0].strip() or None
    return job


def deduplicate(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Keep one posting per (company, title, city). Prefer direct employer boards, then postings with
    salary, then the most recent. Every merged source is remembered for attribution."""
    priority = {"greenhouse": 0, "lever": 0, "ashby": 0, "adzuna": 2, "jsearch": 1, "synthetic": 5}
    best: dict[str, NormalizedJob] = {}
    seen_urls: dict[str, str] = {}
    for j in jobs:
        key = j.dedupe_key
        if j.apply_url:
            url_key = re.sub(r"[?#].*$", "", j.apply_url.lower())
            if url_key in seen_urls:
                key = seen_urls[url_key]
            else:
                seen_urls[url_key] = key
        cur = best.get(key)
        if cur is None:
            best[key] = j
            continue
        rank_new = (priority.get(j.source, 3), j.salary_min is None, -(j.posted_at.timestamp() if j.posted_at else 0))
        rank_cur = (priority.get(cur.source, 3), cur.salary_min is None, -(cur.posted_at.timestamp() if cur.posted_at else 0))
        winner, loser = (j, cur) if rank_new < rank_cur else (cur, j)
        if winner.salary_min is None and loser.salary_min is not None and loser.salary_verified:
            winner.salary_min, winner.salary_max = loser.salary_min, loser.salary_max
            winner.salary_currency, winner.salary_period, winner.salary_verified = (
                loser.salary_currency, loser.salary_period, True)
        best[key] = winner
    return list(best.values())


def to_dict(j: Any) -> dict[str, Any]:
    keys = ["id", "source", "source_job_id", "origin_publisher", "company", "title", "location", "city", "country",
            "work_arrangement", "employment_type", "seniority", "industry", "salary_min", "salary_max",
            "salary_currency", "salary_period", "salary_verified", "required_skills", "preferred_skills",
            "posted_at", "retrieved_at", "apply_url", "verification_status", "is_synthetic"]
    out = {k: getattr(j, k, None) for k in keys}
    if out.get("id") is not None:
        out["id"] = str(out["id"])
    for k in ("posted_at", "retrieved_at"):
        if isinstance(out.get(k), datetime):
            out[k] = out[k].isoformat()
    desc = getattr(j, "description", "") or ""
    out["description_snippet"] = desc[:400]
    return out
