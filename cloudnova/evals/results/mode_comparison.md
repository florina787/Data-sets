# Hybrid vs Qwen-only on the six stakeholder questions

Measured 2026-11-07T18:45:41+00:00 · model `qwen2.5-coder:3b` · x86_64 · 4 CPU threads · CPU-only inference · temperature 0 · correctness judged against `evals/oracle.py`.

| Mode | Correct | Median latency | Max latency |
|---|---|---|---|
| hybrid | 6/6 | 10 ms | 61 ms |
| llm | 2/6 | 20,619 ms | 42,858 ms |

| Q | Hybrid | Qwen-only | Qwen-only detail |
|---|---|---|---|
| Q1 | ✓ 61 ms | ✓ 15,452 ms | paid 2024 found |
| Q2 | ✓ 8 ms | ✗ 20,619 ms | sql_error: The database could not run this query: Binder Error: Ambiguous reference to column name "region" (use: 'accounts.region' |
| Q3 | ✓ 7 ms | ✓ 6,733 ms | refund total found |
| Q4 | ✓ 7 ms | ✗ 42,858 ms | sql_error: The database could not run this query: Binder Error: Ambiguous reference to column name "plan" (use: 'accounts.plan' or  |
| Q5 | ✓ 12 ms | ✗ 27,033 ms | got ['ACC-7509', 'ACC-1420', 'ACC-9946', 'ACC-5211', 'ACC-1196'] |
| Q6 | ✓ 10 ms | ✗ 17,791 ms | sql_rejected: Query rejected: unknown column 'status'. |

## SQL Qwen generated (Qwen-only mode)

**Q1** — correct
```sql
SELECT SUM(amount_usd) AS total_revenue FROM invoices WHERE status = 'paid' AND invoice_year = 2024
```

**Q2** — WRONG: sql_error: The database could not run this query: Binder Error: Ambiguous reference to column name "region" (use: 'accounts.region'
```sql
SELECT region, AVG(accounts.current_mrr_usd) AS avg_mrr_per_account FROM accounts JOIN invoices ON accounts.account_id = invoices.account_id WHERE accounts.is_active GROUP BY region ORDER BY avg_mrr_per_account DESC LIMIT 1
```

**Q3** — correct
```sql
SELECT SUM(amount_usd) AS total_refunds FROM invoices WHERE status = 'refunded'
```

**Q4** — WRONG: sql_error: The database could not run this query: Binder Error: Ambiguous reference to column name "plan" (use: 'accounts.plan' or 
```sql
SELECT 
    CASE WHEN plan = 'Enterprise' THEN 1 ELSE 0 END AS is_enterprise,
    COUNT(*) AS account_count,
    SUM(CASE WHEN invoices.status = 'churned' THEN 1 ELSE 0 END) AS churned_accounts,
    (SUM(CASE WHEN invoices.status = 'churned' THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) * 100 AS churn_rate
FROM 
    accounts
JOIN 
    invoices ON accounts.account_id = invoices.account_id
GROUP BY 
    is_enterprise
ORDER BY 
    churn_rate DESC
```

**Q5** — WRONG: got ['ACC-7509', 'ACC-1420', 'ACC-9946', 'ACC-5211', 'ACC-1196']
```sql
SELECT account_id, SUM(amount_usd) AS total_revenue, csat_score 
FROM invoices 
WHERE status = 'paid' 
GROUP BY account_id, csat_score 
ORDER BY total_revenue DESC 
LIMIT 5
```

**Q6** — WRONG: sql_rejected: Query rejected: unknown column 'status'.
```sql
SELECT COUNT(*) AS pending_failed_invoices, SUM(exposure_usd) AS exposed_dollars FROM monthly_revenue WHERE status IN ('pending', 'failed')
```
