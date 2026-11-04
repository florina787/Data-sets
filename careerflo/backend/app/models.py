"""Database schema for Career_flo AI.

Every user-owned table carries ``user_id`` and is protected twice:
1. The API layer always filters by the authenticated user's id (see ``app/security/auth.py``).
2. On Supabase/PostgreSQL, row-level security policies (``migrations/versions/0002_rls.py``)
   restrict rows to ``auth.uid()`` for any direct client access.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OwnedMixin(TimestampMixin):
    """A row that belongs to exactly one user."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)


def user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)


# ---------------------------------------------------------------- identity
class User(TimestampMixin, Base):
    __tablename__ = "users"
    # Equals the Supabase auth.users id in production.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Hash of a canonicalised email (lower-case, +tags and gmail dots removed). Lets us refuse
    # re-registration with an alias of an existing address without storing anything extra.
    email_canonical_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))  # local auth mode only
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    headline: Mapped[str | None] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200))
    target_titles: Mapped[list[str]] = mapped_column(JSONType, default=list)
    target_salary_min: Mapped[int | None] = mapped_column(Integer)
    target_currency: Mapped[str | None] = mapped_column(String(3))
    github_username: Mapped[str | None] = mapped_column(String(100))
    years_experience: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Skill(OwnedMixin, Base):
    __tablename__ = "skills"
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(30), default="resume")  # resume | user
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_skill_user_name"),)


class Experience(OwnedMixin, Base):
    __tablename__ = "experience"
    user_id: Mapped[uuid.UUID] = user_fk()
    employer: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    bullets: Mapped[list[str]] = mapped_column(JSONType, default=list)


class Education(OwnedMixin, Base):
    __tablename__ = "education"
    user_id: Mapped[uuid.UUID] = user_fk()
    institution: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str | None] = mapped_column(String(200))
    year: Mapped[str | None] = mapped_column(String(20))


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), default="system")
    job_alerts: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


# ---------------------------------------------------------------- resumes
class Resume(OwnedMixin, Base):
    __tablename__ = "resumes"
    user_id: Mapped[uuid.UUID] = user_fk()
    title: Mapped[str] = mapped_column(String(200))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    original_text: Mapped[str] = mapped_column(Text)  # never modified after upload
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ResumeVersion(OwnedMixin, Base):
    __tablename__ = "resume_versions"
    user_id: Mapped[uuid.UUID] = user_fk()
    resume_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict[str, Any]] = mapped_column(JSONType)
    text: Mapped[str] = mapped_column(Text)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


# ---------------------------------------------------------------- jobs
class JobSource(TimestampMixin, Base):
    __tablename__ = "job_sources"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # jsearch, adzuna, greenhouse...
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))  # aggregator | ats_board | synthetic
    terms_url: Mapped[str | None] = mapped_column(String(500))
    daily_quota: Mapped[int] = mapped_column(Integer, default=200)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class EmployerBoard(TimestampMixin, Base):
    __tablename__ = "employer_boards"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(String(40), ForeignKey("job_sources.id"))
    board_token: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("source_id", "board_token", name="uq_board"),)


class Job(TimestampMixin, Base):
    """A normalised posting. Shared catalogue (not user-owned): it only holds public posting data."""

    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_job_id: Mapped[str] = mapped_column(String(300))
    origin_publisher: Mapped[str | None] = mapped_column(String(100))  # e.g. LinkedIn, Indeed via JSearch
    dedupe_key: Mapped[str] = mapped_column(String(64), index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    work_arrangement: Mapped[str | None] = mapped_column(String(20))  # remote | hybrid | onsite
    employment_type: Mapped[str | None] = mapped_column(String(40))
    seniority: Mapped[str | None] = mapped_column(String(40))
    industry: Mapped[str | None] = mapped_column(String(100))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(10))
    salary_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # published by the source
    description: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    __table_args__ = (UniqueConstraint("source", "source_job_id", name="uq_job_source_id"),)


class SavedJob(OwnedMixin, Base):
    __tablename__ = "saved_jobs"
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_saved_job"),)


class JobMatch(OwnedMixin, Base):
    __tablename__ = "job_matches"
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"))
    resume_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("resumes.id", ondelete="SET NULL"))
    score: Mapped[float] = mapped_column(Float)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONType)


# ---------------------------------------------------------------- applications / CRM
class Application(OwnedMixin, Base):
    __tablename__ = "applications"
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="SET NULL"))
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    applied_at: Mapped[date | None] = mapped_column(Date)
    salary_offered: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','applied','screening','interviewing','offer','accepted','rejected','withdrawn')",
            name="ck_application_status",
        ),
    )


class ApplicationEvent(OwnedMixin, Base):
    __tablename__ = "application_events"
    user_id: Mapped[uuid.UUID] = user_fk()
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # status_change | note | followup_scheduled | ...
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Interview(OwnedMixin, Base):
    __tablename__ = "interviews"
    user_id: Mapped[uuid.UUID] = user_fk()
    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("applications.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(30))  # real | mock
    topic: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(200))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|in_progress|completed
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Recruiter(OwnedMixin, Base):
    __tablename__ = "recruiters"
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class RecruiterInteraction(OwnedMixin, Base):
    __tablename__ = "recruiter_interactions"
    user_id: Mapped[uuid.UUID] = user_fk()
    recruiter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("recruiters.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(30))  # email | call | linkedin | meeting
    direction: Mapped[str] = mapped_column(String(10))  # inbound | outbound
    summary: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Portfolio(OwnedMixin, Base):
    __tablename__ = "portfolios"
    user_id: Mapped[uuid.UUID] = user_fk()
    github_username: Mapped[str] = mapped_column(String(100))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PortfolioProject(OwnedMixin, Base):
    __tablename__ = "portfolio_projects"
    user_id: Mapped[uuid.UUID] = user_fk()
    portfolio_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    languages: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    topics: Mapped[list[str]] = mapped_column(JSONType, default=list)
    stars: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------- conversations / agents
class Conversation(OwnedMixin, Base):
    __tablename__ = "conversations"
    user_id: Mapped[uuid.UUID] = user_fk()
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | closed
    closed_reason: Mapped[str | None] = mapped_column(String(100))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    metered: Mapped[bool] = mapped_column(Boolean, default=False)  # counted against a trial/quota


class Message(OwnedMixin, Base):
    __tablename__ = "messages"
    user_id: Mapped[uuid.UUID] = user_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # cards, charts, citations
    tokens: Mapped[int] = mapped_column(Integer, default=0)


class AgentRun(OwnedMixin, Base):
    __tablename__ = "agent_runs"
    user_id: Mapped[uuid.UUID] = user_fk()
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="SET NULL"))
    intent: Mapped[str] = mapped_column(String(60))
    agents: Mapped[list[str]] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|completed|failed|awaiting_approval
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class McpToolCall(OwnedMixin, Base):
    __tablename__ = "mcp_tool_calls"
    user_id: Mapped[uuid.UUID] = user_fk()
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    server: Mapped[str] = mapped_column(String(60))
    tool: Mapped[str] = mapped_column(String(80))
    tool_version: Mapped[str] = mapped_column(String(20))
    agent: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))  # ok | error | denied | timeout
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # redacted
    error: Mapped[str | None] = mapped_column(Text)


class ApprovalRequest(OwnedMixin, Base):
    __tablename__ = "approval_requests"
    user_id: Mapped[uuid.UUID] = user_fk()
    action: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|executed
    requested_by: Mapped[str] = mapped_column(String(60))  # agent name or "user"
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor: Mapped[str] = mapped_column(String(60))  # user | agent:<name> | system | stripe
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str | None] = mapped_column(String(200))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    severity: Mapped[str] = mapped_column(String(10), default="info")


class InferenceMetric(TimestampMixin, Base):
    __tablename__ = "inference_metrics"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(String(60))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_per_second: Mapped[float | None] = mapped_column(Float)
    queue_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- billing
class SubscriptionPlan(TimestampMixin, Base):
    __tablename__ = "subscription_plans"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # free | pro | premium
    name: Mapped[str] = mapped_column(String(60))
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    interval: Mapped[str] = mapped_column(String(10), default="month")
    stripe_price_id: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class FeatureCatalog(TimestampMixin, Base):
    __tablename__ = "feature_catalog"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(40))
    trial_limit: Mapped[int] = mapped_column(Integer, default=2)
    est_cost_cents: Mapped[float] = mapped_column(Float, default=0.0)


class FeatureEntitlement(TimestampMixin, Base):
    __tablename__ = "feature_entitlements"
    plan_id: Mapped[str] = mapped_column(String(20), ForeignKey("subscription_plans.id"), primary_key=True)
    feature_id: Mapped[str] = mapped_column(String(60), ForeignKey("feature_catalog.id"), primary_key=True)
    monthly_limit: Mapped[int] = mapped_column(Integer, default=0)


class StripeCustomer(TimestampMixin, Base):
    __tablename__ = "stripe_customers"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(100), unique=True)
    livemode: Mapped[bool] = mapped_column(Boolean, default=False)


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID] = user_fk()
    stripe_subscription_id: Mapped[str] = mapped_column(String(100), unique=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(100), index=True)
    plan_id: Mapped[str] = mapped_column(String(20), ForeignKey("subscription_plans.id"))
    status: Mapped[str] = mapped_column(String(30))  # stripe status
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Stripe "created" timestamp of the newest event applied; older events are ignored.
    last_event_at: Mapped[int] = mapped_column(Integer, default=0)
    livemode: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StripeEvent(TimestampMixin, Base):
    __tablename__ = "stripe_events"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # evt_... (idempotency)
    type: Mapped[str] = mapped_column(String(80))
    stripe_created: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="processed")  # processed | ignored | failed
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class Invoice(TimestampMixin, Base):
    """Payment history mirrored from Stripe webhooks (invoice.paid / payment_failed / refunds)."""

    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # in_...
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20))  # paid | failed | refunded
    amount_cents: Mapped[int] = mapped_column(Integer)
    amount_refunded_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    hosted_invoice_url: Mapped[str | None] = mapped_column(String(1000))
    plan_id: Mapped[str | None] = mapped_column(String(20))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    livemode: Mapped[bool] = mapped_column(Boolean, default=False)


class TrialUsage(Base):
    __tablename__ = "trial_usage"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    feature_id: Mapped[str] = mapped_column(String(60), ForeignKey("feature_catalog.id"), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (
        CheckConstraint("used >= 0 AND reserved >= 0", name="ck_trial_nonneg"),
        CheckConstraint("used + reserved <= 2", name="ck_trial_max_two"),
    )


class MonthlyUsage(Base):
    __tablename__ = "monthly_usage"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    feature_id: Mapped[str] = mapped_column(String(60), ForeignKey("feature_catalog.id"), primary_key=True)
    period: Mapped[str] = mapped_column(String(7), primary_key=True)  # YYYY-MM
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __table_args__ = (CheckConstraint("used >= 0 AND reserved >= 0", name="ck_monthly_nonneg"),)


class UsageReservation(TimestampMixin, Base):
    __tablename__ = "usage_reservations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID] = user_fk()
    feature_id: Mapped[str] = mapped_column(String(60), ForeignKey("feature_catalog.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(10))  # trial | plan
    period: Mapped[str | None] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(12), default="reserved")  # reserved | committed
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "feature_id", "idempotency_key", name="uq_reservation_idem"),
        Index("ix_reservation_status_created", "status", "created_at"),
    )


class UsageEvent(TimestampMixin, Base):
    __tablename__ = "usage_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID] = user_fk()
    feature_id: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(10))
    outcome: Mapped[str] = mapped_column(String(20))  # consumed | released | denied | replayed
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class BillingAuditLog(TimestampMixin, Base):
    __tablename__ = "billing_audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class ProviderUsage(Base):
    """Daily request counter per external job provider (quota enforcement)."""

    __tablename__ = "provider_usage"
    source_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)


class SearchCache(TimestampMixin, Base):
    __tablename__ = "search_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40))
    job_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
