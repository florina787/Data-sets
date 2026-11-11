# VEENA.AI — commercial launch readiness

Date: 2026-11-11 · Branch `claude/amazing-babbage-qia83y` · Builds on `PRICING_AND_BILLING_READINESS.md` and `FOUNDER_INSIGHTS_READINESS.md`.
**Nothing deployed or published. No live Stripe keys. No Cloudflare, Stripe or email resources created. No billing settings changed.**

## Recommendation: **C** — keep the 0.1.0 draft as it is; ship plans in a separate, tested release candidate
The 0.1.0 draft installers are verified (below) and its "free, no account, no subscription" wording is **accurate for that build**, because billing is compiled in but disabled (`BILLING_URL = ""`). Monetization code is complete and tested locally, but it is **blocked from launch** by items that need you: Stripe sandbox testing (no test key was provided), an email provider, policies, tax decision and deployment approval. Publishing 0.1.0 as a free beta (option A) is also safe and accurate if you want users before plans are ready; it doesn't conflict with C.

---

## 1. Implemented features
| Area | State | Where |
| --- | --- | --- |
| Free trial: 3 successful uses per verified feature, independent per feature | Implemented, tested | `cloud/billing` ledger; app metering |
| Trial persistence across sign-out and reinstall (same account) | Implemented, tested | per-account + per-installation counters |
| Verified identity (email one-time code) | Implemented, tested; **needs an email provider** | `authStart` / `authVerify`, `makeMailer` |
| Duplicate-trial protection (no fingerprinting) | Implemented, tested; best-effort by design | per-install counting, 3rd-account rule, appeals |
| Stripe Checkout (credits + subscriptions), portal, webhooks | Implemented; **tested only against a simulator** | `cloud/billing/src/worker.js` |
| Credit ledger, history, refunds, subscription lifecycle | Implemented, tested (simulator) | same |
| Entitlement enforcement in the app | Implemented, tested end to end; **disabled** until `BILLING_URL` is set | `backend/billing`, chat + interview routes |
| Offline behaviour | Implemented, tested (3 uncharged uses per feature, then reconnect) | `backend/billing` |
| Pricing page (Unlimited / Credits / Custom + Free Trial) | Implemented, QA-tested; marked **preview** while `plansLive: false` | `site/pricing.html` |
| Founder dashboard + opt-in statistics | Implemented, tested | `cloud/insights`, Settings |

**Partially implemented / missing:** real Stripe sandbox evidence; email delivery; credit rate for Ask anything/Documents/Screen (not charged; proposal §5); written policies (drafts only); tax collection (off); deployment.

## 2. Stripe sandbox test evidence
**No real Stripe sandbox tests have been run.** You declined the secure key form, so none of the items below are claimed as passed against Stripe. They pass against a local simulator that uses Stripe's request formats and its webhook signature scheme (HMAC-SHA256 over `t.payload`):

| Scenario | Simulator | Real sandbox |
| --- | --- | --- |
| Checkout session creation (payment and subscription mode, USD, exact amounts) | Pass | **Blocked** (needs `sk_test_`) |
| Successful credit purchase → balance | Pass | Blocked |
| Failed / unpaid payment grants nothing | Pass | Blocked |
| Delayed payment success (`async_payment_succeeded`) | Pass | Blocked |
| Expired checkout session grants nothing | Pass | Blocked |
| Subscription create, renew (`invoice.paid`), failed payment, cancel | Pass | Blocked |
| Subscription expiry (no access after the paid period) | Pass | Blocked |
| Refund: credits reversed proportionally; full subscription refund ends Unlimited | Pass | Blocked |
| Duplicate / stale / tampered webhooks | Pass | Blocked |
| Customer portal session | Pass | Blocked |

**To unblock (about 20 minutes):** Stripe Dashboard → **Switch to sandbox** → Developers → API keys (`sk_test_…`). Then either provide it through the secure form (say "add my Stripe test key"), or deploy the Billing Worker yourself with `wrangler secret put STRIPE_SECRET_KEY`. Add a webhook endpoint `https://<billing-worker>/v1/stripe/webhook` for: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `charge.refunded`. Then run Stripe test cards: `4242 4242 4242 4242` (success), `4000 0000 0000 0002` (decline), `4000 0000 0000 0341` (attaches but later fails, for renewal failures), plus a refund and a portal cancellation; and `stripe trigger` / "Resend" on an event to confirm replay protection.

## 3. Email provider recommendation
| Option | Free allowance (checked 2026-11-11) | Fit |
| --- | --- | --- |
| **Resend** | 3,000 emails/month, **100/day**, 3 domains, 30-day log retention | **Recommended**: simple HTTPS API from a Worker, domain authentication (SPF/DKIM) required, no SDK needed |
| Cloudflare Email Sending | Arbitrary recipients **require Workers Paid** (beta) | Not zero-cost |
| Brevo | Pricing page could not be read; **not verified** | Re-check before considering |

Implemented: `makeMailer(env)` (provider-independent; Resend adapter sends only the address, subject and the code; unconfigured = sign-in disabled, fails closed). Codes are 6 digits, hashed with a secret pepper, single-use, expire in 10 minutes, max 5 attempts; 5 code requests per email and 10 per installation per day. **Limit to plan for:** 100 sign-ins/day on the free tier. Not created: any Resend account (needs your approval and a domain you control; `github.io` can't be verified, so a custom domain is needed for sending, about US$10–15/year).

## 4. Security findings and fixes (this audit)
| # | Finding | Fix | Test |
| --- | --- | --- | --- |
| 1 | Another account's operation id returned "allowed" | Scoped to the account (409) | yes |
| 2 | Credit webhook didn't check the amount paid | Credits only for the exact package amount in USD | yes |
| 3 | No rate limit on checkout/portal | 20 per account per day | yes |
| 4 | Sign-out didn't revoke the server session | `/v1/auth/logout`; app calls it | yes |
| 5 | Missing pepper would weaken code hashing | Sign-in fails closed without a ≥16-char pepper | yes |
| 6 | Fully refunded subscription kept Unlimited | Ends Unlimited immediately | yes |
| 7 | "Active" with no period end = unlimited forever | Requires a paid period | yes |
| 8 | Expired sessions/codes never purged | Cron purge | — |

Re-verified: webhook signature/replay, concurrent deductions (atomic `INSERT … WHERE balance ≥ cost`), idempotent commits, cross-account isolation, trial reset by new email, reinstall, offline grace, no content in billing requests (e2e spy test), secrets only via `wrangler secret`, live keys refused. **D1 permissions:** the database is reachable only through the Worker binding; no public access exists by design. **Residual risks:** anyone can modify the GPL app to skip metering (see §6); new email + fresh installation gets a new trial; 90-day session tokens are stored in the app's data folder (mode 600).

## 5. Credit-consumption proposal (not implemented; needs approval)
Meeting/interview accounting is unchanged (1 credit = 60 minutes, 30-minute blocks). For **Ask anything, Documents, Screen**, local token counts exist on the computer (`GenerationStats`) but are never sent. Two transparent options:

| Option | Rule | Price per answer at the 15-credit rate ($5.90/credit) | Notes |
| --- | --- | --- | --- |
| **A (recommended)** | 1 credit = **60 answers** (a "minute" of credit per completed answer; screen analysis = 2) | ≈ $0.10 | Simple, predictable, sends no token data |
| B | 1 minute of credit per **1,000 output tokens**, minimum 1 | similar for typical answers | Requires sending token counts (numbers only) and is harder to explain |

Recommendation: A, or keep these three Unlimited-only until demand is clear. **Credits stay non-expiring** (simplest legally; still confirm with counsel regarding provincial prepaid rules).

## 6. GPL-3.0 assessment
* Charging for VEENA, for downloads, support or services is **compatible** with GPL-3.0.
* **Local restrictions are not enforceable:** every recipient may modify and redistribute the app (GPL §2, §10), including removing trial/plan checks, and you may not add terms forbidding that (§7, §10). The Terms draft therefore says the software licence is separate from the Service.
* **Enforceable:** anything the **server** provides (accounts, ledgers, checkout, future cloud features or sync, support).
* Obligations when distributing builds: provide corresponding source (the public repo satisfies this), keep licence notices, no added restrictions. All bundled models are Apache-2.0 and Ollama is MIT: commercial use is permitted.
* No licence files were changed.

## 7. Draft legal policies
`docs/legal/DRAFT_POLICIES.md`: Terms of Service, privacy addendum, refund policy, subscription/cancellation terms, prepaid credit terms, fair-use policy. **Drafts for lawyer review; not published.** GST/HST: registration is required once taxable sales exceed **CA$30,000 over four consecutive calendar quarters** (CRA); voluntary registration is allowed earlier. Stripe Tax (0.5% no-code or CA$0.50/transaction via API) stays **off** until you decide.

## 8. Cloudflare deployment readiness
* Free-plan limits: Workers 100,000 requests/day, 10 ms CPU; D1 100,000 writes and 5 M reads/day, 500 MB/database; requests fail rather than bill over the limits. Billing uses 1 cron (every 30 min), Insights 1 (daily): 2 of 5.
* Prepared: `cloud/billing/wrangler.example.toml`, `cloud/insights/wrangler.example.toml`, `migrations/0001_initial.sql` for both, `cloud/deploy.sh` (plan / migrate / deploy / backup / rollback; refuses without explicit approval words; refuses `ALLOW_LIVE`). **Not run**: the automated safety check blocked even its guard path, consistent with "no deployment without approval".
* Backup and recovery: `wrangler d1 export` before every deploy, plus **D1 Time Travel** point-in-time restore (7 days on the Free plan): `wrangler d1 time-travel restore <db> --timestamp=<unix>`. Rollback: `wrangler rollback`.
* Monitoring: Workers observability enabled in config; the Worker returns generic errors and never logs request bodies.
* Custom domain: **not required** for the Workers (`workers.dev`); **required for email sending** (domain authentication).

## 9. Operating-cost estimate
| Item | Cost |
| --- | --- |
| Cloudflare Workers + D1, GitHub Pages | $0 within free limits |
| Stripe account, Checkout, portal | $0 fixed |
| Per sale | 2.9% + CA$0.30 (domestic card); +0.8% international; +2% if converted to CAD |
| Subscriptions | +0.7% (Stripe Billing) |
| Email (Resend free) | $0 up to 3,000/month, 100/day |
| Domain for email | ≈ US$10–15/year (only new recurring cost) |
| Code signing (separate, recommended before a wide launch) | Apple Developer Program yearly fee; Windows certificate yearly fee |
Example: a $74.95 monthly subscription on a Canadian card costs about 2.9% + CA$0.30 + 0.7% ≈ US$2.9 in fees.

## 10. Release audit (0.1.0 draft)
| Check | Result | Evidence |
| --- | --- | --- |
| Draft exists, not published | Yes | `veena-ai-v0.1.0`, draft, by github-actions from CI run 42909272329 (commit `4dedcb4`) |
| Installer sizes | Windows 569,794,674 B (zip), macOS 626,491,321 B, Linux 824,839,399 B | run #32 artifacts |
| Integrity chain | Draft files = artifacts uploaded by the tested jobs (digests identical in the release job log); Windows installer SHA-256 `68902f2d…dc78` in both the tested job and the release notes | job logs |
| Install, launch, first run without Ollama, uninstall | **Pass** on Windows, macOS 15 (Apple Silicon), Ubuntu | run #32 steps |
| First-run AI (on Windows) | runtime 0.40.11 downloaded, SHA-256 verified, health check answer, chat, cited document answer, speech-to-text RTF 0.08 | Windows job log |
| Signing | Windows **NotSigned** (SmartScreen warning); macOS ad-hoc, not notarized; Linux n/a | signature step |
| Real-model tests on this machine | 7/7 pass (Qwen 2.5 1.5B, Qwen3-VL 2B, Whisper, MiniLM) | §11 |
| Draft text accuracy | Accurate for 0.1.0 (free, no account): keep it; RC wording drafted separately | `packaging/RELEASE_NOTES_MONETIZED_RC.md` |
Not done: downloading the draft's own files (drafts are private to this session's API access), and manual testing on a physical Mac/PC.

## 11. Tests run (exact commands and results)
| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -m "not ollama and not asr and not embeddings" -q` | 162 passed, 7 deselected |
| `.venv/bin/python -m pytest -m "ollama or asr or embeddings" -q` (Ollama running) | 7 passed (first run: 1 failed on Whisper spelling "Hashmab", 3 skipped while Ollama was stopped; test aligned to its purpose, see commit `5ea4b2e`) |
| `ruff check backend tests packaging`; `ruff format --check backend tests` | clean |
| `node --test cloud/billing/test/billing.test.mjs` | 19/19 |
| `node --test cloud/insights/test/pipeline.test.mjs` | 9/9 |
| `pytest tests/test_billing_e2e.py` (app ↔ real Worker) | 8/8 |
| `npm run typecheck`, `npm run lint`, `npm test` (desktop) | pass, pass, 18/18 |
| `site/build.sh` + `site/tools/site_check.mjs` | pass: 5 pages × phone/tablet/desktop, axe, no third-party requests, pricing interactions, free-wording gate |
| Mutation checks | replay protection, balance check and charge-on-failure removal each detected |

## 12. Remaining blockers (need you)
1. Stripe sandbox key (or deploy the Worker yourself) → run §2's real tests.
2. Email provider + a custom domain for sending.
3. Lawyer review and approval of `docs/legal/DRAFT_POLICIES.md`; a support email address.
4. GST/HST decision; Stripe Tax stays off.
5. Credit rate decision for Ask anything / Documents / Screen (§5).
6. Approval to deploy the Billing and Insights Workers.
7. Code signing (strongly recommended before charging money: unsigned installers trigger OS warnings).

## 13. Launch checklist (monetized RC)
1. ☐ Approve §12 items 2–5; create the Resend account and verify the domain.
2. ☐ `cd veena-ai/cloud/billing && cp wrangler.example.toml wrangler.toml`; `wrangler d1 create veena-billing`; fill `database_id`.
3. ☐ `wrangler secret put STRIPE_SECRET_KEY` (sandbox), `STRIPE_WEBHOOK_SECRET`, `CODE_PEPPER`, `RESEND_API_KEY`; set `EMAIL_PROVIDER="resend"`, `EMAIL_FROM`.
4. ☐ `../deploy.sh plan billing`, then `../deploy.sh migrate billing I-APPROVE-MIGRATE`, `../deploy.sh deploy billing I-APPROVE-DEPLOY`.
5. ☐ Stripe sandbox webhook endpoint + portal enabled; run every row of §2 with test cards; record results.
6. ☐ Set `BILLING_URL` (`apps/desktop/electron/backend.ts`) and bump the version to 0.2.0-rc.1; CI builds a **new draft** (the 0.1.0 draft is untouched).
7. ☐ Manual acceptance on a real Windows PC and Mac: trial counts, purchase, cancellation, offline.
8. ☐ Publish policies; set `plansLive: true` and `billingUrl` in `site/config.js`; apply the wording table in the RC notes; redeploy the site.
9. ☐ Only then: live keys (`sk_live_`), `ALLOW_LIVE=yes`, live webhook, one real low-value purchase and refund.
