"""Career analytics computed from the user's own records."""
from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Application, ApplicationEvent, Interview, Job, JobMatch, Recruiter, RecruiterInteraction, SavedJob, Skill
from .salary import salary_distribution

FUNNEL = ["applied", "screening", "interviewing", "offer", "accepted"]
REACHED = {"applied": 0, "screening": 1, "interviewing": 2, "offer": 3, "accepted": 4, "rejected": 0, "withdrawn": 0, "draft": -1}


def application_metrics(apps: list[Application]) -> dict[str, Any]:
    submitted = [a for a in apps if a.status != "draft"]
    reached = Counter()
    for a in submitted:
        lvl = REACHED.get(a.status, 0)
        for i, stage in enumerate(FUNNEL):
            if i <= lvl:
                reached[stage] += 1
    n = len(submitted) or 1
    return {"total": len(apps), "submitted": len(submitted), "by_status": dict(Counter(a.status for a in apps)),
            "funnel": [{"stage": s, "count": reached[s]} for s in FUNNEL],
            "response_rate": round(reached["screening"] / n, 3) if submitted else 0.0,
            "interview_rate": round(reached["interviewing"] / n, 3) if submitted else 0.0,
            "offer_rate": round(reached["offer"] / n, 3) if submitted else 0.0}


def interview_conversion(interviews: list[Interview], apps: list[Application]) -> dict[str, Any]:
    real = [i for i in interviews if i.kind == "real"]
    mock = [i for i in interviews if i.kind == "mock" and i.score is not None]
    offers = sum(1 for a in apps if a.status in ("offer", "accepted"))
    return {"real_interviews": len(real), "mock_sessions": len(mock),
            "avg_mock_score": round(sum(i.score for i in mock) / len(mock), 1) if mock else None,
            "mock_trend": [{"date": i.created_at.date().isoformat(), "score": i.score, "topic": i.topic} for i in sorted(mock, key=lambda x: x.created_at)],
            "interview_to_offer": round(offers / len(real), 3) if real else None}


def skill_gaps(user_skills: list[str], jobs: list[dict[str, Any]], top: int = 12) -> list[dict[str, Any]]:
    have = {s.lower() for s in user_skills}
    demand = Counter(s for j in jobs for s in j.get("required_skills") or [])
    return [{"skill": s, "demand": c, "have": s.lower() in have} for s, c in demand.most_common(40) if s.lower() not in have][:top]


def dashboard(db: Session, user_id: uuid.UUID, include_synthetic: bool = True) -> dict[str, Any]:
    def owned(model):
        stmt = select(model).where(model.user_id == user_id)
        if not include_synthetic and hasattr(model, "is_synthetic"):
            stmt = stmt.where(model.is_synthetic.is_(False))
        return list(db.scalars(stmt))

    apps = owned(Application)
    interviews = owned(Interview)
    saved = owned(SavedJob)
    matches = owned(JobMatch)
    recruiters = owned(Recruiter)
    interactions = owned(RecruiterInteraction)
    skills = [s.name for s in owned(Skill)]
    job_ids = {s.job_id for s in saved} | {a.job_id for a in apps if a.job_id}
    jobs = [j for j in db.scalars(select(Job).where(Job.id.in_(job_ids)))] if job_ids else []
    from ..jobs.normalize import to_dict

    jd = [to_dict(j) | {"description_snippet": ""} for j in jobs]
    if not jd:
        jd = [to_dict(j) for j in db.scalars(select(Job).order_by(Job.retrieved_at.desc()).limit(200))]
    timeline = Counter(a.applied_at.isoformat()[:7] for a in apps if a.applied_at)
    events = list(db.scalars(select(ApplicationEvent).where(ApplicationEvent.user_id == user_id)
                             .where(ApplicationEvent.kind == "followup_scheduled")))
    match_hist = Counter(int(m.score // 10 * 10) for m in matches)
    return {
        "jobs_discovered": db.query(Job).count(),
        "saved_jobs": len(saved),
        "applications": application_metrics(apps),
        "interviews": interview_conversion(interviews, apps),
        "offers": sum(1 for a in apps if a.status in ("offer", "accepted")),
        "salary_distribution": salary_distribution(jd),
        "match_distribution": [{"bucket": f"{b}-{b + 9}", "count": match_hist[b]} for b in range(0, 100, 10)],
        "skill_gaps": skill_gaps(skills, jd),
        "recruiter_activity": {"recruiters": len(recruiters), "interactions": len(interactions),
                               "by_channel": dict(Counter(i.channel for i in interactions))},
        "application_timeline": [{"month": k, "count": v} for k, v in sorted(timeline.items())],
        "upcoming_followups": len(events),
        "contains_synthetic": any(getattr(a, "is_synthetic", False) for a in apps),
    }
