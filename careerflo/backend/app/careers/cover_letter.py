"""Cover letters and recruiter messages built from verified facts (LLM polish is optional and validated)."""
from __future__ import annotations

from datetime import date
from typing import Any


def draft_cover_letter(parsed: dict[str, Any], job: dict[str, Any], tone: str = "professional") -> str:
    name = parsed["contact"].get("name") or "Applicant"
    have = {s.lower() for s in parsed["skills"]}
    matched = [s for s in (job.get("required_skills") or []) + (job.get("preferred_skills") or []) if s.lower() in have]
    exp = parsed["experience"][:2]
    yrs = parsed.get("years_experience")
    opener = {"professional": "I am writing to apply for", "warm": "I was excited to see your opening for",
              "concise": "Please consider my application for"}.get(tone, "I am writing to apply for")
    lines = [date.today().strftime("%B %d, %Y"), "", f"Hiring Team, {job.get('company', '')}", "", "Dear Hiring Team,", "",
             f"{opener} the {job.get('title')} role at {job.get('company')}."
             + (f" I bring {int(yrs)}+ years of experience" if yrs and yrs >= 1 else " I bring hands-on experience")
             + (f" with {', '.join(matched[:4])}." if matched else ".")]
    for e in exp:
        if e["bullets"]:
            lines += ["", f"As {e['title']}{' at ' + e['employer'] if e.get('employer') else ''}, {e['bullets'][0][0].lower() + e['bullets'][0][1:]}"
                      .rstrip(".") + "."]
    lines += ["", f"I would welcome the chance to discuss how my background could support {job.get('company')}'s goals.",
              "", "Sincerely,", name]
    return "\n".join(lines)


def recruiter_message(parsed: dict[str, Any], job: dict[str, Any], recruiter_name: str | None = None) -> str:
    have = {s.lower() for s in parsed["skills"]}
    matched = [s for s in (job.get("required_skills") or []) if s.lower() in have][:3]
    return (f"Hi {recruiter_name or 'there'},\n\nI noticed the {job.get('title')} opening at {job.get('company')}. "
            f"My background{' in ' + ', '.join(matched) if matched else ''} looks like a strong fit, and I'd value a short conversation "
            f"about the team's priorities.\n\nThank you,\n{parsed['contact'].get('name') or ''}").strip()
