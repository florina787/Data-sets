# Production readiness — evidence and unresolved risks (2026-11-11)

## Test evidence

| Suite | Where it ran | Result |
|---|---|---|
| Backend pytest (SQLite) | local + GitHub Actions | 65 passed locally, 1 skipped (stripe-mock); CI: all passed incl. stripe-mock |
| Backend pytest (PostgreSQL 16, after `alembic upgrade head`) | local (PostgreSQL 16 via pg_ctl) + GitHub Actions | passed |
| Stripe API-spec validation (customer, Checkout Session, Portal) | GitHub Actions with `stripe/stripe-mock:v0.206.0` | 200 responses from all 3 requests (612 validators) |
| Frontend type-check, unit tests (6), build | local + GitHub Actions | passed |
| Browser journeys (Playwright 1.63, Chromium) | local: packaged entrypoint `start.sh`, **real Qwen3-1.7B on 2 cores**, PostgreSQL | **10 passed, 3 skipped** (Supabase email, live job provider, Stripe checkout — need external accounts) |
| Browser journeys, CI configuration (scripted model) | local, same as CI | 10 passed, 3 skipped |
| Concurrency (10 users + 3 streamed chats, whole stack on 2 cores) | local | 0 errors, 3/3 SSE complete — see `HF_COST_AND_CAPACITY.md` |
| Container entrypoint | local (no Docker daemon): `deploy/hf-space/start.sh` with llama.cpp + PostgreSQL | migrations applied, model loaded, readiness `ok`, SPA served on :7860; killing the model server stops the container (supervision) |
| Docker image build + container smoke test | GitHub Actions `space-image` job | see the CI run for this commit |
| Secret scan | GitHub Actions gitleaks + `hf_deploy.py` scan | clean after the fixture fix |

### The ten journeys (Phase 10)
1. Register + sign in + sign out — **passed** (local auth). Email confirmation via Supabase — **skipped (not executed)**.
2. Resume upload → grounded assessment (verified years, career progression) — **passed**.
3. Job discovery with source attribution — **passed with synthetic data (labelled)**; a *real* job — **skipped** (no provider keys).
4. Fact-checked tailored resume + PDF download — **passed** (Qwen summary generated and fact-checked).
5. Interview preparation with rubric + Qwen feedback — **passed**.
6. Career Graph with an actionable next step — **passed**.
7. Trial limit enforced, upgrade prompt, no charge — **passed**.
8. Stripe test checkout → plan only after verified webhook — **skipped in browser**; webhook ordering/idempotency
   covered by backend tests; request shapes by stripe-mock. **A real Stripe test-mode checkout has not been executed.**
9. Cross-user isolation (API 404 + empty UI) — **passed**.
10. Agent prepares an application, waits for approval, user approves — **passed**.
Plus SSE continuity — **passed** (real model, 48 s stream on 2 cores).

### Failure handling verified
- Model server unreachable → features return deterministic results, labelled; degraded chat not charged; readiness
  `degraded` (test `test_features_degrade_when_model_is_down`).
- Database unreachable → readiness `down` + HTTP 503 (test).
- HF router without/with invalid token → `LLMUnavailable` → deterministic fallback; health reports the rejected token
  (live request against `router.huggingface.co` returned 401 and was handled).
- Model process crash → container exits and the platform restarts it (supervisor test).

## Unresolved risks and dependencies

| # | Risk | Impact | Mitigation / next step |
|---|---|---|---|
| 1 | HF Spaces block outbound 5432/6543 | API in a Space cannot use Supabase Postgres | Use Architecture B/C; or request an HF exception and verify with `/api/health/ready` in a private Space |
| 2 | No real Supabase project tested | Email verification, password reset, RLS on the real project unproven | Runbook steps 2 and 6 |
| 3 | No real Stripe test-mode checkout | Webhook delivery/config unproven end-to-end | Runbook step 4 (Stripe CLI `listen`) |
| 4 | No live job-provider calls | Field mapping verified only on fixtures; quotas/terms unchecked | Get keys; run journey 3b; review JSearch/Adzuna commercial terms |
| 5 | Capacity ≈ 2 concurrent chats per 2 vCPU | Queueing (up to ~76 s first token at 3 chats) | More cores, or `LLM_PROVIDER=hf` |
| 6 | Small-model quality | Summaries often restate the resume; 0.6B misses tool choices | Keep 1.7B; fact-check stays mandatory; consider Qwen3.5-9B via router |
| 7 | Single replica, in-process rate limits/metrics | Metrics reset on restart; no horizontal scale | Redis + Prometheus before scaling out |
| 8 | Job-alert digests not sent (no scheduler) | Feature stores alerts only | Add a scheduled worker (cron container) before advertising alerts |
| 9 | Account deletion is a request, not automated | Privacy obligations | Implement deletion job + document retention (runbook step 9) |
| 10 | Coding sandbox not jailed | Abuse risk if public | gVisor/nsjail or disable the Coding Coach for anonymous beta |
| 11 | Hugging Face has no SLA / may suspend | Availability | Keep the VPS path; the image is portable |
| 12 | Docker image never built here | Build issues surface only in CI | `space-image` CI job builds and smoke-tests it |

## Commercial launch readiness (Phase 11)

| Stage | Definition | Status |
|---|---|---|
| Application preparation | Code, packaging, tests, CI/CD, docs | **Done** (this branch) |
| Private beta | Real Supabase + Stripe test mode + invited users; synthetic jobs allowed if labelled | Ready to start after runbook steps 1–7 |
| Public beta (free) | Public URL, live job provider, privacy policy, terms, support email, monitoring alerts | Needs risks 2–4, 9, 10 closed + legal pages |
| Production (paying customers) | Stripe live (approved), Supabase Pro backups, incident process, accessibility review | Needs owner approval + all risks above addressed |

Required before charging customers: privacy policy and data-retention statement (resumes are personal data — PIPEDA in
Canada, GDPR if serving the EU), terms of service incl. subscription/refund terms (already shown in-app), a support
channel and response target, incident/restore procedure (Supabase backups), cookie/analytics disclosure (none used
today), an accessibility review (keyboard navigation, contrast, screen-reader labels — partially implemented, not audited),
and confirmation of job-provider licences for commercial use.

**Job platforms:** Career_flo never scrapes Indeed/LinkedIn (only licensed aggregation via JSearch) and never submits
applications on a user's behalf — "submitted" is a status the user approves after applying on the employer's site.
Keep it that way: automated submission would violate most job platforms' terms.
