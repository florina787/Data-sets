"""Session handling.

DEMO mode: a persona is chosen through POST /api/auth/demo-login and the
server issues an HMAC-signed session token. Identity, role and tenant are
then read from the server-side user record on every request; the client
cannot assert them.

PRODUCTION mode: persona login is disabled. Requests must carry a token from
a configured identity provider (SSO/OIDC). That verifier is not implemented
in this prototype, so production mode rejects all requests with a clear
"identity provider not configured" error rather than falling back.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models.orm import User
from .permissions import Perm, has_perm


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str
    display_name: str
    account_segments: tuple[str, ...]

    def can(self, perm: Perm) -> bool:
        return has_perm(self.role, perm)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_token(user_id: str) -> str:
    s = get_settings()
    body = json.dumps(
        {"sub": user_id, "exp": int(time.time()) + s.session_ttl_minutes * 60, "kind": "demo"},
        separators=(",", ":"),
    ).encode()
    sig = hmac.new(s.session_secret.encode(), body, hashlib.sha256).digest()
    return f"{_b64(body)}.{_b64(sig)}"


def verify_token(token: str) -> str:
    s = get_settings()
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _unb64(body_b64)
        expected = hmac.new(s.session_secret.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig_b64)):
            raise ValueError("bad signature")
        claims = json.loads(body)
        if claims.get("kind") != "demo" or claims["exp"] < time.time():
            raise ValueError("expired")
        return str(claims["sub"])
    except Exception as exc:  # noqa: BLE001 - any parse failure is an auth failure
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION",
                                                     "message": "Session invalid or expired"}) from exc


def get_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    settings = get_settings()
    if not settings.is_demo:
        raise HTTPException(
            status_code=503,
            detail={"code": "IDP_NOT_CONFIGURED",
                    "message": "Production mode requires an SSO identity provider, "
                               "which is not configured in this prototype."},
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "NOT_AUTHENTICATED",
                                                     "message": "Sign in required"})
    user_id = verify_token(authorization.split(" ", 1)[1].strip())
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail={"code": "INVALID_SESSION",
                                                     "message": "Unknown user"})
    principal = Principal(user.id, user.tenant_id, user.role, user.display_name,
                          tuple(user.account_segments or []))
    request.state.principal = principal
    return principal


def require(perm: Perm):
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(perm):
            raise HTTPException(status_code=403, detail={
                "code": "FORBIDDEN", "message": f"Role '{principal.role}' lacks {perm.value}"})
        return principal

    return _dep
