"""Redaction for logs, audit reasons and any text sent to a language provider."""
from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)(\s*[=:]\s*)\S+"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\.\-_]{10,}"), "Bearer [REDACTED]"),
    (re.compile(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]{16,}"), "[REDACTED_IMAGE_DATA]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text


def contains_image_payload(obj) -> bool:
    s = str(obj)
    return "data:image/" in s or "/9j/" in s[:2000] or "iVBORw0KGgo" in s
