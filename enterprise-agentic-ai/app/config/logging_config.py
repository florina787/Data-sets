"""Logging setup with a filter that masks anything that looks like a secret."""

from __future__ import annotations

import logging
import re

_SECRET_PATTERN = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+")


class SecretMaskingFilter(logging.Filter):
    """Mask Anthropic-style API keys if they ever reach a log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API
        message = record.getMessage()
        if "sk-ant-" in message:
            record.msg = _SECRET_PATTERN.sub(r"\1***", message)
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once for the process."""
    root = logging.getLogger()
    if getattr(configure_logging, "_configured", False):
        root.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s - %(message)s")
    )
    handler.addFilter(SecretMaskingFilter())
    root.addHandler(handler)
    root.setLevel(level)
    # Chroma and HTTP clients are chatty at INFO.
    for noisy in ("chromadb", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    configure_logging._configured = True  # type: ignore[attr-defined]
