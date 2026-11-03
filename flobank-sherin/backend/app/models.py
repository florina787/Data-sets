"""Relational schema. Money is stored as NUMERIC(18,2) in USD (the base currency) and converted for display.

Every business record carries:
  data_class  - "synthetic" (seeded demo data) or "measured" (recorded by this running system)
  basis       - "actual", "estimated" or "forecast"
so demonstration figures can never be mistaken for real business performance.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

Money = Numeric(18, 2)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class FxRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    source: Mapped[str] = mapped_column(String(120))
    as_of: Mapped[dt.datetime] = mapped_column(DateTime)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")
    created_by: Mapped[str] = mapped_column(String(64), default="system")


class LedgerLine(Base):
    """Bank-level revenue and operating expenditure (daily granularity)."""
    __tablename__ = "ledger_lines"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # revenue | opex
    category: Mapped[str] = mapped_column(String(48))
    amount_usd: Mapped[Decimal] = mapped_column(Money)
    basis: Mapped[str] = mapped_column(String(16), default="actual")
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class Budget(Base):
    __tablename__ = "budgets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    scope: Mapped[str] = mapped_column(String(24))  # bank_revenue | bank_opex | ai_cost
    amount_usd: Mapped[Decimal] = mapped_column(Money)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class HumanBaseline(Base):
    """Independently configured human-only effort for a workflow type."""
    __tablename__ = "human_baselines"
    workflow_type: Mapped[str] = mapped_column(String(48), primary_key=True)
    department: Mapped[str] = mapped_column(String(48))
    label: Mapped[str] = mapped_column(String(80))
    hours_per_task: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    hourly_rate_usd: Mapped[Decimal] = mapped_column(Money)
    source: Mapped[str] = mapped_column(String(160))
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")
    configured_by: Mapped[str] = mapped_column(String(64), default="finance.controller")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class AgentTask(Base):
    """One unit of agent work, with its full AI-assisted workflow cost."""
    __tablename__ = "agent_tasks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    agent: Mapped[str] = mapped_column(String(48), index=True)
    department: Mapped[str] = mapped_column(String(48), index=True)
    workflow_type: Mapped[str] = mapped_column(String(48), ForeignKey("human_baselines.workflow_type"))
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    duration_s: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # succeeded | failed
    quality_pass: Mapped[bool] = mapped_column(Boolean)
    verified: Mapped[bool] = mapped_column(Boolean)  # passed the Independent Verification Agent
    retries: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    human_review_min: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rework_min: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    cost_model: Mapped[Decimal] = mapped_column(Money)
    cost_compute: Mapped[Decimal] = mapped_column(Money)
    cost_infra: Mapped[Decimal] = mapped_column(Money)
    cost_tooling: Mapped[Decimal] = mapped_column(Money)
    cost_human_review: Mapped[Decimal] = mapped_column(Money)
    cost_rework: Mapped[Decimal] = mapped_column(Money)
    baseline_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot at completion time
    baseline_rate_usd: Mapped[Decimal] = mapped_column(Money)
    summary: Mapped[str] = mapped_column(Text, default="")
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class AiCostRecord(Base):
    """Every Sherin AI cost. Workflow categories are generated 1:1 from AgentTask cost fields so they reconcile."""
    __tablename__ = "ai_cost_records"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    subcategory: Mapped[str] = mapped_column(String(48), default="")
    agent: Mapped[str | None] = mapped_column(String(48), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("agent_tasks.id"), nullable=True, index=True)
    amount_usd: Mapped[Decimal] = mapped_column(Money)
    description: Mapped[str] = mapped_column(String(240), default="")
    vendor: Mapped[str] = mapped_column(String(64), default="")
    basis: Mapped[str] = mapped_column(String(16), default="actual")
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class TokenUsage(Base):
    __tablename__ = "token_usage"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    agent: Mapped[str] = mapped_column(String(48), index=True)
    task_id: Mapped[str] = mapped_column(String(40), ForeignKey("agent_tasks.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16))  # local_qwen | paid_api | none
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    api_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    local_compute_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    local_energy_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    latency_ms: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class RevenueAttribution(Base):
    """Revenue from AI-assisted workflows. A subset of bank revenue, never additional to it."""
    __tablename__ = "revenue_attribution"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    workflow: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(48))
    revenue_category: Mapped[str] = mapped_column(String(48))  # which ledger revenue line it sits inside
    attributed_revenue_usd: Mapped[Decimal] = mapped_column(Money)
    incremental_profit_usd: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(200))
    realized: Mapped[bool] = mapped_column(Boolean, default=True)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    mandate: Mapped[dict] = mapped_column(JSON)
    manager: Mapped[str] = mapped_column(String(64))
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(24), ForeignKey("portfolios.id"), index=True)
    issuer: Mapped[str] = mapped_column(String(120))
    sector: Mapped[str] = mapped_column(String(48))
    asset_class: Mapped[str] = mapped_column(String(32))
    country: Mapped[str] = mapped_column(String(32))
    market_value_usd: Mapped[Decimal] = mapped_column(Money)
    esg_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    liquidity_days: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    rating: Mapped[str] = mapped_column(String(8))
    volatility: Mapped[float] = mapped_column(Numeric(8, 4))  # annualised


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[str] = mapped_column(String(24), ForeignKey("portfolios.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date)
    issuer: Mapped[str] = mapped_column(String(120))
    side: Mapped[str] = mapped_column(String(4))
    notional_usd: Mapped[Decimal] = mapped_column(Money)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class TradeProposal(Base):
    __tablename__ = "trade_proposals"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(24), ForeignKey("portfolios.id"))
    issuer: Mapped[str] = mapped_column(String(120))
    sector: Mapped[str] = mapped_column(String(48))
    asset_class: Mapped[str] = mapped_column(String(32))
    country: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(4))
    notional_usd: Mapped[Decimal] = mapped_column(Money)
    esg_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    liquidity_days: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(8), nullable=True)
    volatility: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    proposed_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    guardian_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))  # investment | deployment | data_change | ai_decision
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    required_roles: Mapped[list] = mapped_column(JSON)
    decisions: Mapped[list] = mapped_column(JSON, default=list)
    financial_impact_usd: Mapped[Decimal] = mapped_column(Money, default=0)
    risk_evidence: Mapped[list] = mapped_column(JSON, default=list)
    policy_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    related_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_proposal_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    related_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(48))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    opened_at: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    service: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16))
    resolved_by_task: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class ComplianceEvent(Base):
    __tablename__ = "compliance_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(12))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class SystemMetricDaily(Base):
    __tablename__ = "system_metrics_daily"
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer)
    p50_ms: Mapped[int] = mapped_column(Integer)
    p95_ms: Mapped[int] = mapped_column(Integer)
    p99_ms: Mapped[int] = mapped_column(Integer)
    cpu_pct: Mapped[float] = mapped_column(Numeric(6, 2))
    mem_pct: Mapped[float] = mapped_column(Numeric(6, 2))
    gpu_pct: Mapped[float] = mapped_column(Numeric(6, 2))
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(40), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class HarnessRun(Base):
    __tablename__ = "harness_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    request: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    plan: Mapped[list] = mapped_column(JSON, default=list)
    trace: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class RealizedSaving(Base):
    """Cash savings actually booked against a budget (e.g. contractor hours not purchased).

    This is a stricter subset of estimated cost avoidance and is shown for context only; it is never
    added to net economic benefit on top of cost avoidance (that would double count)."""
    __tablename__ = "realized_savings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    department: Mapped[str] = mapped_column(String(48))
    amount_usd: Mapped[Decimal] = mapped_column(Money)
    evidence: Mapped[str] = mapped_column(String(240))
    data_class: Mapped[str] = mapped_column(String(16), default="synthetic")
