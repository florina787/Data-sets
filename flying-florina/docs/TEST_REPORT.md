# Test report

Build machine: Linux x86_64 container, 4 vCPU, Python 3.13.17, Node 22.22.0, Chromium (Playwright 1.63.0). Date: 2026-10-25.

| Suite | Command | Result | Duration |
|---|---|---|---|
| Backend unit/integration | `cd backend && .venv/bin/python -m pytest` | **102 passed**, 0 failed, 0 skipped | ~18 s |
| Lint + security lint | `make lint` (ruff E,F,W,B,S,I) | clean | <1 s |
| Frontend typecheck | `npm run typecheck` | clean (strict) | ~5 s |
| Frontend unit | `npm test` (Vitest) | **9 passed** | ~5 s |
| Frontend build | `npm run build` | success (echarts and react-flow split into their own chunks) | ~9 s |
| End-to-end | `npm run test:e2e` (Playwright, isolated backend + fresh DB) | **13 passed** | ~66 s |
| Offline check | `make offline` | all 10 workflows + 4 reports pass; 0 blocked egress attempts | ~4 s |
| Smoke test | `make smoke` against a running server | 6/6 pass | ~1 s |
| Generated adapter | `pytest` inside `generated_adapters/example_part_availability` | **14 passed** (contract 6, security 6, MCP stdio 2) | ~3 s |
| Security Test Lab | Trust Center → Run all (or `POST /api/policy/tests/run`) | **12/12** scenarios observed as expected | <1 s |

## Coverage of required behaviours

| Requirement | Test(s) |
|---|---|
| Deterministic routing for 10 prompts; clarification | `test_intent.py` |
| Policy allow/deny, role access, kill switch, deny-by-default | `test_policy.py` |
| Export blocking with zero tool calls | `test_export_request_denied_before_tool_and_zero_invocations`, `test_chat_export_denial_via_api_zero_invocations`, e2e governance |
| Prompt injection cannot trigger tools | `test_injected_instruction_is_never_executed`, `test_prompt_injection_is_quarantined`, lab |
| Unauthorized record not retrievable | `test_search_filters_before_ranking`, `test_work_orders_filtered_by_classification`, lab |
| Untrusted tool cannot register | `test_untrusted_tool_cannot_register`, lab, e2e bridge |
| Approvals, SoD, expiry, duplicate approval, replayed write | `test_approvals_sim.py`, `test_approval_flow_over_api`, e2e approval |
| Audit verification and tamper detection | `test_audit_chain_verifies_and_detects_tampering`, `test_audit_verify_endpoint` |
| Agent transitions, parallel waves, retries, permanent failure, cancel, persistence | `test_workflows.py` |
| Evidence citations with revision/date/provenance | `test_citations_carry_revision_date_and_provenance` |
| Reproducibility (seed + same inputs) | `test_seed_is_reproducible`, `test_same_inputs_same_outcome`, `test_replay_reports_reproducibility` |
| Cross-screen consistency | `test_cross_screen_consistency`, e2e fleet |
| Legacy import safety (extension, size, binary, XXE, ZIP traversal/bomb, no execution) | `test_legacy_import_rejections`, `test_zip_*` |
| Adapter generation and execution | `test_bridge_generate_and_run_generated_tests`, e2e legacy |
| MCP stdio discovery and per-call authorization | `test_demo_mcp_server_discovery_and_authorization` |
| Offline behaviour | `test_offline_guard_blocks_external_egress`, `scripts/offline_check.py`, e2e request interception |
| Responsive layout, no dead navigation, guest denials | e2e `pages.spec.ts` |

## Measured latency (rules only, no LLM)
From `scripts/measure_latency.py` on the build machine (`docs/latency_measured.json`): startup including seeding ~1.1 s;
warm median per workflow 58 ms (export denial) to ~970 ms (downtime analysis with 2,000 bootstrap resamples);
AC-204 investigation ~250 ms. These are single-machine measurements, not benchmarks.

## Defects found and fixed during this run
* Dev-mode double login cleared the query cache mid-request, leaving pages stuck on "Loading" → login now resets queries and is guarded against concurrent calls.
* Wide tables caused horizontal page scroll on phones → grid/flex children may shrink; tables scroll inside their card.
* Guest persona was denied at workflow precheck instead of receiving PUBLIC evidence → precheck uses PUBLIC + home-organization attribute; tools enforce data labels.
* Export destination was recorded as `external_email` for personal-email requests → gateway now records the requested destination.

## Not tested
Windows PowerShell scripts were written but not executed (Linux build machine). Docker images were not built.
No formal accessibility audit or load test was performed.
