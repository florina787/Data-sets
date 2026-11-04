"""Profile, preferences, skills, feature catalogue, plans and usage."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..billing.metering import usage_summary
from ..features import CHAT_LIMITS, FEATURES, PLANS
from ..governance.approvals import request_approval
from ..models import Profile, Skill, UsageEvent, UserPreference
from ..security.auth import CurrentUser, DB

router = APIRouter(prefix="/api", tags=["account"])


class ProfileIn(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    headline: str | None = Field(None, max_length=300)
    location: str | None = Field(None, max_length=200)
    target_titles: list[str] | None = None
    target_salary_min: int | None = Field(None, ge=0, le=5_000_000)
    target_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    github_username: str | None = Field(None, pattern=r"^[A-Za-z0-9-]{1,39}$")
    years_experience: float | None = Field(None, ge=0, le=60)


def _profile(p: Profile) -> dict[str, Any]:
    return {k: getattr(p, k) for k in ("full_name", "headline", "location", "target_titles", "target_salary_min",
                                       "target_currency", "github_username", "years_experience")}


@router.get("/profile")
def get_profile(user: CurrentUser, db: DB) -> dict:
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    skills = db.scalars(select(Skill).where(Skill.user_id == user.id).order_by(Skill.name))
    return {"profile": _profile(p) if p else {}, "skills": [{"id": str(s.id), "name": s.name, "source": s.source} for s in skills]}


@router.put("/profile")
def update_profile(body: ProfileIn, user: CurrentUser, db: DB) -> dict:
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return {"profile": _profile(p)}


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.post("/profile/skills", status_code=201)
def add_skill(body: SkillIn, user: CurrentUser, db: DB) -> dict:
    """User-confirmed skills count as verified facts for matching and tailoring."""
    if db.scalar(select(Skill).where(Skill.user_id == user.id, Skill.name == body.name.strip())):
        raise HTTPException(409, "Skill already in profile")
    s = Skill(user_id=user.id, name=body.name.strip(), source="user", verified=True)
    db.add(s)
    db.commit()
    return {"id": str(s.id), "name": s.name}


@router.delete("/profile/skills/{skill_id}")
def delete_skill(skill_id: str, user: CurrentUser, db: DB) -> dict:
    import uuid

    s = db.get(Skill, uuid.UUID(skill_id))
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Skill not found")
    db.delete(s)
    db.commit()
    return {"deleted": True}


@router.get("/preferences")
def get_prefs(user: CurrentUser, db: DB) -> dict:
    p = db.get(UserPreference, user.id)
    return {"theme": p.theme, "job_alerts": p.job_alerts, "settings": p.settings}


class PrefsIn(BaseModel):
    theme: str | None = Field(None, pattern="^(light|dark|system)$")
    job_alerts: list[dict[str, Any]] | None = Field(None, max_length=20)
    settings: dict[str, Any] | None = None


@router.put("/preferences")
def put_prefs(body: PrefsIn, user: CurrentUser, db: DB) -> dict:
    p = db.get(UserPreference, user.id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return {"theme": p.theme, "job_alerts": p.job_alerts, "settings": p.settings}


@router.get("/features")
def features() -> dict:
    return {"features": [f.__dict__ for f in FEATURES.values()], "chat_limits": CHAT_LIMITS}


@router.get("/plans")
def plans() -> dict:
    return {"plans": [{"id": p.id, "name": p.name, "price_cents": p.price_cents, "currency": p.currency, "interval": "month",
                       "highlights": list(p.highlights), "monthly_limits": p.monthly_limits} for p in PLANS.values()],
            "features": {f.id: f.name for f in FEATURES.values()}}


@router.get("/usage")
def usage(user: CurrentUser, db: DB) -> dict:
    """Server-side trial and plan balances. Read-only: there is no endpoint that modifies counters."""
    return usage_summary(db, user.id)


@router.get("/usage/history")
def usage_history(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(UsageEvent).where(UsageEvent.user_id == user.id).order_by(UsageEvent.created_at.desc()).limit(200))
    return {"events": [{"feature": r.feature_id, "source": r.source, "outcome": r.outcome, "at": r.created_at.isoformat()} for r in rows]}


@router.post("/account/delete-request")
def delete_account_request(user: CurrentUser, db: DB) -> dict:
    req = request_approval(db, user.id, "delete_data", "Delete a record you selected", {"kind": "account"}, "user")
    return {"approval_id": str(req.id), "status": req.status,
            "note": "Full account deletion is processed by support after confirmation (Stripe records are retained as required by law)."}
