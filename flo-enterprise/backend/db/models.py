"""Relational schema for FLO. All monetary amounts are stored as integer cents (BigInteger) in the
reporting currency (CAD) so that values are exact on every database engine; services convert to Decimal.
Every table holds SYNTHETIC data only."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    residency: Mapped[str] = mapped_column(String(8), default="CA")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    display_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(120))
    roles: Mapped[list] = mapped_column(JSON)
    advisor_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    clearance: Mapped[str] = mapped_column(String(16), default="internal")
    business_unit: Mapped[str] = mapped_column(String(40), default="corporate")
    region: Mapped[str] = mapped_column(String(8), default="CA")


class Advisor(Base):
    __tablename__ = "advisors"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(40))
    team: Mapped[str] = mapped_column(String(60))
    business_unit: Mapped[str] = mapped_column(String(40))
    hire_date: Mapped[date] = mapped_column(Date)


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    advisor_id: Mapped[str] = mapped_column(ForeignKey("advisors.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(32))
    dob: Mapped[date] = mapped_column(Date)
    sin: Mapped[str] = mapped_column(String(16))
    address: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(60))
    province: Mapped[str] = mapped_column(String(4))
    postal_code: Mapped[str] = mapped_column(String(8))
    account_number: Mapped[str] = mapped_column(String(16), unique=True)
    segment: Mapped[str] = mapped_column(String(24))
    risk_profile: Mapped[str] = mapped_column(String(24))
    risk_score: Mapped[int] = mapped_column(Integer)
    investable_assets_cents: Mapped[int] = mapped_column(BigInteger)
    annual_income_cents: Mapped[int] = mapped_column(BigInteger)
    time_horizon_years: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(4))
    onboarding_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12))
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kyc_last_review: Mapped[date] = mapped_column(Date)
    business_unit: Mapped[str] = mapped_column(String(40), default="private_wealth")


class ClientGoal(Base):
    __tablename__ = "client_goals"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    goal_type: Mapped[str] = mapped_column(String(24))
    target_amount_cents: Mapped[int] = mapped_column(BigInteger)
    current_amount_cents: Mapped[int] = mapped_column(BigInteger)
    monthly_contribution_cents: Mapped[int] = mapped_column(BigInteger)
    target_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[int] = mapped_column(Integer)


class Security(Base):
    __tablename__ = "securities"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(24))
    sector: Mapped[str] = mapped_column(String(40))
    country: Mapped[str] = mapped_column(String(4))
    region: Mapped[str] = mapped_column(String(24))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(4))


class SecurityReturn(Base):
    __tablename__ = "security_returns"
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    ret: Mapped[float] = mapped_column(Float)


class Benchmark(Base):
    __tablename__ = "benchmarks"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(24))
    region: Mapped[str] = mapped_column(String(24))


class BenchmarkReturn(Base):
    __tablename__ = "benchmark_returns"
    benchmark_id: Mapped[str] = mapped_column(ForeignKey("benchmarks.id"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    ret: Mapped[float] = mapped_column(Float)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(120))
    asset_class: Mapped[str] = mapped_column(String(24))
    vehicle: Mapped[str] = mapped_column(String(24))
    strategy: Mapped[str] = mapped_column(String(60))
    region: Mapped[str] = mapped_column(String(24))
    mgmt_fee_bps: Mapped[int] = mapped_column(Integer)
    launch_date: Mapped[date] = mapped_column(Date)
    benchmark_id: Mapped[str] = mapped_column(ForeignKey("benchmarks.id"))
    risk_rating: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(12))


class ProductHolding(Base):
    __tablename__ = "product_holdings"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float)


class ProductMonthly(Base):
    __tablename__ = "product_monthly"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    aum_open_cents: Mapped[int] = mapped_column(BigInteger)
    subscriptions_cents: Mapped[int] = mapped_column(BigInteger)
    redemptions_cents: Mapped[int] = mapped_column(BigInteger)
    market_cents: Mapped[int] = mapped_column(BigInteger)
    aum_close_cents: Mapped[int] = mapped_column(BigInteger)
    ret: Mapped[float] = mapped_column(Float)
    fee_bps: Mapped[int] = mapped_column(Integer)
    revenue_cents: Mapped[int] = mapped_column(BigInteger)


class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mandate: Mapped[str] = mapped_column(String(40))
    model_risk_profile: Mapped[str] = mapped_column(String(24))
    benchmark_id: Mapped[str] = mapped_column(ForeignKey("benchmarks.id"))
    inception_date: Mapped[date] = mapped_column(Date)
    base_currency: Mapped[str] = mapped_column(String(4), default="CAD")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"), primary_key=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), primary_key=True)
    target_weight: Mapped[float] = mapped_column(Float)
    current_weight: Mapped[float] = mapped_column(Float)


class PortfolioMonthly(Base):
    __tablename__ = "portfolio_monthly"
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    mv_open_cents: Mapped[int] = mapped_column(BigInteger)
    net_external_flow_cents: Mapped[int] = mapped_column(BigInteger)
    mv_close_cents: Mapped[int] = mapped_column(BigInteger)
    ret: Mapped[float] = mapped_column(Float)


class ClientPosition(Base):
    __tablename__ = "client_positions"
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    market_value_cents: Mapped[int] = mapped_column(BigInteger)
    cost_basis_cents: Mapped[int] = mapped_column(BigInteger)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    tx_date: Mapped[date] = mapped_column(Date)
    tx_type: Mapped[str] = mapped_column(String(16))
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(String(200))


class ServiceInteraction(Base):
    __tablename__ = "service_interactions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    advisor_id: Mapped[str] = mapped_column(ForeignKey("advisors.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    channel: Mapped[str] = mapped_column(String(16))
    interaction_type: Mapped[str] = mapped_column(String(24))
    topic: Mapped[str] = mapped_column(String(60))
    sentiment: Mapped[str] = mapped_column(String(12))
    notes: Mapped[str] = mapped_column(Text)
    follow_up_required: Mapped[bool] = mapped_column(Boolean)


class FinanceMonthly(Base):
    __tablename__ = "finance_monthly"
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    line: Mapped[str] = mapped_column(String(40), primary_key=True)
    actual_cents: Mapped[int] = mapped_column(BigInteger)
    budget_cents: Mapped[int] = mapped_column(BigInteger)


class Control(Base):
    __tablename__ = "controls"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(40))
    framework_refs: Mapped[list] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(80))
    frequency: Mapped[str] = mapped_column(String(24))


class ComplianceEvent(Base):
    __tablename__ = "compliance_events"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16))
    control_id: Mapped[str] = mapped_column(ForeignKey("controls.id"))
    opened_at: Mapped[date] = mapped_column(Date)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_unit: Mapped[str] = mapped_column(String(40))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    portfolio_id: Mapped[str | None] = mapped_column(ForeignKey("portfolios.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(80))


class RiskRegisterItem(Base):
    __tablename__ = "risk_register"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    category: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(160))
    likelihood: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    owner: Mapped[str] = mapped_column(String(80))
    trend: Mapped[str] = mapped_column(String(12))
    mitigation: Mapped[str] = mapped_column(Text)


class Initiative(Base):
    __tablename__ = "initiatives"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(160))
    owner: Mapped[str] = mapped_column(String(80))
    domain: Mapped[str] = mapped_column(String(40))
    budget_cents: Mapped[int] = mapped_column(BigInteger)
    spent_cents: Mapped[int] = mapped_column(BigInteger)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    progress_pct: Mapped[int] = mapped_column(Integer)
    planned_progress_pct: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    target_kpi: Mapped[str] = mapped_column(String(60))
    target_value: Mapped[float] = mapped_column(Float)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(80))
    decision_date: Mapped[date] = mapped_column(Date)
    rationale: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON)
    assumptions: Mapped[list] = mapped_column(JSON)
    expected_impact: Mapped[str] = mapped_column(Text)
    target_kpi: Mapped[str] = mapped_column(String(60))
    baseline_value: Mapped[float] = mapped_column(Float)
    target_value: Mapped[float] = mapped_column(Float)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline: Mapped[date] = mapped_column(Date)
    approval_status: Mapped[str] = mapped_column(String(16))
    approver: Mapped[str] = mapped_column(String(80))
    follow_ups: Mapped[list] = mapped_column(JSON)
    outcome_status: Mapped[str] = mapped_column(String(20))
    initiative_id: Mapped[str | None] = mapped_column(ForeignKey("initiatives.id"), nullable=True)


class AgentTrace(Base):
    __tablename__ = "agent_traces"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(32))
    workflow_id: Mapped[str] = mapped_column(String(40), index=True)
    workflow_type: Mapped[str] = mapped_column(String(40))
    agent_id: Mapped[str] = mapped_column(String(60), index=True)
    agent_version: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    tokens_in: Mapped[int] = mapped_column(Integer)
    tokens_out: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    failure_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer)
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_calls: Mapped[list] = mapped_column(JSON)
    approval_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    policy_outcome: Mapped[str] = mapped_column(String(16))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(40), unique=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    actor: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[list] = mapped_column(JSON)
    policy_version: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    action_type: Mapped[str] = mapped_column(String(40))
    requested_by: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[list] = mapped_column(JSON)
    risk_class: Mapped[str] = mapped_column(String(16))
    approver_role: Mapped[str] = mapped_column(String(40))
    resource_ref: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    workflow_thread_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    policy_version: Mapped[str] = mapped_column(String(40))


class VaultEntry(Base):
    __tablename__ = "token_vault"
    __table_args__ = (UniqueConstraint("tenant_id", "token"), Index("ix_vault_lookup", "tenant_id", "value_digest"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    token: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(24))
    value_digest: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(16))
    classification: Mapped[str] = mapped_column(String(16))
    access_groups: Mapped[list] = mapped_column(JSON)
    effective_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(4))
    doc_type: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    injection_flags: Mapped[list] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime)


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(120))
    recipient_ref: Mapped[str] = mapped_column(String(80))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    approval_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    requested_by: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SeedManifest(Base):
    __tablename__ = "seed_manifest"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Conversation(Base):
    """A user's FLO conversation. `state` holds only analysis parameters and entity ids (never PII values or vault mappings)."""
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    persona: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    state: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "client_message_id", name="uq_conversation_client_message"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(40), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    client_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_refs: Mapped[dict] = mapped_column(JSON)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)
