"""Flo session isolation. Each chat session has an unguessable id and a bearer token.

This is local session isolation, not user authentication: ConvoLens does not implement
SSO or RBAC (see docs/SECURITY.md).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.orm import ChatSession


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session) -> tuple[str, str]:
    sid = "ses_" + secrets.token_hex(12)
    token = secrets.token_urlsafe(32)
    db.add(ChatSession(id=sid, token_hash=_hash(token)))
    db.commit()
    return sid, token


def verify_session(db: Session, session_id: str, token: str | None) -> None:
    row = db.get(ChatSession, session_id)
    if not row or not token or not hmac.compare_digest(row.token_hash, _hash(token)):
        raise HTTPException(status_code=403, detail="Session not found or token invalid.")


def require_session(
    x_flo_session: str = Header(..., alias="X-Flo-Session"),
    x_flo_token: str = Header(..., alias="X-Flo-Token"),
    db: Session = Depends(get_db),
) -> str:
    verify_session(db, x_flo_session, x_flo_token)
    return x_flo_session
