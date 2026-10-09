"""Platform errors mapped to HTTP status codes by the API layer."""

from __future__ import annotations


class PlatformError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(PlatformError):
    status_code = 404
    code = "not_found"


class Unauthorized(PlatformError):
    status_code = 401
    code = "unauthorized"


class Forbidden(PlatformError):
    status_code = 403
    code = "forbidden"


class Conflict(PlatformError):
    status_code = 409
    code = "conflict"


class InvalidTransition(Conflict):
    code = "invalid_transition"


class GateFailed(Conflict):
    code = "release_gates_not_satisfied"


class ToolRejected(PlatformError):
    status_code = 422
    code = "tool_request_rejected"


class LiveModeUnavailable(PlatformError):
    status_code = 503
    code = "live_mode_unavailable"
