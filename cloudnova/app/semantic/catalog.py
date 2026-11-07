"""Semantic layer: the ONLY place metric SQL is defined (specs/financial_metrics.md).

Invoice-grain SQL uses alias `i` (invoices) and may join `a` (accounts) for account attributes.
Account-grain SQL uses alias `a`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    grain: str          # invoice | account
    sql: str
    unit: str           # usd | count | pct | score
    definition: str
    keywords: tuple[str, ...] = ()


METRICS: dict[str, Metric] = {m.id: m for m in [
    Metric("paid_revenue", "Paid revenue (USD)", "invoice", "SUM(i.amount_usd) FILTER (WHERE i.status = 'paid')", "usd",
           "Sum of amount_usd over invoices whose status normalizes to 'paid' (refunds not netted)."),
    Metric("net_revenue", "Recognized revenue, net of refunds (USD)", "invoice",
           "SUM(i.amount_usd) FILTER (WHERE i.status IN ('paid','refunded'))", "usd",
           "Paid invoices plus refunded invoices (negative amounts), i.e. recognized revenue netted for refunds. "
           "Pending/failed/void are excluded."),
    Metric("refunds", "Refunds (USD, negative)", "invoice", "SUM(i.amount_usd) FILTER (WHERE i.status = 'refunded')", "usd",
           "Sum of amount_usd over refunded invoices (Refunded/REFUND/charged_back). Amounts are negative."),
    Metric("refund_count", "Refunded invoices", "invoice", "COUNT(*) FILTER (WHERE i.status = 'refunded')", "count",
           "Number of invoices whose status normalizes to 'refunded'."),
    Metric("exposure", "Pending + failed exposure (USD)", "invoice",
           "SUM(i.amount_usd) FILTER (WHERE i.status IN ('pending','failed'))", "usd",
           "Sum of amount_usd for invoices stuck in pending or failed — billed but not collected."),
    Metric("exposure_count", "Pending + failed invoices", "invoice", "COUNT(*) FILTER (WHERE i.status IN ('pending','failed'))",
           "count", "Number of invoices whose status normalizes to pending or failed."),
    Metric("invoice_count", "Invoices", "invoice", "COUNT(*)", "count", "Number of unique invoices after deduplication."),
    Metric("avg_invoice_value", "Average paid invoice (USD)", "invoice", "AVG(i.amount_usd) FILTER (WHERE i.status = 'paid')",
           "usd", "Mean amount_usd of paid invoices."),
    Metric("discount_given", "Discounts given on paid invoices (USD, list-price basis)", "invoice",
           "SUM(i.list_price_usd * i.seats * i.billed_months * i.discount_pct / 100) FILTER (WHERE i.status = 'paid')", "usd",
           "list_price × seats × billed_months × discount_pct/100 over paid invoices (USD list prices)."),
    Metric("seats_billed", "Seats on paid invoices", "invoice", "SUM(i.seats) FILTER (WHERE i.status = 'paid')", "count",
           "Total seats across paid invoices."),
    Metric("avg_mrr", "Average MRR per active account (USD)", "account", "AVG(a.current_mrr_usd) FILTER (WHERE a.is_active)",
           "usd", "Mean of list_price[plan] × seats × (1 − discount/100) over active (not churned) accounts, "
           "using each account's latest invoice (annual invoices map to the same MRR)."),
    Metric("total_mrr", "MRR (USD)", "account", "SUM(a.current_mrr_usd) FILTER (WHERE a.is_active)", "usd",
           "Sum of current MRR over active (not churned) accounts."),
    Metric("churn_rate", "Churn rate", "account", "AVG(CASE WHEN a.churned THEN 1.0 ELSE 0.0 END) FILTER (WHERE a.churned IS NOT NULL)",
           "pct", "Share of accounts whose latest invoice says churned = true (accounts with unknown churn excluded)."),
    Metric("churned_accounts", "Churned accounts", "account", "COUNT(*) FILTER (WHERE a.churned)", "count",
           "Accounts whose latest snapshot says churned."),
    Metric("account_count", "Accounts", "account", "COUNT(*)", "count", "Distinct account_id values."),
    Metric("active_accounts", "Active accounts", "account", "COUNT(*) FILTER (WHERE a.is_active)", "count",
           "Accounts whose latest snapshot is not churned."),
    Metric("avg_csat", "Average CSAT (1–5)", "account", "AVG(a.csat_score)", "score",
           "Mean latest CSAT over accounts with a score (blank CSAT excluded, never imputed)."),
]}


@dataclass(frozen=True)
class Dimension:
    id: str
    label: str
    invoice_sql: str | None   # expression at invoice grain
    account_sql: str | None   # expression at account grain


DIMENSIONS: dict[str, Dimension] = {d.id: d for d in [
    Dimension("region", "Region", "i.region", "a.region"),
    Dimension("plan", "Plan", "i.plan", "a.plan"),
    Dimension("industry", "Industry", "i.industry", "a.industry"),
    Dimension("billing_cycle", "Billing cycle", "i.billing_cycle", None),
    Dimension("currency", "Currency", "i.currency", None),
    Dimension("status", "Status", "i.status", None),
    Dimension("payment_method", "Payment method", "i.payment_method", None),
    Dimension("invoice_year", "Year", "i.invoice_year", None),
    Dimension("invoice_month", "Month", "i.invoice_month", None),
    Dimension("account", "Account", "i.account_id", "a.account_id"),
    Dimension("churned", "Churned", None, "a.churned"),
    Dimension("csat_score", "CSAT", None, "a.csat_score"),
]}

# filter field → (invoice-grain column, account-grain column)
FILTER_COLUMNS = {
    "region": ("i.region", "a.region"), "plan": ("i.plan", "a.plan"), "industry": ("i.industry", "a.industry"),
    "status": ("i.status", None), "currency": ("i.currency", None), "billing_cycle": ("i.billing_cycle", None),
    "invoice_year": ("i.invoice_year", None), "csat_max": ("a.csat_score", "a.csat_score"),
    "churned": ("a.churned", "a.churned"), "account": ("i.account_id", "a.account_id"),
}

SCHEMA_DOC = """
invoices (one row per unique invoice, after cleaning):
  invoice_id, account_id, account_name, region ('NA','EMEA','APAC','LATAM'), industry, plan ('Starter','Pro','Enterprise'),
  billing_cycle ('monthly','annual'), billed_months (1|10), seats, currency ('USD','EUR','GBP'), amount_local,
  amount_usd (USD, negative for refunds), discount_pct, list_price_usd, mrr_usd, status ('paid','pending','failed','refunded','void'),
  is_revenue, payment_method, signup_date, invoice_date (DATE), invoice_year (INT), invoice_month ('YYYY-MM'),
  churned (BOOLEAN), csat_score (1-5, may be NULL), support_tickets, dq_flags
accounts (one row per account_id, latest-invoice snapshot):
  account_id, account_name, region, industry, plan, seats, discount_pct, churned, csat_score, current_mrr_usd,
  is_active (NOT churned), first_invoice_date, last_invoice_date, invoice_count, paid_revenue_usd, refunds_usd, net_revenue_usd
monthly_revenue (view): invoice_month, paid_revenue_usd, refunds_usd, net_revenue_usd, exposure_usd, invoice_count
""".strip()
