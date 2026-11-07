# Requirements traceability

Source: `docs/ASSIGNMENT.md` (A) and `data/raw/BUSINESS_CONTEXT.md` (B). Status vocabulary: IMPLEMENTED (code
exists) → TESTED (an automated test or eval exercises it and passes) · NOT_APPLICABLE · DEFERRED.
Verified 2026-11-07 with `python -m pytest` (114 passed) and `python -m evals --llm` (PASS 33 · FAIL 0 · XFAIL 3).

| ID | Source | Requirement | Class | Evidence (file / function) | Test / eval | Status |
|---|---|---|---|---|---|---|
| R1 | A · Track B | Spec for cleaned schema: types, constraints, dedup, normalization, dates, FX→USD, MRR | mandatory | `specs/cloudnova_data_contract.md`, `specs/financial_metrics.md` (committed before pipeline: `git log`) | `tests/test_rules.py`, `tests/test_pipeline.py` | TESTED |
| R2 | A · Track B | AI generates transformation code from the spec | mandatory | `app/pipeline/{rules,clean,build}.py`; `.claude/prompt-history.md` §3–4 | `tests/test_pipeline.py::test_every_raw_row_is_accounted_for` | TESTED |
| R3 | A · Track B | NL question → query over cleaned data, answer **with generated query shown** | mandatory | `app/agent/supervisor.py::ask`, `app/semantic/planner.py::compile_sql`, `tools.run_llm_sql`; `sql` field in every answer | evals FU-*, OE-*, `tests/test_planner.py` | TESTED |
| R4 | A · Track B / B | Correct revenue/MRR/churn stakeholder answers | mandatory | README §3 | evals Q1–Q6 vs `evals/oracle.py` | TESTED |
| R5 | A | Runnable from a single command | mandatory | `python -m app` → `app/startup.py::up` | README §7 (4 scenarios, fresh shell); CI runs `python -m app demo` | TESTED (manual + CI smoke) |
| R6 | A · deliverable 1 | README: run, spec, decisions, next day, limitations | mandatory | `README.md` §1–9, `docs/LIMITATIONS.md` | — | IMPLEMENTED |
| R7 | A · deliverable 2 | `.claude/` / CLAUDE.md showing AI steering + trimmed log | mandatory | `CLAUDE.md`, `.claude/prompt-history.md`, `docs/VERIFY.md` | — | IMPLEMENTED |
| R8 | A · deliverable 3 | Architecture diagram matching the code | mandatory | `docs/architecture.md` (Mermaid; module paths in labels) | — | IMPLEMENTED |
| R9 | A · deliverable 4 | `/specs` | mandatory | 5 specs | — | IMPLEMENTED |
| R10 | A · deliverable 5 | Eval harness, ≥5 cases, pass/fail view, ≥1 expected failure with reason | mandatory | `evals/__main__.py`, `evals/cases.yaml` (36 cases, 3 XFAIL with reasons) | `python -m evals` | TESTED |
| R11 | A · deliverable 6 | One production-hardening touch | bonus | CI workflow · read-only SQL guard · structured errors · health/readiness · graceful shutdown | `tests/test_governance.py`, CI | TESTED |
| R12 | A | Secrets not committed; `.env` + `.env.example` | mandatory | `.gitignore`, `.env.example` (no secrets needed) | — | IMPLEMENTED |
| R13 | A | Honest git history | mandatory | milestone commits: specs → pipeline → query layer → evals/tests → startup/UI → reconciliation/API/docs | — | IMPLEMENTED |
| B1 | B | Only `paid` = revenue; refunded negative nets; pending/failed/void excluded | mandatory | `catalog.py` paid_revenue / net_revenue / refunds | Q1, Q3, OE-*; `test_status_aliases` | TESTED |
| B2 | B | List prices 49/99/299; annual = 10 months; discount on gross | mandatory | `rules.LIST_PRICE_USD`, `BILLED_MONTHS`; pricing check (0 violations) | `test_annual_and_mrr_and_fx`, `test_built_database_invariants` | TESTED |
| B3 | B | FX EUR 1.08, GBP 1.27, fixed | mandatory | `config.py` (env), `rules.to_usd` | `test_fx_conversion_documented_and_inverse`, XFAIL-q1-inverse-fx | TESTED (open question documented) |
| B4 | B | MRR = list × seats × (1−disc), annual not double-counted | mandatory | `rules.mrr_usd`, `accounts.current_mrr_usd` | `test_mrr_is_independent_of_cycle_and_currency`, Q2 | TESTED |
| B5 | B | Normalize plan/status/cycle/boolean variants | mandatory | `rules.py` maps (unknown → quarantine) | `test_rules.py` (40+ params) | TESTED |
| B6 | B | Mixed/ambiguous dates: decide & document rule | mandatory | data contract §5.2 (evidence), `rules.parse_date` | `test_dates` | TESTED |
| B7 | B | Messy amounts (symbols, commas, suffix, missing cents, negatives) | mandatory | `rules.parse_amount` | `test_amount_parsing` | TESTED |
| B8 | B | Nulls / malformed emails | mandatory | `rules.norm_email`, no imputation | `test_nulls_not_imputed_and_flags` | TESTED |
| B9 | B | Full + near duplicates, documented winner rule | mandatory | data contract §3, `clean.clean`, `dedup_conflicts`, `app/reconciliation.py` | `test_conflict_precedence_and_audit`, DQ-row-accounting, `test_reconciliation_*` | TESTED |
| B10 | B | Be honest about what it gets wrong and why | mandatory | README §3 "Where we may be wrong", LIMITATIONS, 3 XFAILs | evals XFAIL-* | TESTED |
| U1 | user | Local Qwen only, no paid APIs | mandatory (user) | `app/llm/provider.py` (OpenAI-compatible local), `docs/ENVIRONMENT.md` | LLM-* evals (live Qwen), `test_qwen_provider_against_fake_openai_server` | TESTED |
| U2 | user | Reuse existing copilots | mandatory (user) | `docs/REUSE_MATRIX.md`; source headers in `harness.py`, `errors.py`, `guards.py`, `provider.py` | `test_text_to_sql_path_with_scripted_model` | IMPLEMENTED |
| U3 | user | Reconciliation view 5,125 → 5,000 + 125 with $ impact | requested | `app/reconciliation.py`, `/api/v1/reconciliation`, dashboard | `test_reconciliation_accounts_for_every_row_and_dollar` | TESTED |
| U4 | user | Qwen-only vs hybrid comparison | requested | `evals/compare_modes.py`, `evals/results/mode_comparison.md` | measured run (6/6 vs 2/6) | TESTED (measured) |
| U5 | user | Versioned REST API + adapter architecture | requested | `/api/v1/*`, `app/sources/`, `docs/INTEGRATION_ARCHITECTURE.md` | `test_v1_api_contract`, `test_csv_adapter_enforces_raw_contract` | TESTED |
| U6 | user | Isolation Forest only if justified | optional | README §6 rationale (0 pricing violations; not explainable value here) | — | DEFERRED (by decision) |
| U7 | user | Premium dashboard | optional | `app/web/static/*` | `test_api_ask_health_and_errors` serves `/`; Playwright screenshots during build | IMPLEMENTED |
| U8 | user | Demo script | requested | `docs/DEMO_SCRIPT.md` | — | IMPLEMENTED |
