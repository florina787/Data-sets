"""Request dependencies: database session, authentication, tenant-scoped lookups."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from florome.context import AppContext
from florome.models import Tenant, User, session_factory
from florome.security.rbac import Principal

T = TypeVar("T")


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_principal(authorization: str | None = Header(default=None), db: Session = Depends(get_db),
                  ctx: AppContext = Depends(get_ctx)) -> Principal:
    """Demo mode: bearer tokens issued per demo user at seed time. Live mode needs an OIDC provider, which is not
    implemented yet, so live tenants cannot authenticate (fails closed)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    token = authorization.split(" ", 1)[1].strip()
    user_id = ctx.demo_tokens.get(token)
    if user_id is None:
        raise HTTPException(401, "Invalid token (live OIDC authentication is not implemented; only demo tokens are accepted)")
    user = db.get(User, user_id)
    tenant = db.get(Tenant, user.tenant_id) if user else None
    if user is None or tenant is None or tenant.mode != "demo":
        raise HTTPException(401, "Token is not valid for this tenant")
    return Principal(user.id, user.tenant_id, user.name, tuple(user.roles))


def require(permission: str):  # noqa: ANN201
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if not p.can(permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return p

    return dep


def owned(db: Session, model: type[T], obj_id: str, p: Principal) -> T:
    """Fetch a tenant-owned row. Rows of other tenants are indistinguishable from missing ones (404)."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "tenant_id", None) != p.tenant_id:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj
