"""Identity: JWT validation and the Principal propagated through every layer.

The token proves *who* the caller is. It deliberately does NOT carry the list
of clients the caller may see: entitlements change daily (book transfers,
leaves, terminations) and are resolved server-side from the authoritative
entitlement store on every request (see ``authz.py``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

import jwt

from wealth_ai.config import settings


class Role(str, Enum):
    ADVISOR = "advisor"
    RELATIONSHIP_MANAGER = "relationship_manager"
    PORTFOLIO_MANAGER = "portfolio_manager"
    OPERATIONS = "operations"
    COMPLIANCE = "compliance"


@dataclass(frozen=True)
class Principal:
    user_id: str
    name: str
    roles: frozenset[Role]
    advisor_group: str
    region: str
    token_id: str | None = None
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    def has_role(self, *roles: Role) -> bool:
        return bool(self.roles.intersection(roles))


class AuthenticationError(Exception):
    pass


def issue_token(user_id: str, name: str, roles: list[str], advisor_group: str = "wealth", region: str = "canada", ttl_s: int = 3600) -> str:
    """Dev/test helper. Production tokens come from the corporate IdP."""
    now = int(time.time())
    claims = {
        "sub": user_id,
        "name": name,
        "roles": roles,
        "advisor_group": advisor_group,
        "region": region,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + ttl_s,
        "jti": f"{user_id}-{now}",
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def authenticate(token: str) -> Principal:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],  # never accept "none" or let the token choose
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError(str(exc)) from exc

    try:
        roles = frozenset(Role(r) for r in claims.get("roles", []))
    except ValueError as exc:
        raise AuthenticationError(f"unknown role: {exc}") from exc
    if not roles:
        raise AuthenticationError("token carries no roles")

    return Principal(
        user_id=claims["sub"],
        name=claims.get("name", claims["sub"]),
        roles=roles,
        advisor_group=claims.get("advisor_group", "wealth"),
        region=claims.get("region", "canada"),
        token_id=claims.get("jti"),
    )
