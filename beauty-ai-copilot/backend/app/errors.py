"""Structured errors. Categories distinguish failed computation, failed policy and unavailable integration."""
from __future__ import annotations


class DomainError(Exception):
    category = "error"
    http_status = 400

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self, trace_id: str | None = None) -> dict:
        return {"error": {"category": self.category, "code": self.code, "message": self.message,
                          "details": self.details, "trace_id": trace_id}}


class NotFound(DomainError):
    category = "not_found"
    http_status = 404


class Unauthorized(DomainError):
    category = "authentication"
    http_status = 401


class Forbidden(DomainError):
    category = "authorization"
    http_status = 403


class PolicyViolation(DomainError):
    """A deterministic policy or lifecycle rule blocked the action."""
    category = "policy"
    http_status = 409


class Conflict(DomainError):
    category = "conflict"
    http_status = 409


class ValidationFailed(DomainError):
    category = "validation"
    http_status = 422


class ComputationFailed(DomainError):
    category = "computation"
    http_status = 500


class IntegrationUnavailable(DomainError):
    category = "integration_unavailable"
    http_status = 503
