"""Domain errors mapped to HTTP responses by the API layer."""

from __future__ import annotations


class CommerceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(CommerceError):
    status_code = 404
    code = "not_found"


class Forbidden(CommerceError):
    status_code = 403
    code = "forbidden"


class Conflict(CommerceError):
    status_code = 409
    code = "conflict"


class PaymentFailed(CommerceError):
    status_code = 402
    code = "payment_declined"


class CheckoutUnavailable(CommerceError):
    status_code = 503
    code = "checkout_temporarily_unavailable"
