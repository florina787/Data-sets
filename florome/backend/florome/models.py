"""Persistent domain model (SQLAlchemy 2.x; SQLite for local dev, PostgreSQL via FLOROME_DATABASE_URL).

Conventions
-----------
* Every tenant-owned row carries ``tenant_id``; every query in the API layer filters on it.
* ``source_system`` / ``source_ref`` preserve identifiers from the system a record came from.
* Observed facts (``Evidence``) are stored separately from inferred conclusions (``Hypothesis``, ``RCAReport``).
* ``is_demo`` marks synthetic records so they can never be presented as real.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, datetime: DateTime(timezone=True)}


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(10))  # demo | live
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    policy: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list[Any]] = mapped_column(default=list)


class Connection(Base):
    """A configured connector instance. ``status`` is only 'verified' after a successful live health check."""

    __tablename__ = "connections"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("conn"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50))
    connector_type: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="unverified")  # unverified | verified | failed
    capabilities: Mapped[list[Any]] = mapped_column(default=list)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("tenant_id", "connection_id", "source_ref"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    connection_id: Mapped[str | None] = mapped_column(ForeignKey("connections.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(50))  # aws | azure | databricks | github | business | ...
    kind: Mapped[str] = mapped_column(String(50))  # lambda | s3_bucket | databricks_job | app_service | business_process | ...
    name: Mapped[str] = mapped_column(String(200))
    environment: Mapped[str] = mapped_column(String(20), default="prod")
    source_ref: Mapped[str] = mapped_column(String(300))  # identifier in the source system (ARN, job id, ...)
    attributes: Mapped[dict[str, Any]] = mapped_column(default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Dependency(Base):
    """Directed edge: ``source`` feeds / is called by ``target`` (data or call flows source -> target)."""

    __tablename__ = "dependencies"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("dep"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    kind: Mapped[str] = mapped_column(String(50), default="data_flow")
    provenance: Mapped[str] = mapped_column(String(50), default="declared")  # declared | discovered


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("inc"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    severity: Mapped[str] = mapped_column(String(10))  # sev1..sev4
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | investigating | remediating | resolved
    primary_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    detected_at: Mapped[datetime] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    symptoms: Mapped[list[Any]] = mapped_column(default=list)
    source_system: Mapped[str] = mapped_column(String(50), default="florome")
    source_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fingerprint: Mapped[dict[str, Any]] = mapped_column(default=dict)  # learning: set after RCA
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Evidence(Base):
    """An observed fact collected from a connector. Immutable once stored; ``content_hash`` detects tampering."""

    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ev"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    kind: Mapped[str] = mapped_column(String(30))  # log | metric | deployment | config_change | trace | status
    observed_at: Mapped[datetime] = mapped_column()
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source_system: Mapped[str] = mapped_column(String(50))
    source_ref: Mapped[str] = mapped_column(String(300))
    content_hash: Mapped[str] = mapped_column(String(64))
    collected_at: Mapped[datetime] = mapped_column(default=utcnow)
    collected_by: Mapped[str] = mapped_column(String(100))  # connector id
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class RCAReport(Base):
    __tablename__ = "rca_reports"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rca"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    engine_version: Mapped[str] = mapped_column(String(20))
    conclusion_status: Mapped[str] = mapped_column(String(20))
    report: Mapped[dict[str, Any]] = mapped_column(default=dict)
    report_hash: Mapped[str] = mapped_column(String(64))


class Hypothesis(Base):
    """Inferred conclusion. Linked to the evidence that supports or contradicts it."""

    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    rca_id: Mapped[str] = mapped_column(ForeignKey("rca_reports.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(20))  # root_cause | propagation
    title: Mapped[str] = mapped_column(Text)
    candidate_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    status: Mapped[str] = mapped_column(String(20))  # confirmed | probable | inconclusive | disproven
    basis: Mapped[str] = mapped_column(Text)
    tests: Mapped[list[Any]] = mapped_column(default=list)
    supporting_evidence: Mapped[list[Any]] = mapped_column(default=list)
    contradicting_evidence: Mapped[list[Any]] = mapped_column(default=list)


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("plan"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    rca_id: Mapped[str] = mapped_column(ForeignKey("rca_reports.id"))
    # draft | pending_approval | approved | executing | succeeded | failed | rejected | blocked
    status: Mapped[str] = mapped_column(String(30))
    steps: Mapped[list[Any]] = mapped_column(default=list)
    plan_hash: Mapped[str] = mapped_column(String(64))
    risk: Mapped[str] = mapped_column(String(10))
    requires_approval: Mapped[bool] = mapped_column(Boolean)
    policy_decision: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    current_step: Mapped[int] = mapped_column(Integer, default=0)  # durable checkpoint
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic concurrency


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("appr"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("remediation_plans.id"), index=True)
    approver_id: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(10))  # approved | rejected
    plan_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(100), unique=True)  # replay protection
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column()


class ActionExecution(Base):
    __tablename__ = "action_executions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("exec"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("remediation_plans.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[str] = mapped_column(String(64))
    action_id: Mapped[str] = mapped_column(String(100))
    target_resource_id: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20))  # running | succeeded | failed | timed_out
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(default=dict)
    verification: Mapped[dict[str, Any]] = mapped_column(default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[str] = mapped_column(String(64))


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("val"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("remediation_plans.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    passed: Mapped[bool] = mapped_column(Boolean)
    checks: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuditEvent(Base):
    """Append-only, hash-chained audit log (per tenant). ``verify_chain`` detects edits or deletions."""

    __tablename__ = "audit_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: new_id("aud"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    at: Mapped[datetime] = mapped_column(default=utcnow)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(300))
    outcome: Mapped[str] = mapped_column(String(20))  # success | denied | failed | info
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class MCPServerRecord(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mcp"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    transport: Mapped[str] = mapped_column(String(20), default="stdio")
    status: Mapped[str] = mapped_column(String(20), default="registered")  # registered | healthy | unreachable
    server_info: Mapped[dict[str, Any]] = mapped_column(default=dict)
    last_checked: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MCPToolRecord(Base):
    __tablename__ = "mcp_tools"
    __table_args__ = (UniqueConstraint("server_id", "name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tool"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_servers.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)  # sanitized
    input_schema: Mapped[dict[str, Any]] = mapped_column(default=dict)
    schema_hash: Mapped[str] = mapped_column(String(64))  # pinned at review; drift disables the tool
    access: Mapped[str] = mapped_column(String(10))  # read | write
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CostRecord(Base):
    __tablename__ = "cost_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cost"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    period: Mapped[str] = mapped_column(String(10))  # YYYY-MM
    provider: Mapped[str] = mapped_column(String(30))
    account: Mapped[str] = mapped_column(String(100))
    business_unit: Mapped[str] = mapped_column(String(100))
    application: Mapped[str] = mapped_column(String(100))
    ai_component: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source_system: Mapped[str] = mapped_column(String(50))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------------------------------------- engine/session

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(url: str) -> None:
    global _engine, _SessionLocal
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _):  # noqa: ANN001
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(_engine, expire_on_commit=False)


def session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised; call init_engine() first")
    return _SessionLocal


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; normalise everything we read back to aware UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
