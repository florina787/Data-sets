# Test results (actual runs)

Run on 2026-10-11 in a Linux container: Python 3.13, Node 22, Chromium 1194. Default modes: deterministic language,
synthetic fixtures, simulated deployment; no paid credentials.

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration + security | `cd backend && python -m pytest -q` | **134 passed, 1 skipped** (the optional live-LLM test, skipped unless `LIVE_LLM_TESTS=1` and a key is set) in ~21 s |
| Frontend typecheck | `npm run typecheck` | pass |
| Frontend unit (vitest) | `npm test` | **6 passed** |
| Frontend production build | `npm run build` | pass |
| End-to-end (Playwright, real backend + built UI) | `npx playwright test` | **2 passed**: the full BR-101 journey across 8 personas, and a server-side refusal of an unauthorized action |
| Migrations | `alembic upgrade head && alembic check` | pass (SQLite and PostgreSQL 16) |
| PostgreSQL smoke | migrate, seed, rc1 FAIL, rc2 PASS, simulated canary, audit chain valid | pass |
| Docker Compose | `docker compose build && up` | pass: images built, `/ready` OK through nginx, BR-101 served; state persisted across `docker compose restart backend` |
| Fixture reproducibility | `python -m app.datagen.synthetic && git diff --exit-code data/synthetic` | no diff |

Not run here: the GitHub Actions workflow itself, gitleaks, Trivy, pip-audit and npm audit. They are configured in
`.github/workflows/beauty-ai-copilot-ci.yml` and run on GitHub. The Docker build in this sandbox needed
`EXTRA_CA_FILE` because of a TLS-intercepting proxy.

## Coverage of required test areas

| Required area | Test(s) |
|---|---|
| All legal and illegal lifecycle transitions | `test_every_legal_transition_is_permitted` (parametrised over the full table), `test_illegal_transitions_rejected`, `test_all_pairs_covered` |
| Gate arithmetic | `test_regression_boundary_exact_threshold_passes` (−2.00 pp passes), `test_regression_just_beyond_threshold_fails_despite_target_gain` (−2.01 pp fails), `test_target_below_minimum_fails`, `test_thresholds_take_stricter_value` |
| Subgroup regression despite overall gain | `test_failing_candidate_hides_subgroup_regression_and_blocks` |
| Insufficient sample size | `test_insufficient_samples_is_inconclusive_never_pass`, `test_missing_required_cell_is_inconclusive`, `test_insufficient_samples_inconclusive_via_stricter_criteria` (end to end) |
| Abstention denominator | `test_abstention_stays_in_denominator`, `test_abstaining_model_does_not_look_better` |
| Artifact mismatch | `test_artifact_tampering_fails_evaluation`, `test_artifact_mismatch_after_approval_blocks_deploy` |
| Outdated approval | `test_expired_approval_blocks_deploy`, `test_policy_change_invalidates_approval`, `test_reevaluation_invalidates_prior_reviews` |
| Duplicate deployment and replay | `test_replay_and_duplicate_deployment`, `test_idempotency_key_required_and_reuse_with_different_body` |
| Rejected release | `test_rejected_release_cannot_deploy`, `test_release_approval_requires_reviews` |
| Failed rollback | `test_failed_rollback_keeps_state`; rejection path `test_rollback_rejection_returns_to_monitoring` |
| Checkpoint resume | `test_checkpoint_resume_after_node_failure` (evidence is not re-run) |
| Background jobs, cancel, restart recovery | `test_background_job_and_cancel_and_recovery`, `test_real_thread_pool_job_completes` |
| Cross-tenant access | `test_cross_tenant_access_denied` |
| Server-side roles | `test_server_side_roles_enforced`, e2e “unauthorized action is refused” |
| Production mode / persona selector | `test_production_mode_disables_persona_selector` |
| Prompt injection in knowledge | `test_prompt_injection_in_knowledge_cannot_change_policy_or_roles` |
| Authorization before retrieval | `test_restricted_document_filtered_before_retrieval` |
| Citations resolve | `test_evidence_citations_resolve_and_flags`, `test_citation_validation_detects_unresolved_and_tampered` |
| Invalid agent JSON / no silent switching | `test_invalid_agent_json_rejected`, `test_invalid_agent_json_recorded_not_silently_switched` |
| Favourable summary cannot override gates | `test_favourable_summary_cannot_override_failed_gate`, `test_overclaiming_summary_rejected_and_gate_unchanged` |
| Missing credentials | `test_missing_credentials_shows_unconfigured` |
| Unconfigured real adapters | `test_real_prediction_and_deployment_modes_unconfigured` |
| Secret redaction | `test_secret_and_image_redaction`; control test CT-LOG-REDACTION runs in every evaluation |
| Image validation and deletion | `test_image_sandbox_disabled_by_default`, `test_image_validation_and_deletion` |
| Persistence across restart | `test_state_persists_across_restart`; Docker restart check |
| Backup and restore | `test_backup_and_restore_roundtrip` |
| Concurrency guard | `test_concurrent_modification_detected` |
| Audit tamper detection | `test_audit_chain_detects_tampering` |
| Seeded journey end to end | `test_corrected_candidate_passes_and_full_release_rollback_flow`; Playwright journey |

## Prototype gates from the brief

| Gate | Status |
|---|---|
| All safety and permission tests pass | Yes |
| Every seeded scenario reaches its expected state | Yes: rc1 → EVALUATION_FAILED; rc2 → REVIEW_REQUIRED → … → ROLLED_BACK; stricter criteria → EVALUATION_INCONCLUSIVE |
| No unauthorized release occurs | Yes: blocked without reviews, with expired, replayed or invalidated approvals, with digest mismatch, or by the wrong role |
| All citations resolve | Yes: every stored citation opens its exact excerpt (tested) |
| Clean startup without paid credentials | Yes: local and Docker |

## Defect found and fixed during testing

The first full-suite run had one failure. The monitoring simulator seeded its draws with the random release ID, so a
chance false alert (DEV-T2 × warm) occasionally appeared. The simulator is now seeded by model, lighting map and
window index, which makes the demo reproducible. The episode also shows that a statistical alert alone does not
establish a cause.
