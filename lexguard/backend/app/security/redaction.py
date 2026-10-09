"""Safe-logging helpers: secrets are never written to logs or audit payloads."""

from __future__ import annotations

import re

SECRET_KEYS = re.compile(r"(api[_-]?key|token|secret|password|authorization|cookie)", re.IGNORECASE)
SECRET_VALUES = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{8,}|sk-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._\-]{10,})")


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SECRET_KEYS.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return SECRET_VALUES.sub("[REDACTED]", value)
    return value
