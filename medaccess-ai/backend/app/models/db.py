"""SQLAlchemy ORM schema (PostgreSQL in Docker, SQLite for local/test).

Timestamps are stored in UTC. Patient free text (chat messages, symptoms) is not
persisted; search requests store only the service, a coarse location label and
search parameters. Sensitive optional fields use application-level encryption
(see ``app.security.crypto``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TS:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), default="")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("role_id", "permission", name="uq_role_permission"),)


class User(Base, TS):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserPreference(Base, TS):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    default_radius_km: Mapped[int] = mapped_column(Integer, default=25)
    prefer_transit: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_wheelchair_access: Mapped[bool] = mapped_column(Boolean, default=False)
    include_private_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="en-CA")
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_in_app: Mapped[bool] = mapped_column(Boolean, default=True)


class Facility(Base, TS):
    __tablename__ = "facilities"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    facility_type: Mapped[str] = mapped_column(String(40), index=True)
    network: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(30))
    booking_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    booking_capability: Mapped[str] = mapped_column(String(30))
    funding: Mapped[str] = mapped_column(String(30))
    wheelchair_accessible: Mapped[bool] = mapped_column(Boolean)
    transit_score: Mapped[int] = mapped_column(Integer)
    parking: Mapped[bool] = mapped_column(Boolean)
    hours: Mapped[dict] = mapped_column(JSON)
    accepted_requisition_formats: Mapped[list] = mapped_column(JSON)
    integration_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"), index=True)
    data_mode: Mapped[str] = mapped_column(String(30), default="SYNTHETIC")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class FacilityLocation(Base):
    __tablename__ = "facility_locations"
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), primary_key=True)
    address: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(80), index=True)
    neighbourhood: Mapped[str] = mapped_column(String(80))
    postal_code: Mapped[str] = mapped_column(String(10))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(40), default="America/Toronto")
    __table_args__ = (Index("ix_facility_locations_latlon", "latitude", "longitude"),)


class HealthcareService(Base):
    __tablename__ = "healthcare_services"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30))


class FacilityService(Base):
    __tablename__ = "facility_services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("healthcare_services.code"), index=True)
    referral_required: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("facility_id", "service_code", name="uq_facility_service"),)


class ProviderIntegration(Base, TS):
    __tablename__ = "provider_integrations"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    adapter_type: Mapped[str] = mapped_column(String(40))
    reliability: Mapped[float] = mapped_column(Float)
    data_mode: Mapped[str] = mapped_column(String(30))
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class AppointmentSlot(Base, TS):
    __tablename__ = "appointment_slots"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("healthcare_services.code"), index=True)
    start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    source_status: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(ForeignKey("provider_integrations.id"))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (Index("ix_slots_service_start", "service_code", "start_utc"),)


class SlotVerification(Base, TS):
    __tablename__ = "slot_verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[str] = mapped_column(String(40), index=True)
    workflow_id: Mapped[str] = mapped_column(String(40), index=True)
    verification_status: Mapped[str] = mapped_column(String(40))
    build_version: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[list] = mapped_column(JSON)
    data_age_hours: Mapped[float | None] = mapped_column(Float, nullable=True)


class SearchRequest(Base, TS):
    __tablename__ = "search_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(40), index=True)
    service_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    location_label: Mapped[str | None] = mapped_column(String(120), nullable=True)  # coarse label only
    radius_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict)


class SearchResult(Base, TS):
    __tablename__ = "search_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_requests.id", ondelete="CASCADE"), index=True)
    facility_id: Mapped[str] = mapped_column(String(20))
    slot_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40))
    eligibility_status: Mapped[str] = mapped_column(String(40))
    straight_km: Mapped[float] = mapped_column(Float)


class RecommendationRow(Base, TS):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[str] = mapped_column(ForeignKey("search_requests.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(40))
    facility_id: Mapped[str] = mapped_column(String(20))
    slot_id: Mapped[str] = mapped_column(String(40))
    days_until: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_saved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(40))
    build_version: Mapped[str] = mapped_column(String(20))


class RequisitionRequirement(Base):
    __tablename__ = "requisition_requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    service_code: Mapped[str] = mapped_column(ForeignKey("healthcare_services.code"))
    requirement: Mapped[str] = mapped_column(String(60))  # requisition | referral | none
    accepted_formats: Mapped[list] = mapped_column(JSON)
    source_document_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PatientConsent(Base, TS):
    __tablename__ = "patient_consents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(60))  # booking_handoff | notifications | voice | data_sharing
    granted: Mapped[bool] = mapped_column(Boolean)
    scope: Mapped[str] = mapped_column(String(200), default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BookingRequest(Base, TS):
    __tablename__ = "booking_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    facility_id: Mapped[str] = mapped_column(String(20))
    slot_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), index=True)
    approval_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    handoff: Mapped[dict] = mapped_column(JSON, default=dict)
    notes_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class BookingConfirmation(Base, TS):
    """Only populated from a verifiable provider confirmation (never in synthetic mode)."""

    __tablename__ = "booking_confirmations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("booking_requests.id", ondelete="CASCADE"), index=True)
    provider_reference: Mapped[str] = mapped_column(String(120))
    source_integration_id: Mapped[str] = mapped_column(String(30))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base, TS):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkflowExecution(Base, TS):
    __tablename__ = "workflow_executions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    langsmith_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    build_version: Mapped[str] = mapped_column(String(20))
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentExecution(Base, TS):
    __tablename__ = "agent_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(40), index=True)
    agent: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[float] = mapped_column(Float)
    detail: Mapped[str] = mapped_column(Text, default="")
    retries: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)


class ToolExecution(Base, TS):
    __tablename__ = "tool_executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(40), index=True)
    agent: Mapped[str] = mapped_column(String(60))
    tool: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[float] = mapped_column(Float)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ApprovalRequest(Base, TS):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(60), index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(40), default="patient")
    requesting_agent: Mapped[str] = mapped_column(String(60))
    required_role: Mapped[str] = mapped_column(String(40))
    subject_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    consequences: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), index=True, default="PENDING")
    decided_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(Base, TS):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    actor: Mapped[str] = mapped_column(String(60))
    workflow_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(10), default="INFO")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # redacted before write
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class SystemMetric(Base, TS):
    __tablename__ = "system_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelUsage(Base, TS):
    __tablename__ = "model_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)


class IntegrationError(Base, TS):
    __tablename__ = "integration_errors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_id: Mapped[str] = mapped_column(String(30), index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeDocument(Base, TS):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    provider: Mapped[str] = mapped_column(String(120))
    publication_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retrieval_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    version: Mapped[str] = mapped_column(String(20))
    jurisdiction: Mapped[str] = mapped_column(String(40))
    service_type: Mapped[str] = mapped_column(String(40))
    access_classification: Mapped[str] = mapped_column(String(30))
    checksum: Mapped[str] = mapped_column(String(64))
    kb_version: Mapped[str] = mapped_column(String(20))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)


class ReleaseVersion(Base, TS):
    __tablename__ = "release_versions"
    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    status: Mapped[str] = mapped_column(String(30))
    environment: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SdlcArtifact(Base, TS):
    """Auditable artifact produced by an AI-SDLC stage (extension table)."""

    __tablename__ = "sdlc_artifacts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str] = mapped_column(String(60))
    agent: Mapped[str] = mapped_column(String(60))
    trace_ref: Mapped[str] = mapped_column(String(60))  # REQ-/ARCH-/CODE-/TEST-/REL-/MON- id
    content: Mapped[dict] = mapped_column(JSON)
