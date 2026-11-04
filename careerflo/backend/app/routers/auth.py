from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from ..config import get_settings
from ..governance.audit import audit
from ..models import User
from ..security.auth import PASSWORD_RE, CurrentUser, DB, hash_password, issue_local_token, provision_user, verify_password
from ..security.ratelimit import client_ip, limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str


@router.get("/config")
def auth_config() -> dict:
    s = get_settings()
    return {"mode": s.auth_mode, "supabase_url": s.supabase_url or None}


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request, db: DB) -> dict:
    s = get_settings()
    if s.auth_mode != "local":
        raise HTTPException(400, "Registration is handled by Supabase Auth in this deployment.")
    limiter.check(f"register:{client_ip(request)}", 5, 3600)  # light abuse control, no fingerprinting
    if not PASSWORD_RE.match(body.password):
        raise HTTPException(422, "Password must be 10–128 characters and include a letter and a number.")
    user = provision_user(db, uuid.uuid4(), body.email, password_hash=hash_password(body.password),
                          verified=s.environment != "production")
    audit(db, user.id, "user", "auth.registered")
    return {"access_token": issue_local_token(user), "token_type": "bearer", "user": _me(user)}


@router.post("/login")
def login(body: Credentials, request: Request, db: DB) -> dict:
    if get_settings().auth_mode != "local":
        raise HTTPException(400, "Sign-in is handled by Supabase Auth in this deployment.")
    limiter.check(f"login:{client_ip(request)}", 10, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    audit(db, user.id, "user", "auth.login")
    return {"access_token": issue_local_token(user), "token_type": "bearer", "user": _me(user)}


def _me(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "is_admin": user.is_admin, "email_verified": user.email_verified,
            "created_at": user.created_at.isoformat() if user.created_at else None}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return _me(user)
