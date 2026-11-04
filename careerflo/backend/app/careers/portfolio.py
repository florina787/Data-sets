"""GitHub portfolio intelligence (public repositories, or the user's own token if configured)."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

import httpx

from ..config import get_settings
from ..jobs.skills import extract_skills
from ..security.sanitize import neutralize

USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
LANG_SKILL = {"Python": "Python", "TypeScript": "TypeScript", "JavaScript": "JavaScript", "Go": "Go", "Rust": "Rust",
              "Java": "Java", "C++": "C++", "C#": "C#", "Scala": "Scala", "Dockerfile": "Docker", "HCL": "Terraform",
              "Jupyter Notebook": "Python", "Shell": "Linux", "R": "R"}


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "CareerFloAI/0.1"}
    tok = get_settings().github_token
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


async def list_repositories(username: str, limit: int = 30) -> list[dict[str, Any]]:
    if not USERNAME_RE.match(username or ""):
        raise ValueError("Invalid GitHub username")
    async with httpx.AsyncClient(timeout=10, headers=_headers()) as c:
        r = await c.get(f"https://api.github.com/users/{username}/repos", params={"per_page": 100, "sort": "updated", "type": "owner"})
        if r.status_code == 404:
            raise ValueError("GitHub user not found")
        r.raise_for_status()
        repos = [x for x in r.json() if not x.get("fork") and not x.get("archived")][:limit]
        out = []
        for repo in repos[:12]:
            langs: dict[str, int] = {}
            try:
                lr = await c.get(repo["languages_url"])
                if lr.status_code == 200:
                    langs = lr.json()
            except httpx.HTTPError:
                pass
            desc, _ = neutralize(repo.get("description") or "", 500)
            out.append({"name": repo["name"], "url": repo["html_url"], "description": desc, "languages": langs,
                        "topics": repo.get("topics") or [], "stars": repo.get("stargazers_count", 0),
                        "updated_at": repo.get("pushed_at")})
        return out


def analyze_stack(repos: list[dict[str, Any]]) -> dict[str, Any]:
    lang_bytes: Counter[str] = Counter()
    for r in repos:
        lang_bytes.update(r.get("languages") or {})
    total = sum(lang_bytes.values()) or 1
    skills: Counter[str] = Counter()
    for r in repos:
        text = " ".join([r["name"].replace("-", " "), r.get("description") or "", " ".join(r.get("topics") or [])])
        for s in extract_skills(text):
            skills[s] += 1
        for lang in r.get("languages") or {}:
            if lang in LANG_SKILL:
                skills[LANG_SKILL[lang]] += 1
    return {"languages": [{"language": k, "share": round(v / total, 3)} for k, v in lang_bytes.most_common(10)],
            "skills": skills.most_common(20), "repo_count": len(repos),
            "total_stars": sum(r.get("stars", 0) for r in repos)}


def project_skills(r: dict[str, Any]) -> set[str]:
    text = " ".join([r["name"].replace("-", " "), r.get("description") or "", " ".join(r.get("topics") or [])])
    s = set(extract_skills(text))
    s |= {LANG_SKILL[lang] for lang in (r.get("languages") or {}) if lang in LANG_SKILL}
    return s


def match_projects(repos: list[dict[str, Any]], job: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = {s.lower() for s in (job.get("required_skills") or []) + (job.get("preferred_skills") or [])}
    out = []
    for r in repos:
        hits = sorted(s for s in project_skills(r) if s.lower() in wanted)
        if hits:
            out.append({"name": r["name"], "url": r["url"], "matched_skills": hits, "relevance": len(hits),
                        "talking_point": f"{r['name']}: demonstrates {', '.join(hits)} (public repository)."})
    return sorted(out, key=lambda x: -x["relevance"])[:8]
