# Test results and acceptance criteria

Run on 2026-11-03 in the build environment (Python 3.13, Node 22, PostgreSQL 16, Chromium via Playwright).
Local Qwen (Ollama) was **not** running, so every test exercised the deterministic paths.

| Suite | Command | Result |
|---|---|---|
| Backend on PostgreSQL | `TEST_DATABASE_URL=… uv run pytest` | 107 passed |
| Backend on SQLite | `uv run pytest` | 107 passed |
| Frontend typecheck + unit | `npm run typecheck && npm test` | 25 passed |
| Frontend production build | `npm run build` | OK (Plotly lazy-loaded in its own chunk) |
| Browser acceptance (real API + built UI) | `npm run e2e` | 27 passed |

## Acceptance criteria → evidence

| Criterion | Where it is tested |
|---|---|
| Financial totals reconcile | `test_finance.py::test_reconciliation_identities_hold` (4 periods), `test_charts_share_the_same_validated_metrics`, `test_granularities_preserve_totals` |
| Revenue and savings are not double-counted | `test_net_benefit_formula_and_no_double_counting`, `test_attributed_revenue_is_inside_fee_income_every_month`, `test_ai_cash_cost_is_a_line_inside_bank_opex`, `test_bank_revenue_excludes_aum_and_unrealised_returns` |
| Currency conversions are accurate | `test_currency_conversion_is_exact_and_consistent[INR,CAD]`, `test_fx_history_and_new_rate_applies`; e2e "Currency switch" |
| Token accounting is correct | `test_token_rows_sum_to_task_model_cost` (every task), `test_token_totals_match_rows` |
| Cost allocation is consistent | `test_workflow_cost_allocation_by_category`; harness run test checks measured task cost = its cost records |
| Agent task completion is validated | `test_harness.py` (verification of patched code and YAML, rejected runs earn no savings, denied tools fail verification) |
| Productivity comparisons use labelled baselines | `test_human_vs_ai_includes_review_and_rework`; baselines carry `source` and `data_class` and are shown in Graph C |
| Investment controls cannot be bypassed | `test_llm_advisory_cannot_override_block`, `test_block_cannot_be_approved_by_manager`, `test_guardian_run_with_block_is_not_approvable`; e2e "Guardian BLOCK cannot be approved" |
| Manager approvals enforce permissions | `test_material_investment_requires_manager_and_risk` (viewer, engineer, requester and dual-role all refused), `test_escalate_and_request_changes`, `test_unknown_role_rejected`; UI unit test; e2e "Engineer cannot approve; manager can" |
| Charts and filters work | e2e: 8 charts render as Plotly, granularity switch, KPI drill-down, Graph D cost records, currency switch |
| Chat responses match database records | `test_chat_api.py` (AI cost, revenue, net contribution in INR, top token agent, spend drivers, Guardian decisions compared to engine output) |
| Every route displays Sherin's avatar | `avatar.test.tsx` (14 routes, one asset) and e2e on all 14 routes |
| All UI controls function | e2e covers navigation, period/currency/data toggles, drill-downs, chat send + history search, uploads via sample runs, approvals, report download, tablet layout |
| Agent workflows tested end to end | `test_python_debug_run_pauses_for_approval_then_completes`, `test_rejected_run_gets_no_savings_credit`, `test_retry_and_recovery`, `test_tool_permission_denied`, `test_chat_attachment_starts_agent_run`; e2e Python run → approval → completion |
