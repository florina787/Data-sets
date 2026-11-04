"""ATS simulation: keyword coverage, structure and parse-ability checks (deterministic)."""
from __future__ import annotations

import re
from typing import Any

from ..jobs.skills import extract_skills


def ats_check(resume_text: str, parsed: dict[str, Any], job: dict[str, Any] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, weight: int, detail: str) -> None:
        checks.append({"check": name, "passed": ok, "weight": weight, "detail": detail})

    sections = set(parsed.get("sections_found", []))
    add("Standard section headings", {"experience", "education", "skills"} <= sections, 15,
        f"Found: {', '.join(sorted(sections)) or 'none'}. ATS parsers look for Experience, Education and Skills.")
    add("Contact details", bool(parsed["contact"].get("email")), 10, "Email address detected." if parsed["contact"].get("email") else "Add an email address in plain text.")
    add("Dated experience entries", bool(parsed["experience"]), 15, f"{len(parsed['experience'])} dated roles parsed.")
    pipes = sum(1 for ln in resume_text.splitlines() if ln.count("|") >= 3 or "\t\t" in ln)
    add("No tables / multi-column layout", pipes <= 2, 10, f"{pipes} table-like lines detected." if pipes > 2 else "Single-column text parses cleanly.")
    odd = len(re.findall(r"[^\x00-\x7F•–—’‘“”éèàçôö]", resume_text))
    add("No unusual symbols / icons", odd < 15, 5, f"{odd} unusual characters (icons, emoji, special glyphs).")
    wc = len(resume_text.split())
    add("Length", 300 <= wc <= 1200, 5, f"{wc} words (300–1,200 recommended).")
    keyword_score = None
    missing: list[str] = []
    matched: list[str] = []
    if job:
        keywords = list(dict.fromkeys((job.get("required_skills") or []) + (job.get("preferred_skills") or [])))
        if not keywords:
            keywords = extract_skills(job.get("description", ""))
        have = {s.lower() for s in extract_skills(resume_text)} | {s.lower() for s in parsed.get("skills", [])}
        matched = [k for k in keywords if k.lower() in have]
        missing = [k for k in keywords if k.lower() not in have]
        keyword_score = round(100 * len(matched) / len(keywords), 1) if keywords else None
        title_words = [w for w in re.findall(r"[a-z]+", (job.get("title") or "").lower()) if len(w) > 3]
        title_hit = all(w in resume_text.lower() for w in title_words) if title_words else True
        add("Keyword coverage", (keyword_score or 0) >= 60, 30, f"{len(matched)}/{len(keywords)} job keywords present.")
        add("Target title present", title_hit, 10, "Job title wording appears in resume." if title_hit else "Consider using the target title wording where it truthfully applies.")
    total = sum(c["weight"] for c in checks)
    score = round(100 * sum(c["weight"] for c in checks if c["passed"]) / total, 1)
    return {"score": score, "keyword_coverage": keyword_score, "matched_keywords": matched, "missing_keywords": missing,
            "checks": checks,
            "note": "Simulation of common ATS parsing behaviour; real ATS products differ. Never add keywords you can't back up."}
