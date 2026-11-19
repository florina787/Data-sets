"""Florome Shield persistent model. Shares Florome's Base, tenants and audit chain.

Provenance rules
----------------
* Every code-derived row references a ``RepositorySnapshot`` (commit + content tree hash) and a file/line.
* Every finding references the tools (name + version) and evidence it rests on.
* Conclusions produced by a model (none today: the engine is deterministic) must fill ``model_provenance``.
* Observed facts (symbols, scanner output, verification transcripts) are kept apart from conclusions
  (hypotheses, adjudications).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from florome.models import Base, new_id, utcnow


class Repository(Base):
    __tablename__ = "shield_repositories"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("repo"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    root: Mapped[str] = mapped_column(Text)  # resolved path inside an authorised root
    authorized_by: Mapped[str] = mapped_column(String(64))
    authorized_at: Mapped[datetime] = mapped_column(default=utcnow)
    data_class: Mapped[str] = mapped_column(String(20), default="benchmark")  # benchmark | simulated | production


class RepositorySnapshot(Base):
    __tablename__ = "shield_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("snap"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("shield_repositories.id"), index=True)
    commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    tree_hash: Mapped[str] = mapped_column(String(64))
    file_hashes: Mapped[dict[str, Any]] = mapped_column(default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(default=dict)
    analyzer: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class CodeSymbol(Base):
    __tablename__ = "shield_symbols"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("shield_snapshots.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # module | class | function | route | external
    name: Mapped[str] = mapped_column(String(300))
    qualname: Mapped[str] = mapped_column(String(500))
    file: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    attrs: Mapped[dict[str, Any]] = mapped_column(default=dict)


class CodeRelationship(Base):
    __tablename__ = "shield_relationships"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rel"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("shield_snapshots.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # contains | imports | calls | sink | data_flow | authenticated_by | guarded_by
    source_id: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64))
    file: Mapped[str] = mapped_column(Text)
    line: Mapped[int] = mapped_column(Integer)
    attrs: Mapped[dict[str, Any]] = mapped_column(default=dict)
    provenance: Mapped[dict[str, Any]] = mapped_column(default=dict)


class TrustBoundary(Base):
    __tablename__ = "shield_trust_boundaries"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tb"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("shield_snapshots.id"), index=True)
    route_symbol_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(30))  # unauthenticated_input | authenticated_input
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)


class ScanRun(Base):
    __tablename__ = "shield_scan_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("scan"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("shield_snapshots.id"), index=True)
    started_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))  # succeeded | partial | failed
    tools: Mapped[list[Any]] = mapped_column(default=list)  # [{tool, version, status, findings, seconds, error}]
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class FindingEvidence(Base):
    """Raw, normalised output of one tool for one location (an observed fact)."""

    __tablename__ = "shield_finding_evidence"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("fev"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("shield_scan_runs.id"), index=True)
    tool: Mapped[str] = mapped_column(String(30))
    tool_version: Mapped[str] = mapped_column(String(40))
    rule_id: Mapped[str] = mapped_column(String(200))
    vuln_class: Mapped[str] = mapped_column(String(40))
    cwe: Mapped[str | None] = mapped_column(String(20), nullable=True)
    severity: Mapped[str] = mapped_column(String(10))
    file: Mapped[str] = mapped_column(Text)
    line: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    raw: Mapped[dict[str, Any]] = mapped_column(default=dict)


class SecurityHypothesis(Base):
    __tablename__ = "shield_hypotheses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("shyp"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("shield_snapshots.id"), index=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vuln_class: Mapped[str] = mapped_column(String(40))
    symbol_id: Mapped[str] = mapped_column(String(64))
    function: Mapped[str] = mapped_column(String(300))
    file: Mapped[str] = mapped_column(Text)
    line: Mapped[int] = mapped_column(Integer)
    assumption: Mapped[str] = mapped_column(Text)
    weakness: Mapped[str] = mapped_column(Text)
    supporting: Mapped[list[Any]] = mapped_column(default=list)  # [{type, ref, detail}]
    contradicting: Mapped[list[Any]] = mapped_column(default=list)
    verification_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | confirmed | probable | inconclusive | disproven
    status_basis: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    model_provenance: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class VerificationRun(Base):
    __tablename__ = "shield_verification_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ver"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    hypothesis_id: Mapped[str] = mapped_column(ForeignKey("shield_hypotheses.id"), index=True)
    method: Mapped[str] = mapped_column(String(60))
    purpose: Mapped[str] = mapped_column(String(20), default="verify")  # verify | patch_regression
    attempt: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(20))  # reproduced | not_reproduced | error | timeout
    isolation: Mapped[dict[str, Any]] = mapped_column(default=dict)
    transcript: Mapped[dict[str, Any]] = mapped_column(default=dict)
    seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class VulnerabilityFinding(Base):
    """Adjudicated result for a hypothesis. Severity is assessed separately from the evidential status."""

    __tablename__ = "shield_findings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vf"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    hypothesis_id: Mapped[str] = mapped_column(ForeignKey("shield_hypotheses.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    severity_basis: Mapped[str] = mapped_column(Text)
    incident_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class RemediationPatch(Base):
    __tablename__ = "shield_patches"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("patch"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    hypothesis_id: Mapped[str] = mapped_column(ForeignKey("shield_hypotheses.id"), index=True)
    diff: Mapped[str] = mapped_column(Text)
    generator: Mapped[str] = mapped_column(String(60))
    regression: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20))  # verified | failed_regression | approved_for_review | rejected
    requested_by: Mapped[str] = mapped_column(String(64))
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patch_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ContainmentEvent(Base):
    __tablename__ = "shield_containment_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cont"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario: Mapped[str] = mapped_column(String(60))
    violation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    actions_taken: Mapped[list[Any]] = mapped_column(default=list)
    forensics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    outcome: Mapped[str] = mapped_column(String(20))  # contained | completed | error
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TemporaryCredential(Base):
    """Synthetic short-lived credential issued to an agent session; revoked by the containment supervisor."""

    __tablename__ = "shield_temp_credentials"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cred"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column()
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class MCPServerManifest(Base):
    __tablename__ = "shield_mcp_manifests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("man"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_servers.id"), unique=True)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    server_identity: Mapped[dict[str, Any]] = mapped_column(default=dict)
    pinned_by: Mapped[str] = mapped_column(String(64))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SecurityPolicyDecision(Base):
    __tablename__ = "shield_policy_decisions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pd"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str] = mapped_column(Text)
    allowed: Mapped[bool] = mapped_column(Boolean)
    engines: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {"builtin": {...}, "opa": {...}}
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class BenchmarkRun(Base):
    __tablename__ = "shield_benchmark_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("bench"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    corpus: Mapped[str] = mapped_column(String(100))
    pipeline: Mapped[str] = mapped_column(String(40))  # scanner_only | hybrid_verified | llm_only
    status: Mapped[str] = mapped_column(String(20))  # completed | not_run
    sample_size: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    per_site: Mapped[list[Any]] = mapped_column(default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
