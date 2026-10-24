"""Local demo identity: seeded synthetic users and HMAC-signed session tokens.

Tokens travel in the Authorization header (never in cookies), so browsers do
not attach them automatically and cross-site request forgery does not apply.
This is a demonstration mechanism; production requires an enterprise IdP
(OIDC/SAML), MFA and a formal security review.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Header, HTTPException, Request

from app.core import db
from app.core.config import get_settings

AUDIENCE = "flying-florina-ui"


@dataclass(frozen=True)
class Actor:
    id: str
    display_name: str
    role: str
    org: str
    clearances: tuple[str, ...] = field(default_factory=tuple)
    persona: str = ""
    is_agent: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "role": self.role,
            "org": self.org,
            "clearances": list(self.clearances),
            "persona": self.persona,
            "is_agent": self.is_agent,
        }


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(user_id: str, audience: str = AUDIENCE) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {"sub": user_id, "aud": audience, "iat": now, "exp": now + settings.session_ttl_seconds}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = _b64(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


class TokenError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def verify_token(token: str | None, audience: str = AUDIENCE) -> dict[str, Any]:
    if not token:
        raise TokenError("missing_token", "No session token was supplied.")
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("malformed_token", "Token is not in the expected format.") from exc
    expected = _b64(hmac.new(get_settings().session_secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise TokenError("bad_signature", "Token signature is invalid.")
    payload = json.loads(_unb64(body))
    if payload.get("aud") != audience:
        raise TokenError("wrong_audience", f"Token audience '{payload.get('aud')}' does not match '{audience}'.")
    if payload.get("exp", 0) < time.time():
        raise TokenError("expired_token", "Token has expired.")
    return payload


def load_actor(user_id: str) -> Actor | None:
    u = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not u:
        return None
    return Actor(
        id=u["id"],
        display_name=u["display_name"],
        role=u["role"],
        org=u["org"],
        clearances=tuple(db.jload(u["clearances"], [])),
        persona=u["persona"],
    )


def current_actor(request: Request, authorization: str | None = Header(default=None)) -> Actor:
    """FastAPI dependency: authenticated actor or 401."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    try:
        payload = verify_token(token)
    except TokenError as err:
        raise HTTPException(status_code=401, detail={"code": err.code, "message": err.message}) from err
    actor = load_actor(payload["sub"])
    if actor is None:
        raise HTTPException(status_code=401, detail={"code": "unknown_user", "message": "User no longer exists."})
    request.state.actor = actor
    return actor


SYSTEM_AGENT = Actor(id="agent.supervisor", display_name="Supervisor Agent", role="agent", org="FF-Demo-MRO", is_agent=True)
