# Security

| Threat | Control | Where | Verified by |
|---|---|---|---|
| Cross-user data access | Every query is filtered by the authenticated `user_id`. MCP tools receive a server-injected `user_id`. Supabase RLS (`user_id = auth.uid()`) covers direct client access. | `security/auth.py`, `careers/context.py`, `mcp_gateway.py`, migration `0002` | `test_scenario_f_isolated_users`, `test_tool_cannot_target_another_user`, a manual RLS check on PostgreSQL (client `UPDATE trial_usage` changed 0 rows) |
| Trial counter manipulation | No endpoint writes counters. RLS makes metering and billing tables read-only to clients. A check constraint enforces `used + reserved <= 2`. | `billing/metering.py`, `models.py` | `test_trial_counters_cannot_be_modified_by_client` |
| Concurrent trial bypass | An atomic conditional `UPDATE … WHERE used + reserved < limit` | `metering.reserve` | `test_concurrent_requests_cannot_exceed_trial` (12 threads, SQLite and PostgreSQL) |
| Double charge on retry | A unique `(user, feature, Idempotency-Key)` key. Committed results are replayed. | `metering.reserve/commit` | `test_idempotent_retry_does_not_double_charge` |
| Premium access without paying | Entitlements come only from webhook-synced `subscriptions`. A success redirect only polls. Stale periods are ignored. | `metering.active_plan`, `BillingResult` page | `test_stale_subscription_gives_no_access`, scenario E test |
| Webhook forgery and replay | Stripe signature verification. `stripe_events` primary key (replays are skipped). Events older than the last applied one are ignored. | `billing/stripe_service.py` | `test_scenario_e_webhook_unlocks_plan_idempotently_and_in_order` |
| Live charges by mistake | `sk_live_` keys are refused unless `STRIPE_ALLOW_LIVE=true`. | `stripe_service._client` | code review |
| Prompt injection | External text is neutralised and wrapped as untrusted. Tool access is fixed by allowlists, not by the model. Consequential actions need approval. Generated resumes and letters are fact-checked. | `security/sanitize.py`, gateway, approvals | `test_prompt_injection_*` |
| Agent overreach | Per-agent allowlists, a tool budget, timeouts, a recursion limit. Approvals can be decided only by the user via REST. | `mcp_gateway.py`, `agents/graph.py`, `governance/approvals.py` | `test_mcp_discovery_and_allowlist`, `test_autonomous_workflow_requires_approval` |
| Malicious uploads | Extension and magic-byte checks. PDFs with JavaScript, launch actions or attachments are refused. DOCX checks for macros and zip bombs. 5 MB limit. Strict UTF-8 text. Page cap. | `security/uploads.py` | `test_malicious_uploads_rejected` |
| Code execution (coding coach) | AST allowlist (no imports outside a short list, no dunder access, no open/exec/eval), a separate isolated Python process, CPU/memory/file rlimits, an empty temp dir, an empty environment, a wall-clock timeout | `careers/coding.py` | `test_coding_sandbox` (incl. infinite loop) |
| SSRF via URL verification | Only http(s) URLs. Private and loopback hosts are refused. | `jobs/providers.verify_url` | code review |
| Brute force and abuse | Per-IP login/registration limits, per-user chat and tool limits, a global per-IP limit. Canonical-email hash blocks Gmail alias re-registration. No device fingerprinting. | `security/ratelimit.py`, `routers/auth.py` | `test_email_alias_cannot_reregister` |
| Secrets | Environment variables only. Redaction removes secrets from audit logs. Stripe keys stay server-side. Raw card data is never seen (Stripe-hosted Checkout). | `config.py`, `sanitize.redact` | — |
| Transport and headers | HTTPS at the proxy. HSTS in production. nosniff, frame-deny and referrer-policy headers. A CORS allowlist. Bearer tokens, not cookies, so CSRF does not apply. | `main.py`, `frontend/nginx.conf` | — |

## Known gaps before production
- **Coding sandbox:** for untrusted multi-tenant use, also run the runner in a no-network container (gVisor or nsjail). The rlimits and AST checks are defence in depth, not a full jail.
- **Rate limiter:** it is in-process. With more than one API replica, move it to Redis.
- **Dependency scanning:** `pip-audit` and `npm audit` run in CI as warnings. Decide whether a finding should fail the build.
- **Account deletion:** it currently creates an approval request. A support process (or a scheduled job) must complete it and keep Stripe records as the law requires.
