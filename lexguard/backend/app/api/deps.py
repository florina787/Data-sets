"""Request identity. DEMO: the user is selected with the X-LexGuard-User header.
Production: replace with SSO/OIDC; every downstream control uses the resolved user only."""

from __future__ import annotations

import re

from fastapi import Header, HTTPException

from app.models.domain import User
from app.services.data_store import get_store

USER_RE = re.compile(r"^U-\d{3}$")


def current_user(x_lexguard_user: str = Header(default="U-002", alias="X-LexGuard-User")) -> User:
    if not USER_RE.match(x_lexguard_user or ""):
        raise HTTPException(status_code=401, detail="Invalid user identifier.")
    user = get_store().users.get(x_lexguard_user)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user.")
    return user
