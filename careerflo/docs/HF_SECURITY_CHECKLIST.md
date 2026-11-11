# Security checklist for deployment (Hugging Face Spaces / VPS)

Legend: ✅ implemented and tested · 🔧 implemented, needs configuration at launch · ⬜ owner action / not yet done.

## Secrets and configuration
- ✅ No secrets in the repository; CI runs **gitleaks v8.30.0** on every push (one known test-fixture false positive is
  ignored by exact fingerprint in `.gitleaksignore`).
- ✅ `scripts/hf_deploy.py` scans the staged upload for Stripe, HF, GitHub, AWS keys, private keys and password-bearing
  Postgres URLs, and **refuses** to deploy on a finding; refuses live Stripe configuration (`STRIPE_ALLOW_LIVE=true` or
  `sk_live_…`). Covered by `tests/test_deploy_scripts.py`.
- ✅ Secret values synced to a Space are never printed (test asserts this).
- 🔧 Space **Secrets** (private) for: `DATABASE_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `JSEARCH_API_KEY`,
  `ADZUNA_*`, `GITHUB_TOKEN`, `HF_TOKEN`, `ADMIN_EMAILS`. Space **Variables are public** — only non-sensitive values
  (`deploy/hf-space/space.env.example` marks each).
- 🔧 HF tokens: fine-grained, least privilege — CI deploy token: *write to the one Space*; runtime token (only if
  `LLM_PROVIDER=hf`): *Make calls to Inference Providers* only.
- 🔧 GitHub environment `huggingface-production` with **required reviewers** gates deploy and rollback workflows.
- ⬜ Rotate any credential that was ever pasted into chat, logs or a ticket.

## Network exposure
- ✅ The model server listens on `127.0.0.1:8081` inside the container; only the API port (7860) is exposed.
- ✅ VPS: Caddy terminates TLS (HSTS); the app container publishes no host port.
- ✅ CORS allow-list from `CORS_ORIGINS`; bearer tokens (no cookies) so CSRF does not apply.
- 🔧 New Spaces are created **private**; making the app public is an explicit `--visibility` step after approval.

## Identity and data isolation
- ✅ Supabase ES256 tokens verified against the project's JWKS (tested with real signatures: valid, forged key, expired,
  wrong audience). User row id = `auth.uid()`; email change keeps the same account and trial counters.
- ✅ Every query filters by the authenticated user; MCP tools receive a server-injected `user_id` (forged ids rejected).
- ✅ Supabase RLS migration: 37 policies; metering/billing tables read-only to clients.
- ⬜ Run the RLS verification queries in the runbook against the real Supabase project.
- ✅ Container disk is ephemeral; no user data is written to Hugging Face repos, datasets, cards or logs. Request logs
  record route templates (ids collapsed), never bodies.

## Payments
- ✅ Entitlements only from signature-verified, idempotent, order-checked webhooks; success redirect never unlocks.
- ✅ Stripe request shapes validated against Stripe's OpenAPI spec (stripe-mock 0.206.0) in CI.
- 🔧 Test-mode keys only. ⬜ Live mode requires explicit owner approval and `STRIPE_ALLOW_LIVE=true`.

## Application hardening (unchanged from `docs/SECURITY.md`)
- ✅ Upload validation, prompt-injection neutralisation, fact-checking, approval gates, rate limits, sandboxed coding runner.
- ⬜ Coding sandbox: run in a no-network jail (gVisor/nsjail) before opening to the public internet.
- ⬜ Multi-replica: move rate limiter and request metrics to Redis/Prometheus (single replica today).
- ⬜ Dependency audits (pip-audit / npm audit) currently warn instead of failing CI — decide policy.

## Supply chain
- ✅ Base image pinned by digest (`ghcr.io/ggml-org/llama.cpp:server-b12199@sha256:ca4072…`); uv pinned (0.11.32);
  `uv.lock` / `package-lock.json` used with `--frozen` / `npm ci`.
- ✅ Model weights pinned by repository revision and verified with SHA-256 at build time.
