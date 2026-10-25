"""Token checks for the adapter (demo HMAC tokens; production: OIDC/JWT via the enterprise IdP).

Validates signature, audience, expiry and scope for every request. The
caller's token is verified here and is never forwarded upstream.
"""
import base64
import hashlib
import hmac
import json
import os
import time

AUDIENCE = "ff-parts-adapter"
REQUIRED_SCOPE = "inventory.read"


def _secret() -> bytes:
    return os.environ.get("ADAPTER_DEMO_SECRET", "local-demo-secret-change-me").encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def issue_demo_token(sub: str, scopes: list[str], aud: str = AUDIENCE, ttl: int = 600) -> str:
    body = _b64(json.dumps({"sub": sub, "aud": aud, "scope": " ".join(scopes), "exp": int(time.time()) + ttl}).encode())
    return body + "." + _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


class AuthError(Exception):
    def __init__(self, code: str, status: int = 401):
        super().__init__(code)
        self.code = code
        self.status = status


def verify(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing_token")
    token = authorization[7:].strip()
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("malformed_token") from exc
    good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(good, sig):
        raise AuthError("bad_signature")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if claims.get("aud") != AUDIENCE:
        raise AuthError("wrong_audience")
    if claims.get("exp", 0) < time.time():
        raise AuthError("expired_token")
    if REQUIRED_SCOPE not in claims.get("scope", "").split():
        raise AuthError("insufficient_scope", 403)
    return claims
