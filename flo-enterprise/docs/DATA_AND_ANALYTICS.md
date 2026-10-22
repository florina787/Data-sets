# Data products, synthetic data, financial methodology and scenarios

## Synthetic data (deterministic, seed 20261020)

`data/synthetic/generator.py` produces every record; `manifest()` hashes each table and `tests/unit` proves two runs are
identical. Counts: 100 products, 500 portfolios, 2,000 clients, 50 advisors, 24 month-ends (2024-10-31 → 2026-09-30),
10,000 transactions, 3,000 service interactions, 100 compliance events, 100 decisions, 1,000 historical agent traces
(flagged `synthetic`), plus securities, benchmarks, goals, positions, controls, risks, initiatives and 22 documents.
Referential integrity is enforced by foreign keys (SQLite `PRAGMA foreign_keys`, PostgreSQL constraints) and tests.
PII is obviously synthetic: `@example.com` e-mails, 555-01xx phone numbers, 0-prefixed SINs, labelled `(SYN)` names.
A second tenant (Northwind) exists solely to test isolation.

The data embeds a narrative rather than scripted answers: markets rise with a spring-2025 drawdown, flows rotate from
high-fee mutual funds to ETFs/fixed income/an institutional mandate, a 15 bp fee cut applies from Nov 2025, technology
spend steps up from Aug 2025. Result (measured): AUM +20% over 24 months while revenue yield falls ~150 → ~135 bps and
operating margin ~30% → ~26%.

## D. Governed data products

| Product | Entities | Owner | Classification | Quality checks | Freshness SLA | Access policy |
|---|---|---|---|---|---|---|
| Investment | products, holdings, portfolios, valuations, benchmarks, securities | Office of the CIO | confidential | DQ-INV-001..004 | month-end + 5 bd | investment:read / portfolio:read + ABAC |
| Wealth | clients, goals, positions, advisors, interactions, transactions | Head of Private Wealth | confidential (PI fields restricted) | DQ-WLT-001..005 | daily | client:read + ABAC-CLIENT-ASSIGNMENT |
| Finance | product_monthly, finance_monthly | CFO | confidential | DQ-FIN-001..002 | close + 7 bd | finance:read / exec:read |
| Risk | risk register, compliance events, controls | CRO | confidential | DQ-RSK-001 | weekly | risk:read_aggregate / compliance:read |
| Strategy | decisions, initiatives | Strategy Office | confidential | DQ-STR-001 | monthly | decisions:read/write |

Schemas, lineage and versions are served live by `GET /api/data/products`. Data-quality checks run on demand
(`/api/aiops/data-quality`) and currently report **one real failure**: 396 active clients with KYC older than 730 days.

**Semantic metrics layer** (`analytics/semantic.py`, version `2026.10.1`): 25 governed metric definitions (id, formula,
unit, grain, sources, owner, data product). Every dataset's lineage lists the metric ids it uses.

## F. Financial methodology

* **Currency** CAD; amounts stored as integer cents; computed with `Decimal` (34-digit context); quantized once to the
  cent with ROUND_HALF_EVEN. Statistics (volatility, Sharpe, correlation) are floats — estimates, not ledger amounts.
* **Periods**: month-end valuations; trailing windows of 12 or 24 month-ends; prior period = equal preceding window.
* **AUM roll-forward**: `close = open + subscriptions − redemptions + market`; every product-month reconciled to the cent.
* **Net flows** = subscriptions − redemptions; **organic growth** = net flows / opening AUM × 12 / months.
* **Management fee revenue** = avg(open, close) × fee bps / 10,000 / 12; ledger revenue is reconciled to product accruals.
* **Revenue yield** = annualized revenue / average AUM × 10,000.
* **Revenue attribution** (exact): Δrevenue = volume (ΔAUM × y₀) + rate (Δy × AUM₁); rate = mix Σ(s₁−s₀)f₀ + fee Σs₁(f₁−f₀).
* **TWR**: geometric linking of `(MV_close − flow)/MV_open − 1` (flows at month-end). **MWR**: IRR of opening value,
  external flows and closing value (bisection, 1e-10). Annualized only for ≥ 12 months.
* **Volatility** sample stdev × √12; **Sharpe** mean excess over T-bill × 12 / (stdev × √12); **max drawdown** on the
  wealth index; **tracking error / information ratio / beta**; **HHI** and effective N; **drift** = ½ Σ|w − target|.
* **Product contribution** (illustrative management allocation): revenue − 40 bp trailer on mutual funds − shared costs by revenue share.
* **Fee impact**: amount × (1+g)ⁿ vs amount × (1+g−fee)ⁿ.
* The LLM never computes figures: narratives are rendered from tool facts and the harness rejects any narrative
  containing a number not present in the facts (numeric grounding check).
* Unit tests with hand-computed expectations: `tests/unit/test_analytics.py` (release-blocking).

## S. Scenario simulator & strategy twin

`scenarios/engine.py`: inputs (equity/bond shocks, rate shock, inflation, net flows, stress redemptions, fee compression,
opex growth, technology investment, expected returns, horizon) → AUM path, revenue, expenses, operating income/margin,
asset-class and portfolio impacts, base/bull/bear/severe-stress comparison, one-at-a-time sensitivity (tornado), and
full assumption traceability (each input labelled preset / user override). Fixed assumptions (duration 6.5, EM beta 1.2,
60/40 balanced mix, instantaneous shock) are listed in every output. **No probabilities or confidence intervals** are
produced; outputs are conditional on stated assumptions.
