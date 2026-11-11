# Cloudflare sandbox deployment plan — VEENA Billing (test only)

Status: **PLAN — awaiting the owner's approval. Nothing has been created or deployed.**
Date: 2026-11-11. Scope: Stripe **sandbox** only; no live keys, no paid services, no domain purchase, no release publication.

## 1. Audit of what exists (reused as is)
| Component | State | Evidence |
| --- | --- | --- |
| Billing Worker `cloud/billing/src/worker.js` | Complete; no dependencies, no build step | 19/19 Worker tests; 8 security fixes |
| D1 schema `cloud/billing/migrations/0001_initial.sql` | Complete (11 tables) | used by all tests |
| Stripe integration (Checkout, portal, webhooks, refunds, renewals) | Verified against the **real Stripe sandbox**: 21/21 | `cloud/billing/test/sandbox-results.json` |
| Email sign-in (provider-independent, Resend adapter) | Code complete; **no provider configured** | Worker tests; fails closed |
| RC 0.2.0-rc.1 (app + CI enforcement test) | Built in CI; billing URL is a placeholder until this deployment | CI run 43049936256 (re-run in progress) |
| Insights Worker | **Not part of this plan** (separate approval) | — |

## 2. Exact resources (1 Worker, 1 database)
| Resource | Name | Notes |
| --- | --- | --- |
| Worker | **`veena-billing-sandbox`** | the only Worker |
| D1 database | **`veena-billing-sandbox`** | the only database; binding `DB` |
| Cron trigger | `*/30 * * * *` | 1 of 5 free cron triggers: releases abandoned reservations, purges expired sessions/codes |
| Logs | Workers Logs, `head_sampling_rate = 0.1` | the Worker logs no request bodies, tokens or emails |
| **Billing API URL** | `https://veena-billing-sandbox.<your-subdomain>.workers.dev` | `<your-subdomain>` is your account's free workers.dev subdomain, chosen when you first enable Workers |
| Stripe webhook endpoint (sandbox) | `<billing API URL>/v1/stripe/webhook` | 8 events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `charge.refunded` |

Not created: custom domains, routes, KV, R2, Queues, Durable Objects, a production Worker or database.

## 3. Configuration
**Plain variables** (visible in the Cloudflare dashboard; not secret):
`SITE_URL=https://florina787.github.io/Data-sets`, `EMAIL_PROVIDER=""` (until a provider is approved), `EMAIL_FROM=""`. `ALLOW_LIVE` is **never set**; the Worker refuses any key not starting `sk_test_`.

**Secrets** (stored with Cloudflare's encrypted Worker secrets; never in code, logs, chat or reports):
| Secret | Value | Who sets it |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | a **new, never-shared** sandbox key `sk_test_…` (see §6) | you, via the secure form or the Cloudflare dashboard |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` from the sandbox webhook endpoint | created when the endpoint is added; set without display |
| `CODE_PEPPER` | 48 random bytes, generated during deployment | generated and set without printing |
| `RESEND_API_KEY` | only after an email provider is approved | you |

## 4. Free-tier limits and expected cost (verified on Cloudflare docs, 2026-11-10/11)
| Limit (Workers Free) | Value | This deployment's use (test traffic) |
| --- | --- | --- |
| Requests | 100,000/day | < 1,000/day |
| CPU per request | 10 ms | ≈ 1–3 ms (no heavy work) |
| Cron triggers | 5 per account | 1 |
| D1 rows written / read | 100,000 / 5,000,000 per day | < 5,000 / < 50,000 |
| D1 size | 500 MB per database, 5 GB per account, 10 databases | < 1 MB |
| D1 queries per invocation | 50 | ≤ 12 |
| Workers Logs | 200,000 events/day, 3-day retention | < 1,000 |
| **Expected monthly cost** | **$0** | |
On the Free plan, exceeding a limit makes requests fail; **it does not bill**. Note: Cloudflare says Workers Logs moves to "Cloudflare Observability pricing" on **2026-12-01**; on a Free account there is no payment method to charge, but re-check before then (or set `observability.enabled = false`).

## 5. How deployment would be done (after approval)
This session has **no Cloudflare access**. Two options:
* **A (recommended):** you create a Cloudflare API token limited to **Account → Workers Scripts: Edit, D1: Edit** (no zone permissions, no billing), and enter it in the secure credential form for `api.cloudflare.com`. I then use Cloudflare's REST API directly (no extra tools to download): create the D1 database, apply the migration, upload the Worker module, set the cron and the secrets, and verify. Afterwards you can revoke the token.
* **B:** you run the commands yourself: `cd veena-ai/cloud/billing && cp wrangler.example.toml wrangler.toml` (set `name` and `database_name` to `veena-billing-sandbox`), `npx wrangler login`, `npx wrangler d1 create veena-billing-sandbox`, paste the id, `npx wrangler d1 migrations apply veena-billing-sandbox --remote`, `npx wrangler secret put STRIPE_SECRET_KEY` (and the others), `npx wrangler deploy`.

## 6. Stripe sandbox security (status: **NOT READY**)
* Checked 2026-11-11: **the original key still authenticates (HTTP 200)**, so it has **not** been revoked, and **the replacement key also appeared in chat**. Both must be treated as exposed.
* Required before deployment: in the Stripe **sandbox** → Developers → API keys → expire **all** existing secret keys (choose "expire now"), create one new secret key, and give it **only** through the secure credential form or the Cloudflare dashboard's secret field. Never paste it in chat.
* After you confirm, I will re-test that both old keys return HTTP 401, without printing them.
* The copy of the second key in this session's private scratch folder will be deleted when the current RC test finishes. It was never committed or logged.

## 7. Email verification (status: **BLOCKER**)
* Resend's free plan: 3,000 emails/month, 100/day, 3 domains. It **requires a verified domain you own**; `github.io` can't be used, and Resend's docs say a shared or public domain isn't allowed.
* Options: (1) buy a domain (≈ US$10–15/year, **needs your approval**) and verify a subdomain such as `mail.yourdomain`; (2) leave email off: the Worker then refuses sign-in (`503 sign-in is not configured`), so the sandbox can't be used by real people. Authentication is not bypassed.
* For **automated tests only**, the test harness reads codes from its own in-memory mailer (`cloud/billing/test`), never on the deployed Worker.

## 8. Migrations, backup, rollback, recovery
* Migrations: `migrations/0001_initial.sql` is applied once; future changes are new numbered files applied with D1 migrations (never edited in place).
* Backup: export before every deploy (`wrangler d1 export veena-billing-sandbox --remote --output backups/<time>.sql`) plus **D1 Time Travel** (free plan: **7 days** of point-in-time history).
* Restore: `wrangler d1 time-travel restore veena-billing-sandbox --timestamp=<unix time>` (returns a bookmark to undo the restore).
* Rollback the code: `wrangler rollback` (previous Worker version).
* Kill switch: delete the Stripe webhook endpoint and the Worker; the RC app then fails closed (no unlimited use).
* Full teardown: `wrangler delete` + `wrangler d1 delete veena-billing-sandbox`; nothing else exists.

## 9. Security and privacy implications
* The Worker becomes **publicly reachable** at its workers.dev URL. Protections in place: webhook signatures, signed-in sessions (hashed tokens), per-account isolation, rate limits on sign-in codes and checkout, strict input validation, sandbox-only keys.
* Data stored: email address, random installation id, feature name, operation ids, minutes, plan and payment status. **Never** prompts, documents, screenshots, transcripts or card data.
* This is a test environment: only test cards work, and no real money moves. It is fully separate from any future production Worker or database.

## 10. What I need from you to proceed
1. **Approve this plan** (1 Worker + 1 D1 database on the Free plan, at $0).
2. **Expire every exposed Stripe sandbox key** and create a fresh one (enter it only through the secure form or the Cloudflare dashboard).
3. Choose deployment option **A** (scoped API token via the secure form) or **B** (you run the commands).
4. Decide on email: approve buying a domain for Resend, or accept that sign-in stays disabled (blocks real-user testing; automated tests still run).
