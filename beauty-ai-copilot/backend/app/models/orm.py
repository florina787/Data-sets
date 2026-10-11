"""Persistent information model (SQLAlchemy 2.x). Works on SQLite (default) and PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list] = mapped_column(JSON, default=list)
    persona: Mapped[str] = mapped_column(String(100))


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(String(64), default="foundation_shade")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    current_requirement_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baseline_model_id: Mapped[str] = mapped_column(String(100))
    candidate_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code_revision_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dataset_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evaluation_config_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latest_evaluation_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    impact_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    deployment_target: Mapped[str] = mapped_column(String(100), default="sim-eu-web-shade-finder")
    trace_id: Mapped[str] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_no}


class RequirementVersion(Base):
    __tablename__ = "requirement_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    statement: Mapped[str] = mapped_column(Text)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")  # DRAFT | APPROVED | SUPERSEDED
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("change_id", "version"),)


class Clarification(Base):
    __tablename__ = "clarifications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    owner_role: Mapped[str] = mapped_column(String(64))
    suggested_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)


class AcceptanceCriterion(Base):
    __tablename__ = "acceptance_criteria"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement_version_id: Mapped[str] = mapped_column(ForeignKey("requirement_versions.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class EvidenceReference(Base):
    __tablename__ = "evidence_references"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(100))
    source_version: Mapped[str] = mapped_column(String(30))
    section: Mapped[str] = mapped_column(String(100))
    excerpt: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retrieved_by: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(200))
    validation_status: Mapped[str] = mapped_column(String(30), default="VALID")  # VALID | OUTDATED | CONFLICT | UNRESOLVED
    flags: Mapped[list] = mapped_column(JSON, default=list)


class ImpactAssessment(Base):
    __tablename__ = "impact_assessments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    requirement_version_id: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    accepted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CodeRevision(Base):
    __tablename__ = "code_revisions"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    author_user_id: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    diff: Mapped[str] = mapped_column(Text)
    diff_digest: Mapped[str] = mapped_column(String(80))
    requirement_refs: Mapped[list] = mapped_column(JSON, default=list)
    test_refs: Mapped[list] = mapped_column(JSON, default=list)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(40))
    role: Mapped[str] = mapped_column(String(40))
    artifact_digest: Mapped[str] = mapped_column(String(80))
    artifact_uri: Mapped[str] = mapped_column(String(300))
    preprocessing: Mapped[dict] = mapped_column(JSON)
    catalogue_version: Mapped[str] = mapped_column(String(40))
    code_revision_id: Mapped[str] = mapped_column(String(100))
    lighting_profile_map_id: Mapped[str] = mapped_column(String(40))
    provenance: Mapped[str] = mapped_column(Text)
    is_fixture: Mapped[bool] = mapped_column(Boolean, default=True)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    digest: Mapped[str] = mapped_column(String(80))
    record_count: Mapped[int] = mapped_column(Integer)
    devices_covered: Mapped[list] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class DatasetRecord(Base):
    __tablename__ = "dataset_records"
    sample_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    split: Mapped[str] = mapped_column(String(20))
    tone_stratum: Mapped[str] = mapped_column(String(20))
    lighting_category: Mapped[str] = mapped_column(String(40))
    device_category: Mapped[str] = mapped_column(String(20))
    expected_shade_id: Mapped[str] = mapped_column(String(20))
    label_provenance: Mapped[str] = mapped_column(Text)
    consent_record_id: Mapped[str] = mapped_column(String(40))
    image_quality: Mapped[str] = mapped_column(String(10))
    grouping_protocol: Mapped[str] = mapped_column(Text)
    image_ref: Mapped[str] = mapped_column(String(200))
    declared_eligible: Mapped[bool] = mapped_column(Boolean)


class DatasetConsentRecord(Base):
    __tablename__ = "dataset_consent_records"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    sample_id: Mapped[str] = mapped_column(String(40), index=True)
    consent_status: Mapped[str] = mapped_column(String(20))
    permitted_use: Mapped[list] = mapped_column(JSON)
    retention_until: Mapped[str] = mapped_column(String(20))


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")  # QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELLED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline_model_id: Mapped[str] = mapped_column(String(100))
    candidate_model_id: Mapped[str] = mapped_column(String(100))
    candidate_artifact_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    baseline_artifact_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    code_revision_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dataset_snapshot_id: Mapped[str] = mapped_column(String(100))
    dataset_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evaluation_config_id: Mapped[str] = mapped_column(String(100))
    evaluation_config_digest: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    requirement_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # PASS | FAIL | INCONCLUSIVE
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    test_set_evaluation_index: Mapped[int] = mapped_column(Integer, default=1)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(100))
    sample_id: Mapped[str] = mapped_column(String(40))
    top3: Mapped[list] = mapped_column(JSON)
    abstained: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (Index("ix_pred_run_model", "run_id", "model_id"),)


class MetricResult(Base):
    __tablename__ = "metric_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    scope: Mapped[str] = mapped_column(String(80))  # "overall" or "TS-4|warm_indoor"
    model_role: Mapped[str] = mapped_column(String(20))  # baseline | candidate | delta
    metrics: Mapped[dict] = mapped_column(JSON)


class GateDecision(Base):
    __tablename__ = "gate_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    context: Mapped[str] = mapped_column(String(30))  # evaluation | release
    gate_id: Mapped[str] = mapped_column(String(64))
    rule: Mapped[str] = mapped_column(Text)
    observed: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    owner_role: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    policy_version: Mapped[str] = mapped_column(String(40))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # code | domain | privacy | qa
    decision: Mapped[str] = mapped_column(String(20))  # APPROVE | REJECT
    reviewer_id: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(Text, default="")
    binding: Mapped[dict] = mapped_column(JSON)
    binding_digest: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # requirements | release | rollback
    decision: Mapped[str] = mapped_column(String(20))  # APPROVED | REJECTED
    approver_id: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(Text, default="")
    binding: Mapped[dict] = mapped_column(JSON)
    binding_digest: Mapped[str] = mapped_column(String(80))
    nonce: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Release(Base):
    __tablename__ = "releases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(100))
    artifact_digest: Mapped[str] = mapped_column(String(80))
    previous_model_id: Mapped[str] = mapped_column(String(100))
    previous_artifact_digest: Mapped[str] = mapped_column(String(80))
    deployment_target: Mapped[str] = mapped_column(String(100))
    approval_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))  # CANARY | MONITORING | RELEASED | ROLLED_BACK
    stage_index: Mapped[int] = mapped_column(Integer, default=0)
    stages: Mapped[list] = mapped_column(JSON)  # prototype settings, e.g. [5, 25, 100]
    history: Mapped[list] = mapped_column(JSON, default=list)
    mode: Mapped[str] = mapped_column(String(20), default="simulated")
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_no}


class MonitoringWindow(Base):
    __tablename__ = "monitoring_windows"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    release_id: Mapped[str] = mapped_column(ForeignKey("releases.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    allocation_pct: Mapped[int] = mapped_column(Integer)
    simulated_sessions: Mapped[int] = mapped_column(Integer)
    exposures: Mapped[int] = mapped_column(Integer)
    labelled: Mapped[int] = mapped_column(Integer)
    cohorts: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("release_id", "index"),)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    release_id: Mapped[str] = mapped_column(ForeignKey("releases.id"), index=True)
    change_id: Mapped[str] = mapped_column(String(64), index=True)
    rule: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(100))
    observed: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN | INVESTIGATED | RESOLVED
    investigation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RollbackRecord(Base):
    __tablename__ = "rollback_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    release_id: Mapped[str] = mapped_column(ForeignKey("releases.id"), index=True)
    change_id: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    alert_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # REQUESTED | APPROVED | EXECUTED | FAILED | REJECTED
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_model_id: Mapped[str] = mapped_column(String(100))
    compatibility: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    change_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text, default="")
    version_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    input_refs: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(80))
    hash: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowCheckpoint(Base):
    __tablename__ = "workflow_checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[int] = mapped_column(Integer)
    node: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))  # RUNNING | COMPLETED | FAILED | INTERRUPTED
    state: Mapped[dict] = mapped_column(JSON)
    pending_nodes: Mapped[list] = mapped_column(JSON)
    interrupt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentInvocation(Base):
    __tablename__ = "agent_invocations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_id: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))  # OK | ERROR
    language_mode: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_config: Mapped[str | None] = mapped_column(String(40), nullable=True)
    output: Mapped[dict] = mapped_column(JSON)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | agent | system
    author: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(60))
    request_digest: Mapped[str] = mapped_column(String(80))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImageUpload(Base):
    __tablename__ = "image_uploads"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(100))
    consent_text_version: Mapped[str] = mapped_column(String(40))
    training_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(30))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    metadata_stripped: Mapped[list] = mapped_column(JSON, default=list)
    storage_inventory: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="STORED")  # STORED | DELETED | DELETE_PARTIAL
    deletion_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delete_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
