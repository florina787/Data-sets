"""Identity: the Principal model, the IdentityProvider interface and the MOCK identity provider.

Production integrates the enterprise IdP via OIDC (token validation against JWKS, group->role mapping).
The mock IdP issues short-lived HS256 tokens for synthetic demo users only."""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

import jwt

from backend.config import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: tuple[str, ...]
    display_name: str = ""
    title: str = ""
    advisor_id: str | None = None
    clearance: str = "internal"
    business_unit: str = "corporate"
    region: str = "CA"
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def as_policy_input(self) -> dict:
        d = asdict(self)
        d["roles"] = list(self.roles)
        return d


class IdentityProvider(ABC):
    mode: str

    @abstractmethod
    def authenticate(self, token: str) -> Principal: ...


class AuthError(Exception):
    pass


class MockIdentityProvider(IdentityProvider):
    mode = "mock-idp (synthetic users, HS256, short-lived)"
    issuer = "flo-mock-idp"
    audience = "flo-api"

    def __init__(self, users: dict[str, dict]):
        self.users = users

    def issue(self, user_id: str) -> tuple[str, int]:
        u = self.users.get(user_id)
        if u is None:
            raise AuthError("unknown user")
        s = get_settings()
        now = int(time.time())
        exp = now + s.jwt_ttl_seconds
        claims = {"sub": user_id, "tid": u["tenant_id"], "iss": self.issuer, "aud": self.audience, "iat": now, "exp": exp,
                  "jti": uuid.uuid4().hex}
        return jwt.encode(claims, s.jwt_secret, algorithm="HS256"), exp

    def authenticate(self, token: str) -> Principal:
        s = get_settings()
        try:
            claims = jwt.decode(token, s.jwt_secret, algorithms=["HS256"], audience=self.audience, issuer=self.issuer,
                                options={"require": ["exp", "iat", "sub", "tid"]})
        except jwt.PyJWTError as e:
            raise AuthError(f"invalid token: {e.__class__.__name__}") from e
        u = self.users.get(claims["sub"])
        # roles and attributes come from the directory at request time, never from client-supplied claims
        if u is None or u["tenant_id"] != claims["tid"]:
            raise AuthError("principal not found in directory")
        return Principal(user_id=u["id"], tenant_id=u["tenant_id"], roles=tuple(u["roles"]), display_name=u["display_name"],
                         title=u["title"], advisor_id=u["advisor_id"], clearance=u["clearance"],
                         business_unit=u["business_unit"], region=u["region"], session_id=claims["jti"][:12])
