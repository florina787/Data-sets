"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*['\"]?[^\s'\",]{6,}"),
]


def redact(text: str) -> str:
    """Mask anything that looks like a credential."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON documents."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update({k: v for k, v in extra.items()})
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return redact(json.dumps(payload, default=str))


_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Idempotently configure the root ``archai`` logger."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("archai")
    logger.handlers = [handler]
    logger.setLevel(level.upper())
    logger.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"archai.{name}")


def log_event(logger: logging.Logger, message: str, **fields: object) -> None:
    """Log an INFO event with structured fields."""
    logger.info(message, extra={"extra_fields": fields})
