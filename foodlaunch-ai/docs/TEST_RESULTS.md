# Test results

Recorded on 2026-10-09 in the build container: Linux, Python 3.13.16, Node 22.22, Chromium 141 (Playwright 1.56.1). Every number below comes from commands that actually ran. Re-run them with `scripts/test.sh` and `npm run e2e`.

## Summary

| Check | Command | Result |
|---|---|---|
| Platform lint | `ruff check backend scripts` | passed |
| Storefront lint (policy config) | `ruff check` in `v1.2-timeout-repair` | passed |
| Fixture patches in sync with stage trees | `python scripts/regen_fixture_patches.py --check` | passed |
| Backend tests | `python -m pytest` | **23 passed** in 68.8 s |
| UI typecheck | `npm run typecheck` (strict TS, both apps) | passed |
| UI build | `npm run build` | passed (control room 234 kB JS / 71 kB gzip) |
| Browser end-to-end | `npm run e2e` | **2 passed** in 2.0 min |
| Guided demo via API (13 checked steps) | `POST /api/demo/run` | **13/13 done** in about 40 s (latest run 42.1 s) |

Warnings: pytest reports one third-party `DeprecationWarning` (Starlette TestClient's `anyio.abc.BlockingPortal`). LangChain/LangGraph emits an `allowed_objects` pending-deprecation notice at import time. Neither comes from project code.

## Acceptance suite against each storefront stage

The protected suite (`fixtures/acceptance_tests`, 29 tests including parametrisations) was run directly against each stage tree:

| Stage | Result | Failing tests |
|---|---|---|
| `v1.1-campaign-faulty` (patch 01) | 5 failed, 24 passed | REG-001 ×3 (free unit kept after removal / checkout charges / province change), REG-002 ×2 (timeout) |
| `v1.1-campaign-fixed` (+ patch 02) | 2 failed, 27 passed | REG-002 ×2: inventory timeout → 500 after the 4 s upstream delay |
| `v1.2-timeout-repair` (+ patch 03) | **29 passed** | – |

In the product, plan v1 (27 tests, no resilience file) is used for the campaign release, which is why the first release passes. Plan v2 adds `test_resilience.py` after the incident (REQ-9). The platform reproduces the failure on the released revision before repairing.

## Coverage of the required behaviours

| Required behaviour | Where it is verified |
|---|---|
| Eligible quantities, unrelated products, one free unit | `test_campaign_rules.py` AC-1.x |
| Removal of paid items recomputes the cart (REG-001) | `test_removing_qualifying_paid_units_removes_the_free_unit`, `test_checkout_after_removal_charges_for_every_unit`, `test_changing_province_away_from_ontario_removes_free_unit` |
| Province eligibility | AC-3.1 tests |
| Campaign boundaries including DST | `test_campaign_window_is_converted_from_toronto_time_across_dst`, 5 boundary instants (including 23:30 EST on Nov 1), ambiguous/nonexistent local times rejected |
| Discount stacking | `test_discount_codes_do_not_stack_with_free_unit` |
| Exhausted inventory | `test_exhausted_inventory_rejects_checkout_without_side_effects` |
| Duplicate redemption | `test_one_free_unit_per_customer_per_campaign`, `test_repeated_checkout_request_is_idempotent` |
| Concurrent checkout | `test_concurrent_checkouts_redeem_at_most_once` (4 threads, barrier) |
| Payment failure | `test_payment_failure_releases_reservation_and_entitlement` |
| Cancellation and refunds | `test_full_cancellation_refunds_everything_and_restores_entitlement`, `test_partial_return_refunds_allocated_promotion_amount`, `test_units_outside_promotion_group_refund_at_full_price_first` |
| Timeouts | `test_resilience.py` (real slow HTTP server; 503 within 3 s, cart kept, no order; recovery) and `test_runner_enforces_allow_list_cwd_timeout_and_credential_scrubbing` |
| Authorization | `test_release_approval_permissions_binding_and_duplicates`, `test_role_permissions_are_enforced_server_side`; e2e engineer approval → 403 |
| Stale approvals | `test_release_approval_permissions_binding_and_duplicates` (wrong hash), `test_new_commit_invalidates_pending_approval`; old-revision evidence rejected by G3 in `test_full_delivery_flow_produces_failing_then_passing_evidence` |
| Invalid transitions | `test_invalid_transitions_are_rejected_and_recorded`, `test_brief_requires_recorded_decisions_before_implementation` |
| Interrupted-run resume | `test_interrupted_run_resumes_from_checkpoint_without_duplicate_work` (simulated crash and graph rebuild; one change set only) |
| Pause and continue | `test_pause_stops_after_current_node_and_continue_resumes`; e2e `guided.spec.ts` |
| Rollback | `test_deploy_starts_exact_revision_and_rollback_restores_last_known_good` (real processes, health shows the expected SHA) |
| Protected tests cannot be weakened | `test_modified_protected_tests_are_refused`; gate G7 |
| Patch and path safety | `test_patch_validation_rejects_unsafe_changes` (5 cases), `test_source_reading_is_scoped_to_the_workspace` |
| LIVE mode without credentials | `test_live_mode_without_credentials_fails_visibly` |

## Browser verification (Playwright)

`e2e/flagship.spec.ts` runs the full chain through the UIs, on an isolated server (ports 9700/9801, its own `var-e2e/`):

brief clarification (Q-ONCE policy gap) → implementation request rejected → seeded decisions → requirements approval → **failing pytest output** (REG-001) → candidate diff → **same tests passing** → engineer approval **rejected (403)** → approver approves the exact manifest → **local deployment** → storefront: free unit added, removed on recompute, re-claimed, order paid ($4.98) → **injected timeout** → real 500s → **incident evidence** (scripted-fault disclaimer, `timeout=None` hypothesis) → **rollback** → REQ-9 approval → repair release approved and deployed → storefront under fault shows "Checkout temporarily unavailable", cart unchanged → fault cleared → incident **resolved** → order succeeds.

`e2e/guided.spec.ts` covers Reset Demo, Run Guided Demo, Pause (stops between steps), Continue and completion (13/13).

## Screenshot review

Screenshots are in [screenshots/](screenshots/), regenerated by the e2e run. Reviewing them found these issues, all fixed and re-verified:

* the revision chip in the header was invisible (cream text on cream);
* the release list could briefly show `approved` after a deploy (refreshes are now awaited);
* the manifest hash overflowed its card;
* an active fault was shown with a "failed" badge;
* the fault disclaimer was duplicated;
* the test-results and telemetry tables clipped their columns;
* the session still appeared signed in after Reset Demo;
* a stale fault indicator showed after the guided demo finished.

## Not verified

* LIVE mode against the real Anthropic API. No key was available. The code path is implemented and the no-credentials failure is tested.
* Container-isolated execution. No Docker daemon was available; see [SECURITY_AND_SANDBOX.md](SECURITY_AND_SANDBOX.md).
* Windows and macOS. Process-group handling and resource limits are POSIX-specific.
* Screen-reader testing with assistive technology. Semantics were checked through Playwright role and label queries and a manual review, not with NVDA or VoiceOver.
