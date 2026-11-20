"""Prompt-injection heuristics.

Defence in depth, not a guarantee: the primary controls are structural (the model
cannot call tools or write SQL, it only fills typed schemas whose values are
validated, and transcript text is passed as delimited data). These patterns flag
suspicious user questions and retrieved passages for the audit log.
"""

from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ignore (all |any )?(previous|prior|above) (instructions|rules|prompts?)",
        r"disregard (the |your )?(system|previous) (prompt|instructions)",
        r"you are now\b",
        r"(reveal|print|show|output) (your|the) (system prompt|instructions|api key|secrets?)",
        r"\b(api[_ -]?key|password|secret|token)\b.*\b(show|give|reveal|print)\b",
        r"(drop|delete|truncate|alter|insert|update)\s+(table|from|into)\b",
        r";\s*--",
        r"<\s*/?\s*(system|assistant|instructions?)\s*>",
        r"(execute|run) (this )?(code|python|shell|sql)",
        r"act as (an? )?(admin|administrator|developer|root)",
    ]
]
MAX_QUESTION_CHARS = 1000
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scan(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


def sanitize_question(text: str) -> str:
    return _CONTROL.sub(" ", text).strip()[:MAX_QUESTION_CHARS]
