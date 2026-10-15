"""Small shared helpers: identifiers, clocks and the safe application error type."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    """Deterministic hash of a JSON-serialisable value (used to bind approvals to change sets)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class AppError(Exception):
    """An error whose message is safe to show to the user.

    `code` is a stable machine-readable identifier; `status` is the HTTP status. Internal
    details (stack traces, paths, prompts) are never put in `message`.
    """

    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None,
                 retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
        self.retryable = retryable

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }
