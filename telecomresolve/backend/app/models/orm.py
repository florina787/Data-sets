"""Persistent entities. All timestamps are stored in UTC.

Reported customer symptoms (Case.reported_symptoms, SupportInteraction.notes)
are kept distinct from measured diagnostics (DiagnosticSample).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, UTCDateTime, utcnow


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class User(Base):
    """Seeded personas. In production, identities come from SSO instead."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    # Account segments this user may access (e.g. ["residential-north"]).
    account_segments: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    # Sensitive contact fields: minimised in API responses and redacted in logs.
    contact_phone: Mapped[str] = mapped_column(String(40))
    contact_email: Mapped[str] = mapped_column(String(200))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    segment: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")
    service_address: Mapped[str] = mapped_column(String(300))
    postal_area: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    product: Mapped[str] = mapped_column(String(64))  # e.g. home_internet
    plan: Mapped[str] = mapped_column(String(64))
    access_technology: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class NetworkAsset(Base):
    __tablename__ = "network_assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32))  # access_node | aggregation_node
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("network_assets.id"), nullable=True)
    postal_area: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ServiceAssetMapping(Base):
    __tablename__ = "service_asset_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("network_assets.id"))
    port: Mapped[str] = mapped_column(String(32))
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    model: Mapped[str] = mapped_column(String(64))
    firmware: Mapped[str] = mapped_column(String(32))
    installed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SupportInteraction(Base):
    __tablename__ = "support_interactions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    summary: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    # Structured record of steps the customer/agent already tried.
    actions_taken: Mapped[list] = mapped_column(JSON, default=list)
    outcome: Mapped[str] = mapped_column(String(64))
    author_type: Mapped[str] = mapped_column(String(32), default="agent")  # agent|customer|analyst


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("network_assets.id"))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(32))  # active | resolved | closed
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Published restoration estimate; None means none has been documented.
    estimated_restoration_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status_history: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class DiagnosticSample(Base):
    __tablename__ = "diagnostic_samples"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    source: Mapped[str] = mapped_column(String(64))  # line_telemetry | cpe_report | on_demand_test
    link_state: Mapped[str] = mapped_column(String(16))  # up | down
    loss_of_signal_events: Mapped[int] = mapped_column(Integer, default=0)
    link_retrains: Mapped[int] = mapped_column(Integer, default=0)  # per sample interval
    packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    snr_margin_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    crc_errors: Mapped[int] = mapped_column(Integer, default=0)
    cpe_uptime_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpe_unexpected_reboots: Mapped[int] = mapped_column(Integer, default=0)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    simulated_post_action: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(32))  # guide | runbook | policy | communication
    authority: Mapped[str] = mapped_column(String(32))  # policy > runbook > guide
    product: Mapped[str] = mapped_column(String(64))
    tenant_scope: Mapped[str] = mapped_column(String(64))  # "*" or tenant id
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list)
    effective_date: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    heading: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    # Populated only when an embedding provider is configured (pgvector path).
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    title: Mapped[str] = mapped_column(String(300))
    complaint_text: Mapped[str] = mapped_column(Text)
    reported_symptoms: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    linked_incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_reason: Mapped[str] = mapped_column(Text, default="")
    workflow_thread_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    active_job: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Demo-only fault injection / post-action telemetry profile for the
    # simulated connectors. Never shown to agents.
    simulation_profile: Mapped[dict] = mapped_column(JSON, default=dict)


class CaseMessage(Base):
    __tablename__ = "case_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    author_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    kind: Mapped[str] = mapped_column(String(32))  # question | clarification | answer
    text: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    generation_mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class EvidenceSnapshot(Base):
    """Immutable bundle of evidence references used for one assessment."""

    __tablename__ = "evidence_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64))
    bundle: Mapped[dict] = mapped_column(JSON)


class EvidenceReference(Base):
    __tablename__ = "evidence_references"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("evidence_snapshots.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(96))
    source_version: Mapped[str] = mapped_column(String(64))
    authority: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))  # observation | statement | policy | note
    excerpt: Mapped[str] = mapped_column(Text)
    freshness: Mapped[str] = mapped_column(String(16))  # fresh | stale | n/a
    supports: Mapped[list] = mapped_column(JSON, default=list)
    opposes: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("evidence_snapshots.id"))
    rank: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(40))
    statement: Mapped[str] = mapped_column(Text)
    sufficiency: Mapped[str] = mapped_column(String(16))  # strong|moderate|weak|insufficient
    supporting_refs: Mapped[list] = mapped_column(JSON, default=list)
    opposing_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("evidence_snapshots.id"))
    action_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(Text)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    uncertainty: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(16))
    approval_requirement: Mapped[dict] = mapped_column(JSON)
    policy_version: Mapped[str] = mapped_column(String(32))
    policy_decision: Mapped[dict] = mapped_column(JSON)
    prior_interventions: Mapped[list] = mapped_column(JSON, default=list)
    refused_requests: Mapped[list] = mapped_column(JSON, default=list)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    proposed_by: Mapped[str] = mapped_column(String(64))
    generation_mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="active")  # active|superseded
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"))
    action_type: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(32))
    evidence_snapshot_id: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    required_roles: Mapped[list] = mapped_column(JSON, default=list)
    separation_of_duties: Mapped[bool] = mapped_column(Boolean, default=False)
    # pending | approved | rejected | expired | consumed | superseded
    status: Mapped[str] = mapped_column(String(16), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    consumed_by_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_exec_idem"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"), unique=True)
    action_type: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    executed_by: Mapped[str] = mapped_column(String(64))
    connector: Mapped[str] = mapped_column(String(64))
    connector_mode: Mapped[str] = mapped_column(String(16))
    # pending | succeeded | failed | unknown (response lost; reconcile)
    status: Mapped[str] = mapped_column(String(16))
    external_ref: Mapped[str | None] = mapped_column(String(96), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class RecoveryObservation(Base):
    __tablename__ = "recovery_observations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("action_executions.id"))
    checked_by: Mapped[str] = mapped_column(String(64))
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)
    window_end: Mapped[datetime] = mapped_column(UTCDateTime)
    sample_ids: Mapped[list] = mapped_column(JSON, default=list)
    healthy_samples: Mapped[int] = mapped_column(Integer)
    unhealthy_samples: Mapped[int] = mapped_column(Integer)
    required_samples: Mapped[int] = mapped_column(Integer)
    customer_report_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(16))  # RESOLVED | MONITORING | ESCALATED
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    simulation_time: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEvent(Base):
    """Append-only (enforced at ORM level; see before_update/delete hooks).

    Each event carries the hash of the previous event in its case chain so
    replay can detect edits made outside the application. This is
    tamper-evident within the prototype, not tamper-proof.
    """

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    actor_id: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    node: Mapped[str | None] = mapped_column(String(40), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generation_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    connector_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    dataset_version: Mapped[str] = mapped_column(String(32))
    generation_mode: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(96))
    summary: Mapped[dict] = mapped_column(JSON)
    results: Mapped[list] = mapped_column(JSON)


class AppendOnlyViolation(RuntimeError):
    pass


@event.listens_for(AuditEvent, "before_update")
def _audit_no_update(mapper, connection, target):  # pragma: no cover - exercised in tests
    raise AppendOnlyViolation("audit_events is append-only")


@event.listens_for(AuditEvent, "before_delete")
def _audit_no_delete(mapper, connection, target):  # pragma: no cover
    raise AppendOnlyViolation("audit_events is append-only")


class SimulatedExternalRecord(Base):
    """Stands in for an external system of record (dispatch, messaging) in
    SIMULATED connector mode, so lost-response reconciliation can be tested."""

    __tablename__ = "simulated_external_records"
    __table_args__ = (UniqueConstraint("system", "idempotency_key", name="uq_sim_ext_idem"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    system: Mapped[str] = mapped_column(String(32))
    tenant_id: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
