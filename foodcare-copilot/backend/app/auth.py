"""Local demo accounts with server-side sessions and role checks.

This is NOT enterprise SSO: accounts, passwords and roles are seeded for the
local demo only. Permissions are enforced server-side on every action; the UI
role picker is merely a convenience that logs in with these credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import now_iso, row, session
from app.errors import Forbidden, Unauthorized
from app.records import audit

DEMO_PASSWORD = "demo-only-password"

DEMO_ACCOUNTS = [
    ("USR-MKT", "maya.marketing", "Maya Chen (Marketing)", "marketing"),
    ("USR-PO", "omar.product", "Omar Haddad (Product Owner)", "product_owner"),
    ("USR-ENG", "eli.engineer", "Eli Novak (Engineer)", "engineer"),
    ("USR-REL", "rina.release", "Rina Das (Release Approver)", "release_approver"),
    ("USR-VIEW", "val.viewer", "Val Park (Viewer)", "viewer"),
]

# Action -> roles allowed. Checked server-side for every mutating endpoint.
PERMISSIONS: dict[str, set[str]] = {
    "brief.submit": {"marketing"},
    "clarification.decide": {"marketing", "product_owner"},
    "requirements.approve": {"product_owner"},
    "run.advance": {"engineer", "product_owner", "marketing"},
    "run.control": {"engineer"},
    "release.approve": {"release_approver"},
    "release.deploy": {"release_approver"},
    "release.rollback": {"release_approver"},
    "incident.manage": {"engineer"},
    "fault.inject": {"engineer"},
    "traffic.generate": {"engineer"},
    "demo.control": {"engineer", "release_approver", "product_owner", "marketing"},
}


@dataclass(frozen=True)
class User:
    id: str
    username: str
    display_name: str
    role: str


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()


def seed_accounts() -> None:
    with session() as conn:
        for user_id, username, display, role in DEMO_ACCOUNTS:
            salt = secrets.token_hex(16)
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, display_name, role, password_hash, salt)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, display, role, _hash(DEMO_PASSWORD, salt), salt),
            )


def login(username: str, password: str) -> tuple[str, User]:
    found = row("SELECT * FROM users WHERE username = ?", (username,))
    if not found or not hmac.compare_digest(found["password_hash"], _hash(password, found["salt"])):
        audit(username or "anonymous", "auth.login", outcome="rejected")
        raise Unauthorized("Invalid demo credentials")
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=get_settings().session_hours)
    with session() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), found["id"], now_iso(),
             expires.isoformat()),
        )
    user = User(found["id"], found["username"], found["display_name"], found["role"])
    audit(user.username, "auth.login")
    return token, user


def logout(token: str) -> None:
    with session() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),)
        )


def user_for_token(token: str | None) -> User:
    if not token:
        raise Unauthorized("Sign in with a demo account")
    found = row(
        "SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ?",
        (hashlib.sha256(token.encode()).hexdigest(),),
    )
    if not found or datetime.fromisoformat(found["expires_at"]) < datetime.now(timezone.utc):
        raise Unauthorized("Session expired or invalid")
    return User(found["id"], found["username"], found["display_name"], found["role"])


def require(user: User, action: str, entity_type: str | None = None, entity_id: str | None = None):
    """Raise Forbidden (and record the rejected attempt) unless the role may act."""
    if user.role not in PERMISSIONS[action]:
        audit(user.username, action, outcome="rejected", entity_type=entity_type,
              entity_id=entity_id, reason=f"role '{user.role}' not permitted")
        raise Forbidden(
            f"Role '{user.role}' is not permitted to perform {action}",
            required_roles=sorted(PERMISSIONS[action]),
        )
