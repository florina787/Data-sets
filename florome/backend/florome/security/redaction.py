"""Credential and PII redaction applied to tool output, connector payloads, logs and audit detail.

PII patterns are adapted from Project A (conversation-intelligence-copilot/backend/app/governance/pii.py);
credential patterns are new. Redaction is defence in depth: credentials are never handed to connectors'
callers or to any model in the first place.
"""

from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "github_token": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws_access_key": re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/]{16,}=*"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    "generic_secret": re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[^\s'\",;]{6,}"),
    "connection_string_key": re.compile(r"(?i)(AccountKey|SharedAccessKey)=[A-Za-z0-9+/=]{16,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
}
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "card_number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
}
SENSITIVE_KEYS = re.compile(r"(?i)(password|secret|token|api[_-]?key|authorization|credential|private[_-]?key)")


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for kind, pat in {**SECRET_PATTERNS, **PII_PATTERNS}.items():
        text, n = pat.subn(f"[REDACTED:{kind}]", text)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return text, counts


def redact(value: Any) -> Any:
    """Recursively redact strings and values under sensitive-looking keys."""
    if isinstance(value, str):
        return redact_text(value)[0]
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE_KEYS.search(str(k)) and v not in (None, "", False) else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value
