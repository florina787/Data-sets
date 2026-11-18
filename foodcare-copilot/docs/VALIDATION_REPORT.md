# Validation report — Flo & Jerry 3.0

Run on 2026-11-18 in the project's Linux container (Python 3.13, Node, Chromium via Playwright).
These are actual results from this run, not targets.

## Results

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && ../.venv/bin/python -m pytest` | **192 passed**, 0 failed (3 min 17 s) |
| Browser end-to-end | `cd e2e && npx playwright test` | **12 passed**, 0 failed (3.3 min) |
| Lint | `ruff check backend` | All checks passed |
| Types | `tsc --noEmit` | No errors |
| Production build | `npm run build` | Main bundle 449 kB (135 kB gzip); heavy screens lazy-loaded |

`ruff format --check` reports files that would be reformatted; formatting is not enforced in this
repository and was not changed wholesale.

## What the tests prove

| Requirement | Evidence |
|---|---|
| Policies enforced server-side before LLM, UI, MCP, exports, memory, logs | `test_privacy.py` canaries across every GET endpoint, model prompts, memory, traces, MCP, decoded PDFs |
| CTO role/lens is not a bypass; role changes apply immediately | `test_cto_lens_does_not_bypass_and_role_changes_take_effect_immediately` |
| Tenant isolation | `test_tenant_isolation` |
| No unrestricted SQL; allowlisted, parameterised Databricks queries | `test_databricks_runs_only_allowlisted_parameterised_queries` |
| Kubernetes read-only, sensitive fields dropped | `test_kubernetes_is_read_only_allowlisted_and_drops_sensitive_fields` |
| Connectors never claim "connected" without evidence | `test_registry_is_honest_when_nothing_is_configured` |
| Tool output treated as data (prompt injection) | `test_tool_output_is_neutralised_as_data` |
| MCP read-only, schema-validated, filtered | `test_mcp_server_lists_read_only_tools_and_filters_results` |
| Real, policy-filtered PDFs; ownership checks | `test_pdf_exports_are_real_and_policy_filtered`, `test_new_reports_are_real_and_clean`, `test_exports_enforce_ownership_and_reject_unknown_kinds` |
| X-Ray shows a real, sanitised trace to its owner only | `test_xray_shows_a_sanitised_real_trace_to_its_owner_only` |
| Invalid visuals/actions never rendered | `test_invalid_visuals_and_actions_are_dropped` |
| Multi-turn context | `test_continuous_supplier_investigation`, `e2e/memory.spec.ts` |
| No fabricated threats; correlation ≠ causation | `test_threats_are_classified_grouped_and_never_overclaimed`, `test_downtime_correlation_is_not_causation` |
| Containment: scope, step-up, distinct approvers, expiry, idempotency, dry run | `test_containment_is_guarded_end_to_end`, `test_expired_approval_cannot_execute` |
| Protected OT refused; conversation never executes | `test_protected_ot_and_critical_workloads_are_refused`, `test_conversation_never_executes_containment`, `e2e/command.spec.ts` |
| Savings are avoided expenditure, arithmetic correct | `test_license_savings_arithmetic_and_contract_constraints` |
| Portfolio calculations; ratings never shown | `test_portfolio_calculations_and_privacy`, `e2e/command.spec.ts` |
| Lens changes layout, never permissions | `test_lens_changes_layout_never_permissions` |

## Not validated / not implemented

* **No live external system was tested.** Databricks, Kubernetes, SIEM/EDR, billing and Jira
  adapters were tested against local mock servers or are simulated. Real connection tests need
  your credentials on the server.
* **Motion Story MP4 export** is not implemented (GIF only).
* **No usability study was run.** UX choices are grounded in published research
  (`CTO_UX_RESEARCH.md`); claims about CTO adoption remain hypotheses.
* **Accessibility** was checked by structure (labels, text alternatives, reduced motion, keyboard
  reachability) and by e2e checks for reduced motion and phone width (`geo.spec.ts`). No automated
  scanner (e.g. axe) runs in the suite, and no WCAG audit with assistive-technology users was performed.
* The inspection screen's computer-vision restyle (robot-hero reference) was not done.

Screenshots from the e2e run: `docs/screenshots/40-jerry-threats.png`, `41-containment.png`,
`42-portfolio.png`, `43-guided-defense.png`.
