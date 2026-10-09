"""Mock payment processor. No real charges are ever made."""

from __future__ import annotations

import hashlib

APPROVED_TOKEN = "tok_demo_ok"
DECLINED_TOKEN = "tok_demo_decline"


class PaymentDeclined(Exception):
    pass


def charge(token: str, amount_cents: int, idempotency_key: str) -> str:
    """Return a mock payment reference or raise PaymentDeclined."""
    if amount_cents < 0:
        raise ValueError("amount must be non-negative")
    if token != APPROVED_TOKEN:
        reason = "Mock card declined" if token == DECLINED_TOKEN else "Unknown mock token"
        raise PaymentDeclined(reason)
    digest = hashlib.sha256(f"{idempotency_key}:{amount_cents}".encode()).hexdigest()[:12]
    return f"MOCKPAY-{digest}"
