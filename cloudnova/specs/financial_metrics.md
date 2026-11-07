# Spec 2 — Financial Metrics (the semantic layer)

Status: **APPROVED v1.0**. Every number the copilot reports must come from one of these
definitions, computed in SQL by DuckDB — never by the LLM. Implemented as views in
`app/pipeline/metrics.sql`; the semantic catalog the agent uses is `app/semantic/catalog.py`.

Money: DECIMAL, all aggregates rounded to 2 dp **at presentation only**. Currency: USD.

## Invoice-grain metrics (table `invoices`)

| Metric id | Definition (SQL over `invoices`) | Notes |
|---|---|---|
| `paid_revenue` | `SUM(amount_usd) FILTER (status='paid')` | "recognized revenue for paid invoices" (Q1) |
| `refunds` | `SUM(amount_usd) FILTER (status='refunded')` | negative number; displayed as an absolute "given back" (Q3) |
| `net_revenue` | `SUM(amount_usd) FILTER (status IN ('paid','refunded'))` | recognized revenue net of refunds |
| `exposure` | `SUM(amount_usd) FILTER (status IN ('pending','failed'))` | money not yet collected (Q6) |
| `invoice_count` | `COUNT(*)` | after dedup |
| `avg_invoice_value` | `AVG(amount_usd) FILTER (status='paid')` | |
| `discount_given` | `SUM(list_price_usd*seats*billed_months*discount_pct/100) FILTER (status='paid')` | list-price based, USD |

Time filter for "in 2024": `invoice_year = 2024` (invoice date, the only date on the record;
there is no service period, so no ratable recognition).

**Q1 interpretation.** "Total recognized revenue for *paid* invoices in 2024" = `paid_revenue`
for 2024. `net_revenue` (paid minus 2024 refunds) is reported alongside it as context.

## Account-grain metrics (table `accounts`, snapshot rule in data contract §2.2)

| Metric id | Definition |
|---|---|
| `account_count` | `COUNT(*)` |
| `active_accounts` | `COUNT(*) FILTER (is_active)` |
| `mrr` | `SUM(current_mrr_usd) FILTER (is_active)` |
| `avg_mrr_per_account` | `AVG(current_mrr_usd) FILTER (is_active)` (Q2) |
| `churn_rate` | `AVG(churned::INT)` over accounts with non-NULL churned, grouped by snapshot plan (Q4) |
| `account_net_revenue` | `net_revenue_usd` per account (Q5 ranking) |

MRR rules from the brief: `list_price[plan] × seats × (1 − discount_pct/100)` in USD. Annual
invoices map to the **same** MRR (never `annual_amount/12`, never `/10`). MRR is not derived from
`amount`, so it is unaffected by the FX open question.

**Q2 "highest average MRR per account by region"**: region and MRR from the account snapshot,
active accounts only (MRR is defined for *active* subscriptions). Sensitivity (all accounts) is
reported as a caveat.

**Q4 churn**: account-level, plan = snapshot plan, churned = snapshot flag. A rate, not a count of
churn *events* — the data has no churn dates, so no time-bounded churn rate can be computed.

**Q5 "top 5 accounts by revenue"**: rank `accounts` by `net_revenue_usd` (paid + refunds, all
time), tie-break `account_id`; flag `csat_score <= 2` (snapshot CSAT; NULL CSAT shown as "unknown",
never as low).

**Q6 "stuck in pending/failed"**: `COUNT(*)` and `exposure` for `status IN ('pending','failed')`,
broken out by status.

## Pricing-rule check (used by Data Quality + anomaly view)
`pricing_delta = amount_local − expected_amount_usd × fx_rate_to_usd` for non-refunds;
`|delta| > 1.00` → `pricing_violation`.

## Change log
* v1.1 (during planner build) — **word → metric rule made explicit**: a bare "revenue / sales /
  billings" means `net_revenue` (BUSINESS_CONTEXT: refunds "net against revenue"); the question must
  say "paid invoices", "paid" or "gross" to get `paid_revenue`. Q1 says "for **paid** invoices" →
  `paid_revenue` (net reported alongside); Q5 "by revenue" → `net_revenue`. Previously this was
  implicit per question; now it is one rule the planner applies everywhere.
* v1.1 — DD-MM-YYYY with day == month is *not* ambiguous (both readings give the same date), so
  `date_was_ambiguous` excludes it (data contract §5.2 clarified).
