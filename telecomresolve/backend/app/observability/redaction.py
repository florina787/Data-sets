"""Redaction for logs and audit details. Secrets and contact identifiers are
masked before anything is written to logs or audit records."""
from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\+?1?[\s\-.(]*\d{3}[\s\-.)]*\d{3}[\s\-.]*\d{4}\b"), "[REDACTED_PHONE]"),
]
_SENSITIVE_KEYS = {"contact_phone", "contact_email", "authorization", "api_key", "llm_api_key",
                   "password", "session_secret", "token"}


def redact_text(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else redact(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value
