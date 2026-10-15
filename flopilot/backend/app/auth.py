"""Authentication and authorization.

Demo mode: bearer tokens for seeded local users (documented in README). Tokens are stored
hashed. Enterprise mode is an interface (`IdentityProvider`) to be backed by OIDC/Entra ID;
it is *not* implemented here and refuses to start rather than silently allowing access.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from fastapi import Header

from . import db
from .common import AppError, now_iso
from .config import get_settings

ROLES = {"viewer", "analyst", "admin"}
# Per-role permissions used by the policy controller.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "analyst": {"read", "propose", "approve", "export", "restore"},
    "admin": {"read", "propose", "approve", "export", "restore", "audit"},
}

# Local demo identities. These tokens grant access only to synthetic demo workspaces.
DEMO_USERS = [
    # (user_id, name, token, workspace_id, role)
    ("usr_florina", "Florina (demo analyst)", "demo-florina-token", "ws_demo", "analyst"),
    ("usr_viewer", "Victor (demo viewer)", "demo-viewer-token", "ws_demo", "viewer"),
    ("usr_admin", "Ada (demo admin)", "demo-admin-token", "ws_demo", "admin"),
    ("usr_other", "Oscar (other workspace)", "demo-other-token", "ws_other", "analyst"),
]


@dataclass(frozen=True)
class Principal:
    user_id: str
    name: str
    workspace_id: str
    role: str

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise AppError("forbidden", f"Your role ({self.role}) does not allow '{permission}'.", 403)


class IdentityProvider(Protocol):
    def authenticate(self, bearer_token: str) -> Principal | None: ...


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class DemoIdentityProvider:
    def authenticate(self, bearer_token: str) -> Principal | None:
        row = db.fetchone("SELECT * FROM users WHERE token_hash = ?", (_hash(bearer_token),))
        if not row:
            return None
        return Principal(row["id"], row["name"], row["workspace_id"], row["role"])


class OidcIdentityProvider:  # pragma: no cover - extension point only
    """Placeholder for enterprise identity (OIDC / Microsoft Entra ID). Not implemented."""

    def authenticate(self, bearer_token: str) -> Principal | None:
        raise AppError("auth_not_configured", "Enterprise authentication is not configured.", 501)


def seed_demo_identities() -> None:
    ts = now_iso()
    with db.tx() as conn:
        for ws, name in (("ws_demo", "Demo workspace"), ("ws_other", "Other workspace")):
            conn.execute("INSERT INTO workspaces(id,name,created_at) VALUES(?,?,?) ON CONFLICT(id) DO NOTHING", (ws, name, ts))
        for uid, name, token, ws, role in DEMO_USERS:
            conn.execute(
                "INSERT INTO users(id,name,token_hash,workspace_id,role,created_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(id) DO NOTHING",
                (uid, name, _hash(token), ws, role, ts),
            )


def get_identity_provider() -> IdentityProvider:
    mode = get_settings().auth_mode
    if mode == "demo":
        return DemoIdentityProvider()
    return OidcIdentityProvider()


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthenticated", "Sign in to continue.", 401)
    principal = get_identity_provider().authenticate(authorization.split(" ", 1)[1].strip())
    if principal is None:
        raise AppError("unauthenticated", "Your session is not valid. Sign in again.", 401)
    return principal
