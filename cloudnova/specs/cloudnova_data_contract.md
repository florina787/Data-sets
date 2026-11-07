# Spec 1 — CloudNova Data Contract (raw → clean)

Status: **APPROVED v1.0** (written before implementation; changes are logged at the bottom).
Source of truth for business rules: [`data/raw/BUSINESS_CONTEXT.md`](../data/raw/BUSINESS_CONTEXT.md).
Implementation: `app/pipeline/clean.py`. Tests: `tests/test_cleaning.py`.

## 1. Input

`data/raw/cloudnova_invoices.csv` — 5,125 rows × 19 columns, read **as strings** (`dtype=str`,
`keep_default_na=False`) so that nothing is coerced before a rule decides. SHA-256 is recorded in
the run manifest (`data/processed/manifest.json`) so every answer is traceable to an exact file.

Profiling facts that drove the rules below (measured, not assumed):

| Fact | Evidence |
|---|---|
| 82 full-duplicate rows | `df.duplicated().sum()` |
| 43 `invoice_id`s with ≥2 *different* rows | after full-dup removal |
| … of which 27 differ only by a status **synonym** (e.g. `completed` vs `PAID`) | collapse after normalization |
| … and 16 are **real conflicts** (paid/pending 7, paid/void 5, paid/failed 2, paid/refunded 2) | differ in canonical status only — all other columns identical |
| `NN/NN/YYYY` dates: first part never > 12, second part > 12 in 786 rows | ⇒ **MM/DD/YYYY** |
| `NN-NN-YYYY` dates: first part > 12 in 151 rows, second never > 12 | ⇒ **DD-MM-YYYY** |
| 3,815 `account_id`s but only 200 distinct `account_name`s | names are **not** identifiers |
| ~25% of accounts have conflicting `region`/`plan`/`churned`/`csat` across their invoices | needs snapshot rule |
| Every amount reconciles to `list × seats × months × (1−disc)` × {USD 1.00, EUR 1.08, GBP 1.27} | see §6 open question |

## 2. Output tables (DuckDB `data/processed/cloudnova.duckdb`, plus parquet copies)

### 2.1 `invoices` — one row per **unique invoice_id** (the analytic fact table)

| Column | Type | Rule |
|---|---|---|
| invoice_id | VARCHAR PK | trimmed; unique after dedup (§3) |
| account_id | VARCHAR NOT NULL | trimmed |
| account_name | VARCHAR | trimmed, internal whitespace collapsed |
| contact_email | VARCHAR NULL | `_at_` → `@`; lower-cased; NULL if blank; NULL if still not `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| email_was_repaired | BOOLEAN | true when `_at_` fix applied |
| region | VARCHAR | one of `NA, EMEA, APAC, LATAM`; else NULL + DQ issue |
| industry | VARCHAR NULL | trimmed; blank → NULL (**never** imputed) |
| plan | VARCHAR NOT NULL | canonical `Starter / Pro / Enterprise` (§4.1). Unknown → row quarantined, never defaulted |
| billing_cycle | VARCHAR NOT NULL | `monthly / annual` (§4.2) |
| billed_months | INTEGER | monthly → 1, annual → **10** (2 months free) |
| seats | INTEGER > 0 | |
| currency | VARCHAR | `USD / EUR / GBP` |
| amount_local | DECIMAL(14,2) | parsed (§5), sign preserved |
| fx_rate_to_usd | DECIMAL(6,4) | USD 1.00, EUR 1.08, GBP 1.27 (config, fixed) |
| amount_usd | DECIMAL(14,2) | `round(amount_local × fx_rate_to_usd, 2)` — the documented rule |
| discount_pct | DECIMAL(5,2) | 0 ≤ x < 100 |
| list_price_usd | DECIMAL | Starter 49, Pro 99, Enterprise 299 |
| mrr_usd | DECIMAL(14,2) | `list_price × seats × (1 − discount_pct/100)` — independent of cycle and currency |
| expected_amount_usd | DECIMAL(14,2) | `mrr_usd × billed_months` (pricing check) |
| status_raw | VARCHAR | original text, kept for audit |
| status | VARCHAR | canonical `paid / pending / failed / refunded / void` (§4.3) |
| is_revenue | BOOLEAN | status in (`paid`,`refunded`) |
| payment_method | VARCHAR NULL | `credit_card / ach / wire / invoice`; blank → NULL |
| signup_date | DATE NULL | §5.2 |
| invoice_date | DATE NOT NULL | §5.2 |
| invoice_year / invoice_month | INTEGER / VARCHAR(`YYYY-MM`) | derived |
| date_was_ambiguous | BOOLEAN | DD-MM-YYYY row where both parts ≤ 12 |
| churned | BOOLEAN | `true/TRUE/Yes/1/Y` → true; `false/FALSE/No/0/N` → false; else NULL |
| csat_score | INTEGER NULL | 1–5; blank → NULL (**never** imputed) |
| support_tickets | INTEGER ≥ 0 | |
| dedup_rule | VARCHAR | `unique` / `exact_duplicate_dropped` / `synonym_collapsed` / `conflict_precedence` |
| dq_flags | VARCHAR | `;`-joined issue codes for this row (e.g. `negative_amount_on_paid`) |

### 2.2 `accounts` — one row per `account_id` (snapshot)

Snapshot rule: account attributes (`account_name, region, industry, plan, seats, discount_pct,
churned, csat_score`) are taken from the account's **latest invoice** by `invoice_date`
(tie-break: highest `invoice_id`). The source has no "updated_at", so latest-invoice is the only
defensible "current state". Attribute disagreement across an account's invoices is counted in
`attr_conflicts` (sensitivity reported in `docs/LIMITATIONS.md`).

| Column | Rule |
|---|---|
| account_id PK, account_name, region, industry, plan, seats, discount_pct, churned, csat_score | latest invoice |
| current_mrr_usd | latest invoice's `mrr_usd` |
| is_active | `NOT churned` (NULL churned → not active, counted) |
| first_invoice_date, last_invoice_date, invoice_count | aggregates |
| paid_revenue_usd, refunds_usd, net_revenue_usd | per `financial_metrics.md` |
| attr_conflicts | number of snapshot attributes with >1 distinct value across invoices |

### 2.3 Audit tables (nothing is silently dropped)

* `rejected_rows` — every raw row that is **not** in `invoices`, with `raw_row_number`, `reason`
  (`exact_duplicate`, `synonym_duplicate`, `lost_conflict`, `unparseable_<field>`,
  `unknown_plan`, …) and the full raw record as JSON.
* `dedup_conflicts` — one row per conflicting `invoice_id`: candidate statuses, winner,
  `usd_at_stake` (= |amount_usd| — the revenue swing if the other record were right).
* `dq_issues` — `(issue_code, column, n_rows, example)` summary used by the Data Quality Studio.

## 3. Deduplication rule

1. Drop **exact duplicates** (all 19 raw columns identical after trimming). Keep first raw row.
2. Group the remainder by `invoice_id`. Normalize every field. If all normalized fields agree →
   **synonym duplicate**: keep the first raw row.
3. If they still disagree → **conflict**. No system timestamp exists, so a deterministic
   *evidence-of-money-movement* precedence decides:
   `refunded > paid > failed > void > pending`.
   Rationale: a refund or a capture is a positive event that two systems are unlikely to
   fabricate; `pending` is the least-final state and the most likely to be stale. The loser goes
   to `rejected_rows`, the decision to `dedup_conflicts` with `usd_at_stake`, so the finance team can
   override. The reconciliation impact on paid revenue is reported in `docs/LIMITATIONS.md`.

## 4. Category normalization (case-insensitive, whitespace-trimmed exact lookup — no fuzzy match)

### 4.1 Plan
`starter, start, tier 1` → **Starter**; `pro, professional, tier 2` → **Pro**;
`enterprise, ent, tier 3` → **Enterprise**. Anything else → `unknown_plan` → quarantined.

### 4.2 Billing cycle
`monthly, month, mo` → **monthly**; `annual, annually, yearly, year, yr` → **annual**.

### 4.3 Status (from BUSINESS_CONTEXT table)
`paid, complete, completed, success` → paid · `pending, in_review, awaiting` → pending ·
`failed, declined, error` → failed · `refunded, refund, charged_back` → refunded ·
`void, cancelled, canceled` → void. Unknown → quarantined.

### 4.4 Payment method
`credit_card, credit card` → credit_card · `ach` → ach · `wire, wire transfer` → wire ·
`invoice` → invoice · blank → NULL.

## 5. Parsing

### 5.1 Amount
Accept `4900.00`, `"$4,900.00"`, `"$-4,900.00"`, `"€1,270.08"`, `"£565.78"`, `31432`,
`"1,200.00 EUR"`, `"-9,999.99 USD"`. Steps: strip; record embedded currency (symbol `$ € £` or
3-letter suffix); remove symbol, suffix, thousands commas; parse as Decimal. If the embedded
currency disagrees with the `currency` column → DQ issue `currency_mismatch` (row kept, column
wins). Unparseable → quarantined. Sign is preserved.

Sign rules (DQ flags, not mutations): `refunded` with amount ≥ 0 → `refund_not_negative`;
non-refund with amount < 0 → `negative_amount_on_<status>`.

### 5.2 Dates
| Pattern | Interpretation |
|---|---|
| `YYYY-MM-DD`, `YYYY/MM/DD` | ISO order |
| `MM/DD/YYYY` | US order (evidence §1) |
| `DD-MM-YYYY` | day-first (evidence §1); if both parts ≤ 12 → `date_was_ambiguous = true` |
| `Mon D YYYY` / `Mon DD YYYY` | English month abbreviation |
Anything else → NULL; if it is `invoice_date` the row is quarantined (`unparseable_invoice_date`).
Additional flags: `invoice_before_signup`, `future_invoice_date` (> pipeline run date).

## 6. Open questions for the CloudNova finance lead (decided provisionally, flagged)

1. **FX direction.** Every EUR/GBP `amount` equals the *USD* list amount × the FX rate
   (e.g. 100 Starter seats annual = $49,000 list; the EUR invoice says €52,920 = 49,000 × 1.08).
   Applying the documented `EUR→USD 1.08` again yields $57,153.60 for a $49,000 contract, i.e.
   non-USD revenue is likely overstated by ×1.08² / ×1.27². **Provisional decision:** follow the
   documented rule (`amount_usd = amount_local × rate`) because it is the customer's stated
   definition; the pipeline also stores `amount_usd_alt = amount_local / rate` and the Data
   Quality Studio reports the difference so the finance lead can decide.
2. **Dedup precedence** (§3) — needs confirmation from the billing-system owner.
3. **Account identity.** 200 names map to 3,815 ids; ids are treated as the key.

## Change log
* v1.0 — initial spec, derived from BUSINESS_CONTEXT.md + measured profile above.
* v1.1 — §5.2: day == month in DD-MM-YYYY is not flagged ambiguous (both readings agree).
