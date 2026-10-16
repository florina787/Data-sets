"""Application-level field encryption (Fernet / AES-128-CBC + HMAC).

In demo mode without FIELD_ENCRYPTION_KEY a per-process key is generated, which
means encrypted demo fields are unreadable after restart (acceptable for demo).
Staging/production refuse to start without a configured key.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config.settings import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().field_encryption_key.get_secret_value()
    return Fernet(key.encode() if key else Fernet.generate_key())


def encrypt(value: str | None) -> str | None:
    return None if value is None else _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    return None if token is None else _fernet().decrypt(token.encode()).decode()
