"""Authentication and per-request identity.

Production uses Supabase Auth: the frontend signs users up / in (with email verification and
password reset handled by Supabase) and sends the access token; the backend verifies it here.
``AUTH_MODE=local`` lets the backend issue equivalent tokens for development, tests and
self-hosting without Supabase.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Profile, User, UserPreference

LOCAL_ISSUER = "careerflo-local"


def canonical_email(email: str) -> str:
    local, _, domain = email.strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def email_hash(email: str) -> str:
    return hashlib.sha256(canonical_email(email).encode()).hexdigest()


# ---------------------------------------------------------------- passwords (local mode)
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_b64, dk_b64 = stored.split("$")
    dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(dk, base64.b64decode(dk_b64))


PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{10,128}$")


def issue_local_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user.id), "email": user.email, "aud": "authenticated", "iss": LOCAL_ISSUER,
              "iat": now, "exp": now + timedelta(minutes=s.local_token_ttl_minutes), "role": "authenticated"}
    return jwt.encode(claims, s.local_jwt_secret, algorithm="HS256")


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True)


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        if s.auth_mode == "local":
            return jwt.decode(token, s.local_jwt_secret, algorithms=["HS256"], audience="authenticated",
                              issuer=LOCAL_ISSUER)
        if s.supabase_jwt_secret:
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience=s.supabase_jwt_audience)
        if not s.supabase_url:
            raise HTTPException(500, "Supabase auth is not configured (SUPABASE_URL)")
        key = _jwks_client(f"{s.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json").get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience=s.supabase_jwt_audience)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"}) from exc


def provision_user(db: Session, user_id: uuid.UUID, email: str, *, password_hash: str | None = None,
                   verified: bool = False) -> User:
    s = get_settings()
    user = User(id=user_id, email=email.lower(), email_canonical_hash=email_hash(email), password_hash=password_hash,
                email_verified=verified, is_admin=email.lower() in s.admin_email_set)
    db.add(user)
    try:
        db.flush()  # user row first: profile/preferences reference it
        db.add(Profile(user_id=user_id))
        db.add(UserPreference(user_id=user_id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An account already exists for this email address (or an alias of it).") from exc
    return user


def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_token(header[7:].strip())
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(401, "Invalid token subject") from exc
    user = db.get(User, user_id)
    if user is None:
        if get_settings().auth_mode == "local":
            raise HTTPException(401, "Unknown user")
        # First request from a Supabase user: provision the application-side row (id = auth.uid()).
        user = provision_user(db, user_id, claims.get("email") or f"{user_id}@users.invalid",
                              verified=bool(claims.get("email_confirmed_at") or claims.get("email_verified", True)))
    elif claims.get("email") and claims["email"].lower() != user.email:
        # Email change: the account (and its trial counters) is keyed by id, so nothing resets.
        user.email = claims["email"].lower()
        db.commit()
    if user.disabled:
        raise HTTPException(403, "Account disabled")
    request.state.user_id = user.id
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DB = Annotated[Session, Depends(get_db)]
