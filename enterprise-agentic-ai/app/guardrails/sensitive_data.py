"""Detection and redaction of sensitive-looking data in generated text."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{8,}")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("credential", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token)\s*[:=]\s*[^\s,;]+")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone", re.compile(r"\+\d{1,3}(?:[\s.-]?\(?\d{1,4}\)?){2,5}\d")),
    ("phone", re.compile(r"(?<![\w-])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
]
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@((?:[\w-]+\.)+[\w-]+)\b")


def _luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redactions: list[str]  # e.g. ["phone x1", "api_key x1"]


def redact_sensitive(text: str, allowed_email_domain: str | None = None) -> RedactionResult:
    """Replace secrets and personal data with ``[REDACTED:<type>]`` markers.

    Work emails on ``allowed_email_domain`` are kept (they are directory data the
    user is allowed to see); any other email address is treated as personal.
    """
    counts: Counter[str] = Counter()

    for kind, pattern in _PATTERNS:
        def _sub(match: re.Match[str], kind: str = kind) -> str:
            counts[kind] += 1
            return f"[REDACTED:{kind}]"

        text = pattern.sub(_sub, text)

    def _card(match: re.Match[str]) -> str:
        if _luhn_valid(match.group(0)):
            counts["payment_card"] += 1
            return "[REDACTED:payment_card]"
        return match.group(0)

    text = _CARD_RE.sub(_card, text)

    def _email(match: re.Match[str]) -> str:
        domain = match.group(1).lower()
        if allowed_email_domain and (domain == allowed_email_domain or domain.endswith("." + allowed_email_domain)):
            return match.group(0)
        counts["personal_email"] += 1
        return "[REDACTED:personal_email]"

    text = _EMAIL_RE.sub(_email, text)
    return RedactionResult(text=text, redactions=[f"{k} x{v}" for k, v in sorted(counts.items())])
