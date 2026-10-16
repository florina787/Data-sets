"""Authentication & RBAC.

Demo mode issues short-lived HS256 JWTs for the seeded synthetic users via
``/auth/demo-login``. OAuth 2.0 / OIDC (authorization-code + PKCE against an
external IdP) is the planned production path; ``OIDC_ISSUER`` configuration is
accepted but token validation against JWKS is NOT implemented yet, so demo login
is refused in staging/production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import get_settings, jwt_secret_value
from app.database.session import DEMO_USERS, ROLE_PERMISSIONS

_bearer = HTTPBearer(auto_error=False)
ALG = "HS256"


@dataclass
class Principal:
    user_id: str
    role: str
    display_name: str

    @property
    def permissions(self) -> set[str]:
        return ROLE_PERMISSIONS.get(self.role, set())


def issue_token(user_id: str) -> dict:
    s = get_settings()
    if s.is_production_like:
        raise HTTPException(403, "Demo login is disabled outside demo/development environments.")
    user = next((u for u in DEMO_USERS if u[0] == user_id), None)
    if user is None:
        raise HTTPException(404, "Unknown demo user")
    now = int(time.time())
    claims = {"sub": user[0], "role": user[3], "name": user[2], "iat": now, "exp": now + s.jwt_ttl_minutes * 60,
              "iss": "medaccess-demo", "aud": "medaccess-api"}
    return {"access_token": jwt.encode(claims, jwt_secret_value(s), algorithm=ALG), "token_type": "bearer",
            "expires_in": s.jwt_ttl_minutes * 60, "user": {"id": user[0], "role": user[3], "name": user[2],
                                                           "permissions": sorted(ROLE_PERMISSIONS[user[3]])}}


def decode(token: str) -> Principal:
    try:
        c = jwt.decode(token, jwt_secret_value(get_settings()), algorithms=[ALG], audience="medaccess-api",
                       issuer="medaccess-demo")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {type(e).__name__}") from e
    if c.get("role") not in ROLE_PERMISSIONS:
        raise HTTPException(401, "Invalid role")
    return Principal(c["sub"], c["role"], c.get("name", ""))


def current_user(request: Request, cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if cred is None:
        raise HTTPException(401, "Authentication required")
    p = decode(cred.credentials)
    request.state.user_id = p.user_id
    return p


def optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal | None:
    return decode(cred.credentials) if cred else None


def require(permission: str):
    def dep(p: Principal = Depends(current_user)) -> Principal:
        if permission not in p.permissions:
            raise HTTPException(403, f"Missing permission: {permission}")
        return p
    return dep
