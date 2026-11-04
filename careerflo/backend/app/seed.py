"""Reference data (always) and clearly-labelled synthetic demo data (on request)."""
from __future__ import annotations

import random
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .careers.resume import parse_resume
from .features import FEATURES, PLANS
from .jobs.search import SOURCES, upsert_jobs
from .jobs.synthetic import synthetic_jobs
from .models import (AgentRun, Application, ApplicationEvent, FeatureCatalog, FeatureEntitlement, Interview, JobSource, Recruiter,
                     RecruiterInteraction, Resume, Skill, SubscriptionPlan, User, utcnow)
from .security.auth import email_hash, hash_password

SAMPLE_RESUME = """Jordan Rivera (Synthetic Demo)
jordan.rivera@example.com | +1 416 555 0100 | github.com/example-demo

SUMMARY
AI engineer building production LLM applications with Python, RAG and LangGraph.

EXPERIENCE
Senior AI Engineer, Maple Circuit Labs (Demo) — Jan 2021 – Present
• Built a RAG assistant with LangGraph and pgvector serving 40,000 monthly users
• Reduced LLM inference cost by 35% by routing simple requests to a smaller model
• Led a team of 4 engineers delivering MCP-based tool integrations with FastAPI
• Deployed services with Docker and Kubernetes on AWS using GitHub Actions CI/CD

Machine Learning Engineer, Northwind Analytics (Demo) — Jun 2017 – Dec 2020
• Trained PyTorch NLP models for document classification with 92% accuracy
• Built data pipelines in Python, SQL and Airflow processing 2 million records daily
• Partnered with customer-facing teams to deploy models for 12 enterprise clients

EDUCATION
BSc Computer Science, University of Toronto, 2017

SKILLS
Python, SQL, PyTorch, LLMs, RAG, LangGraph, MCP, FastAPI, Docker, Kubernetes, AWS, CI/CD, Airflow, NLP, Communication, Leadership

CERTIFICATIONS
AWS Certified Solutions Architect – Associate
"""


def seed_reference(db: Session) -> None:
    for f in FEATURES.values():
        db.merge(FeatureCatalog(id=f.id, name=f.name, description=f.description, unit=f.unit, trial_limit=f.trial_limit,
                                est_cost_cents=f.est_cost_cents))
    for p in PLANS.values():
        db.merge(SubscriptionPlan(id=p.id, name=p.name, price_cents=p.price_cents, currency=p.currency, priority=p.priority))
    db.flush()
    for p in PLANS.values():
        for fid in FEATURES:
            db.merge(FeatureEntitlement(plan_id=p.id, feature_id=fid, monthly_limit=p.monthly_limits.get(fid, 0)))
    for sid, meta in SOURCES.items():
        db.merge(JobSource(id=sid, name=meta["name"], kind=meta["kind"], terms_url=meta["terms_url"]))
    db.commit()


def seed_demo(db: Session, email: str = "demo@careerflo.example", password: str = "DemoPassword123") -> User:
    """Synthetic demo account: 100 jobs, 25 applications, 15 recruiters, a sample resume, interviews and agent traces."""
    rng = random.Random(7)
    user = db.scalar(select(User).where(User.email == email))
    if user:
        return user
    user = User(id=uuid.uuid4(), email=email, email_canonical_hash=email_hash(email), password_hash=hash_password(password),
                email_verified=True, is_demo=True)
    db.add(user)
    db.flush()  # parent row first (no ORM relationships define insert order)
    from .models import Profile, UserPreference

    db.add(Profile(user_id=user.id, full_name="Jordan Rivera (Synthetic Demo)", headline="Senior AI Engineer", location="Toronto, ON",
                   target_titles=["Senior AI Engineer", "Forward Deployed AI Engineer"], target_salary_min=150000, target_currency="CAD"))
    db.add(UserPreference(user_id=user.id))
    db.flush()
    parsed = parse_resume(SAMPLE_RESUME)
    db.add(Resume(user_id=user.id, title="Sample resume (synthetic)", original_filename="sample.txt", mime_type="text/plain",
                  original_text=SAMPLE_RESUME, parsed=parsed, is_primary=True, is_synthetic=True))
    for s in parsed["taxonomy_skills"]:
        db.add(Skill(user_id=user.id, name=s, source="resume"))
    jobs = upsert_jobs(db, synthetic_jobs())
    statuses = ["draft"] * 3 + ["applied"] * 9 + ["screening"] * 5 + ["interviewing"] * 4 + ["offer"] * 2 + ["rejected"] * 2
    now = utcnow()
    apps = []
    for i, st in enumerate(statuses):
        j = jobs[i * 3]
        a = Application(user_id=user.id, job_id=j.id, company=j.company, title=j.title, status=st, is_synthetic=True,
                        applied_at=(now - timedelta(days=rng.randint(2, 90))).date() if st != "draft" else None)
        db.add(a)
        apps.append(a)
    db.flush()
    for a in apps:
        if a.status == "interviewing":
            db.add(Interview(user_id=user.id, application_id=a.id, kind="real", role=a.title, is_synthetic=True,
                             scheduled_at=now + timedelta(days=rng.randint(1, 14))))
            db.add(ApplicationEvent(user_id=user.id, application_id=a.id, kind="followup_scheduled", detail={"note": "Send thank-you note"},
                                    due_at=now + timedelta(days=rng.randint(1, 10))))
    for k in range(6):
        db.add(Interview(user_id=user.id, kind="mock", role="Senior AI Engineer", topic=rng.choice(["rag", "system_design", "behavioral"]),
                         status="completed", score=round(5 + k * 0.6 + rng.random(), 1), is_synthetic=True,
                         created_at=now - timedelta(days=30 - k * 5)))
    first = ["Avery", "Sam", "Priya", "Lucas", "Mei", "Omar", "Elena", "Noah", "Zara", "Kai", "Ines", "Theo", "Hana", "Ravi", "Lea"]
    for i, name in enumerate(first):
        r = Recruiter(user_id=user.id, name=f"{name} Example (Demo)", company=jobs[i * 5].company, email=f"{name.lower()}@example.com",
                      is_synthetic=True)
        db.add(r)
        db.flush()
        for d in range(rng.randint(0, 3)):
            db.add(RecruiterInteraction(user_id=user.id, recruiter_id=r.id, channel=rng.choice(["email", "linkedin", "call"]),
                                        direction=rng.choice(["inbound", "outbound"]), summary="Synthetic demo interaction",
                                        occurred_at=now - timedelta(days=rng.randint(1, 40))))
    for k in range(5):
        db.add(AgentRun(user_id=user.id, intent=rng.choice(["job_discovery", "multi_agent", "interview"]),
                        agents=["job_discovery", "job_matching"], status="completed", duration_ms=rng.randint(400, 6000), is_synthetic=True,
                        steps=[{"agent": "supervisor"}, {"agent": "job_discovery", "tool": "jobs.search_all_jobs", "ms": 120},
                               {"agent": "governance", "status": "ok"}]))
    db.commit()
    return user
