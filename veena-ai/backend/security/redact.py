"""Text redaction for logs, OCR output and anything else that may hold secrets."""

from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

# Ordered: most specific first. Each pattern replaces the whole match, or only
# the value group when the pattern has one named "value".
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("api_key_prefix", re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj|ant)?[-_]?[A-Za-z0-9_-]{16,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+(?P<value>[A-Za-z0-9._~+/=-]{12,})")),
    (
        "assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|token)"
            r"\s*[:=]\s*(?P<value>\"[^\"]+\"|'[^']+'|\S+)"
        ),
    ),
    ("card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact_text(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, kinds_found)."""
    found: list[str] = []
    for kind, pattern in _PATTERNS:

        def _sub(m: re.Match[str], kind: str = kind) -> str:
            if kind == "card" and not _luhn_ok(m.group(0)):
                return m.group(0)
            found.append(kind)
            if "value" in m.groupdict() and m.group("value"):
                start, end = m.span("value")
                s0 = m.start()
                whole = m.group(0)
                return whole[: start - s0] + REDACTED + whole[end - s0 :]
            return REDACTED

        text = pattern.sub(_sub, text)
    return text, found


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs secrets from every record before it is written."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - never break logging
            return True
        record.msg, _ = redact_text(msg)
        record.args = ()
        return True


def install_log_redaction() -> None:
    f = RedactingFilter()
    root = logging.getLogger()
    root.addFilter(f)
    for h in root.handlers:
        h.addFilter(f)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "veena"):
        logging.getLogger(name).addFilter(f)
