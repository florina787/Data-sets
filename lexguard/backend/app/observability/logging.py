"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.security.redaction import redact


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name,
                   "msg": record.getMessage()}
        extra = getattr(record, "structured", None)
        if extra:
            payload.update(redact(extra))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger("lexguard")
    if root.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level)
    root.propagate = False


def log_event(msg: str, **fields) -> None:
    logging.getLogger("lexguard").info(msg, extra={"structured": fields})
