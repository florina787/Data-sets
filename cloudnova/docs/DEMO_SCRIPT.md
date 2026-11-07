# Demo script (4–5 minutes)

Sequence: messy customer data → specification → cleaning & reconciliation → AI query → verified answer →
production architecture → measurable evaluation. Every number below is what the app prints today.

| Time | Show | Say |
|---|---|---|
| 0:00 | `data/raw/cloudnova_invoices.csv` (scroll: `Tier 2`, `$4,900.00`, `05-01-2024`, `billing_at_x.com`) | "Finance gave me 5,125 rows stitched from three systems and asked for answers they can trust." |
| 0:30 | `specs/cloudnova_data_contract.md` §1 evidence table + §6 open questions | "Before code, I profiled and wrote the contract. The date rule is evidence-based: in 1,320 slash dates the first part is never above 12, so they're MM/DD. And I found a question for finance: every EUR amount equals the USD price × 1.08 — the documented conversion may apply FX twice." |
| 1:15 | Terminal: `python -m app` (READY in ~2 s; Q1–Q6 readiness lines) | "One command: validates config, builds DuckDB, connects to local Qwen, checks the six stakeholder questions, starts the API and dashboard." |
| 1:45 | Dashboard → **Reconciliation & Quality**: click each waterfall bar | "5,125 rows → 5,000 invoices. 82 exact duplicates, 27 synonym duplicates, 16 real conflicts. Without dedup paid revenue would be overstated by $2.12M. The conflicts are a $168k decision I surface, not hide." |
| 2:30 | **Ask CloudNova AI**: "Which region has the highest average MRR per account?" → open *Generated SQL*, caveats | "APAC, $6,147.30. Here's the exact SQL. MRR comes from list price × seats × discount, not from the annual lump sum." |
| 3:00 | Follow-ups: "Show revenue by region" → "Only Enterprise" → "Explain the calculation" | "Follow-ups patch the previous query plan; explain shows definitions and SQL." |
| 3:20 | "Why did Acme Ltd churn?" / "Delete all refunded invoices" | "It declines what the data can't support and refuses writes — the database is read-only at two layers." |
| 3:40 | `docs/architecture.md` diagram | "Deterministic metrics first; local Qwen writes SQL only outside the catalog, through the same guard." |
| 4:00 | Terminal: `python -m evals` → PASS 31 / XFAIL 2; `evals/results/mode_comparison.md` | "An independent oracle recomputes every expected value from the raw CSV. Hybrid gets 6/6 in ~10 ms; Qwen-3B alone got 2/6 — it invented `status='churned'`. That's why it's a fallback." |
| 4:30 | `docs/LIMITATIONS.md` | "Two decisions I need from CloudNova: FX direction and what 'customer' means. Both are encoded as expected failures that flip when they decide." |

Backup if Qwen is slow/unavailable: the whole sequence except general chat works in deterministic mode.
