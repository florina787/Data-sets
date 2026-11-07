"""Safe application error. Adapted from FloPilot backend/app/common.py (AppError)."""
from __future__ import annotations


class AppError(Exception):
    """An error whose message is safe to show to the user. `code` is stable and machine-readable."""

    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None,
                 retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details, self.retryable = details or {}, retryable

    def to_dict(self) -> dict:
        return {"schema_version": "1.0", "code": self.code, "message": self.message,
                "details": self.details, "retryable": self.retryable}
