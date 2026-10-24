"""Governance agent: post-generation checks on evidence use, unsupported claims and privacy."""

from __future__ import annotations

import re

_CITE = re.compile(r"\[(\d{1,2})\]")
_FIRST_PERSON_EXPERIENCE = re.compile(
    r"\b(I (led|built|designed|managed|launched|shipped|architected|owned|grew|reduced|increased|delivered)|"
    r"at my (previous|last|current) (company|job|role)|in my (previous|last) role)\b",
    re.I,
)
_PERCENT_OR_MONEY = re.compile(r"\b\d+(\.\d+)?\s?%|\$\s?\d[\d,.]*\s?(k|m|million|billion)?\b", re.I)


def review(
    answer: str,
    *,
    evidence: list[dict],
    knowledge_requested: bool,
    interview_mode: bool,
    resume_evidence: bool,
    notes: list[str],
) -> dict:
    flags: list[dict] = []
    cited = {int(n) for n in _CITE.findall(answer)}
    valid = {e["n"] for e in evidence}
    bogus = sorted(cited - valid)
    if bogus:
        flags.append({"kind": "invalid_citation", "detail": f"answer cites {bogus} but no such evidence was retrieved"})
    if knowledge_requested and not evidence:
        flags.append({"kind": "no_evidence", "detail": "no passages in the selected collections matched this question"})
    elif evidence and not cited:
        flags.append({"kind": "uncited", "detail": "evidence was retrieved but the answer does not cite it"})
    if interview_mode and not resume_evidence and _FIRST_PERSON_EXPERIENCE.search(answer):
        flags.append(
            {
                "kind": "unsupported_experience",
                "detail": "the answer describes personal experience but no resume is loaded to support it",
            }
        )
    if interview_mode and _PERCENT_OR_MONEY.search(answer) and not resume_evidence:
        flags.append({"kind": "unsupported_metric", "detail": "the answer contains figures not backed by your resume"})
    return {
        "flags": flags,
        "notes": notes,
        "cited": sorted(cited & valid),
        "grounded": bool(evidence) and bool(cited & valid) and not bogus,
    }
