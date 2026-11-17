# Risk register

| # | Risk | Likelihood | Impact | Mitigation in place | Residual / owner action |
|---|---|---|---|---|---|
| R1 | Look-ahead bias in features/labels | High (it happened) | Critical | Cohort ranking by `available_at`; truncation tests incl. mid-UTC-day cut; purge + embargo tests | A cross-timezone rank leak was found and fixed this session; keep the tests mandatory in CI |
| R2 | Survivorship bias | High | High | Securities master keeps delisted names; `universe_as_of`; delisting returns realised | Real data needs historical index membership |
| R3 | Synthetic results mistaken for real skill | Medium | High | `SYNTHETIC` status on every row, API response, UI badge and banner; risk engine rejects SYNTHETIC orders | Keep generator out of production builds |
| R4 | Overfitting / multiple testing | High | High | Baselines, single holdout pass, promotion criteria | Add deflated Sharpe and experiment counting |
| R5 | Strategies that only work before costs | High (observed) | High | Gross vs net everywhere; net Sharpe gate | Calibrate cost model to real spreads/fees per venue |
| R6 | Stale data presented as live | Medium | High | Freshness → `CACHED`; per-horizon data-age gates; no live feeds = no horizon "ready" | Live feed SLAs once connected |
| R7 | AI agents overriding risk limits | Medium | Critical | Risk engine has no agent/judge input (signature test); hard caps clamp all profiles | Keep the agent layer outside execution path |
| R8 | Tampering with past forecasts | Low | High | DB triggers block UPDATE/DELETE; SHA-256 hash chain; `verify_chain` shown in UI | Off-box anchoring of chain head (e.g. daily signed digest) |
| R9 | Regulatory: personalised advice | Medium | High | Research/education framing; no brokerage; disclaimer on every page | Legal review per jurisdiction before personalised recommendations or execution |
| R10 | Data licensing violations | Medium | High | Licence notes in provenance; matrix documents terms | Contract review before redistribution/display of vendor data |
| R11 | Crash-risk alarm false confidence | High | Medium | Precision/recall/base rate shown next to the meter | Current alarm is weak (10% precision vs 6.6% base) — improve before relying on it |
| R12 | Feedback loops from self-generated labels | Low | High | Outcomes only from market data; no auto-retrain | — |
| R13 | Secret leakage | Low | High | Keys only from env; none committed; no secrets in logs | Add secret scanning in CI |
| R14 | Single-maintainer bus factor / undocumented ops | Medium | Medium | Reproducible CLI commands, CI smoke | Ops runbook when hosted |
