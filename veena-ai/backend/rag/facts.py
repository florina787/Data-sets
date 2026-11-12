"""Deterministic facts computed from retrieved passages, so a small model does not do arithmetic.

Today: total experience span from employment date ranges ("June 2018 to February 2021",
"03/2021 - Present", "2016 – 2018"). The result is given to the model as a computed note that
lists the ranges it used; nothing is computed when no ranges are found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_POINT = rf"(?:{_MON}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
_END = rf"(?:{_POINT}|present|current|now|today|date)"
_RANGE = re.compile(rf"\b({_POINT})\s*(?:-|–|—|to|until|till)\s*({_END})\b", re.I)
_EXPLICIT = re.compile(
    r"[^.\n]*\b\d{1,2}\+?\s*(?:years?|yrs)\b[^.\n]*\bexperience\b[^.\n]*|[^.\n]*\bexperience\b[^.\n]*\b\d{1,2}\+?\s*(?:years?|yrs)\b[^.\n]*",
    re.I,
)
EXPERIENCE_Q = re.compile(r"\b(years?|how long|experience|tenure)\b", re.I)


@dataclass
class Span:
    text: str
    start: date
    end: date


def _point(s: str, today: date, is_end: bool) -> date | None:
    s = s.strip().lower().rstrip(".")
    if s in ("present", "current", "now", "today", "date"):
        return today
    m = re.fullmatch(rf"({_MON})\.?\s+(\d{{4}})", s)
    if m:
        return date(int(m.group(2)), _MONTHS[m.group(1)[:3]], 1)
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.fullmatch(r"\d{4}", s)
    if m:
        y = int(s)
        return date(y, 12, 1) if is_end else date(y, 1, 1)
    return None


def employment_spans(text: str, today: date | None = None) -> list[Span]:
    today = today or date.today()
    out = []
    for m in _RANGE.finditer(text):
        a, b = _point(m.group(1), today, False), _point(m.group(2), today, True)
        if a and b and a <= b <= today and 1950 <= a.year <= today.year:
            out.append(Span(m.group(0), a, b))
    return out


def experience_note(question: str, passages: list[str], today: date | None = None) -> str | None:
    """A computed-fact note for 'how many years of experience' questions, or None."""
    if not EXPERIENCE_Q.search(question):
        return None
    today = today or date.today()
    joined = "\n".join(passages)
    explicit = [m.group(0).strip() for m in _EXPLICIT.finditer(joined)][:2]
    spans = employment_spans(joined, today)
    if explicit and not spans:
        return f"The document states its experience explicitly: “{explicit[0]}”. Report that statement."
    if not spans:
        return None
    start, end = min(s.start for s in spans), max(s.end for s in spans)
    months = (end.year - start.year) * 12 + (end.month - start.month)
    # Months actually covered by at least one range (overlaps counted once, gaps excluded).
    covered = set()
    for s in spans:
        y, mth = s.start.year, s.start.month
        while (y, mth) <= (s.end.year, s.end.month):
            covered.add((y, mth))
            y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
    worked = max(0, len(covered) - 1)
    ranges = "; ".join(s.text for s in spans)
    lead = (
        (
            f"The document states its experience explicitly: “{explicit[0]}”. Report that stated figure first; you may add the "
            "date-based calculation below as a cross-check. "
        )
        if explicit
        else ""
    )
    return lead + (
        f"Computed by VEENA from the date ranges in the passages (as of {today:%B %Y}): ranges found: {ranges}. "
        f"Earliest start {start:%B %Y}, latest end {'present' if end == today else f'{end:%B %Y}'}: about "
        f"{months // 12} years {months % 12} months in total; about {worked // 12} years {worked % 12} months "
        "covered by the listed roles (gaps excluded, overlaps counted once). Report this calculation and the dates it used."
    )
