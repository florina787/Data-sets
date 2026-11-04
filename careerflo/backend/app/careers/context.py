"""Shared loaders that always scope by user_id (ownership enforced in one place)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs.normalize import to_dict
from ..models import Job, Profile, Resume, Skill


class NotFound(LookupError):
    pass


def as_uuid(value: str | uuid.UUID, what: str = "id") -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFound(f"Invalid {what}") from exc


def get_resume(db: Session, user_id: uuid.UUID, resume_id: str | None = None) -> Resume:
    if resume_id:
        r = db.get(Resume, as_uuid(resume_id, "resume id"))
        if r is None or r.user_id != user_id:
            raise NotFound("Resume not found")
        return r
    r = db.scalar(select(Resume).where(Resume.user_id == user_id).order_by(Resume.is_primary.desc(), Resume.created_at.desc()))
    if r is None:
        raise NotFound("No resume uploaded yet. Upload one in Resume Studio first.")
    return r


def get_job(db: Session, job_id: str) -> dict[str, Any]:
    j = db.get(Job, as_uuid(job_id, "job id"))
    if j is None:
        raise NotFound("Job not found")
    return to_dict(j) | {"description": j.description}


def candidate_profile(db: Session, user_id: uuid.UUID, resume: Resume | None = None) -> dict[str, Any]:
    prof = db.scalar(select(Profile).where(Profile.user_id == user_id))
    skills = [s.name for s in db.scalars(select(Skill).where(Skill.user_id == user_id, Skill.verified.is_(True)))]
    if resume is None:
        try:
            resume = get_resume(db, user_id)
        except NotFound:
            resume = None
    if resume is not None:
        for s in resume.parsed.get("skills", []):
            if s.lower() not in {x.lower() for x in skills}:
                skills.append(s)
    yrs = (prof.years_experience if prof and prof.years_experience is not None else None) or \
        (resume.parsed.get("years_experience") if resume else None)
    return {"skills": skills, "years_experience": yrs, "location": prof.location if prof else None,
            "target_salary_min": prof.target_salary_min if prof else None,
            "target_currency": prof.target_currency if prof else None,
            "preferred_arrangement": None, "has_resume": resume is not None}
