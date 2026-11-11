# Pricing and billing — readiness report

Date: 2026-11-11 · Branch `claude/amazing-babbage-qia83y`
**Test mode only. Nothing deployed. No Stripe or Cloudflare resources created. No live keys used or stored. No billing settings changed.**

## Summary
Built end to end and tested locally against a **Stripe simulator** (the owner declined to provide a test key; the integration needs only configuration to use real Stripe test mode):

| Deliverable | State | Evidence |
| --- | --- | --- |
| Pricing page (Free Trial + Unlimited / Credits / Custom) | Done, not deployed | `site/pricing.html`; browser QA on phone/tablet/desktop, axe clean, keyboard tabs, totals |
| Billing backend (Worker + D1) | Done, not deployed | `cloud/billing`; 11 tests |
| Stripe Checkout, portal, webhooks | Done against simulator | signature, replay, stale/tampered rejection tested |
| Free trial (3 successful uses per feature) | Done | server ledger, per account **and** per installation |
| Credits ledger, subscriptions, refunds, failed payments | Done | tested |
| App integration (trial counter, metering) | Done, **disabled** until `BILLING_URL` is set | 8 end-to-end tests vs the real Worker |
| Website wording for the paid model | Done in repo, **not deployed** | home page "Try free", pricing link, nav |

## Audit of what existed (reused)
Opt-in statistics design (allow-list, never content) was reused for billing metadata; settings/consent patterns; the site's `config.js` switch pattern (`billingUrl` null until approved); Settings `Card`/`Row` components; the Worker + D1 + SQLite-shim test approach from `cloud/insights`.

## Prices (USD, exactly as approved)
| Package | Price | Allowance |
| --- | ---: | --- |
| Free trial | $0 | 3 successful uses each: Ask anything, Documents, Screen, Meeting sessions, Interview practice |
| 1 Credit | $19.00 | 60 minutes |
| 3 Credits | $29.50 | 180 minutes |
| 8 Credits | $59.00 | 480 minutes |
| 15 Credits | $88.50 | 900 minutes |
| Unlimited monthly | $74.95 / month | unlimited use of the five verified features |
| Unlimited annual | $299.95 / year | same (about $25.00/month, 67% less than 12 × monthly) |
| Custom | not priced | "Coming soon" + contact link; nothing activated |

**Trial feature list (audited):** the five above are verified, user-facing AI features. **"AI Agent tasks" are not offered as a separate feature**: VEENA's agents route every answer internally and the Agents page *measures* answers; there is no standalone agent task to sell, so advertising one would be inaccurate. Speech-to-text and question detection are parts of Ask anything / Meetings, not separately metered.

## How metering works (and its honest limits)
1. Before an AI operation the app **authorises** it with the server (Unlimited → free use → credits).
2. Only after the operation **completes** is it **committed**. Failed, cancelled or interrupted operations are **released**; abandoned reservations expire after 3 hours uncharged.
3. Operation ids make retries idempotent; the credit ledger's unique `ref` makes double charging impossible; an atomic `INSERT … WHERE balance ≥ cost` prevents overspend under concurrency (verified by a test and a mutation check).
4. **Meeting and interview** sessions: one 30-minute block (0.5 credit) covers every answer in that session for 30 minutes.
5. **Ask anything / Documents / Screen after the trial require Unlimited.** Credits do not apply to them yet, because the per-answer conversion is not approved. Proposal for your decision: *1 credit = 60 answers* (1 minute of credit per completed answer). Local generation stats (`GenerationStats`: prompt and output tokens) are measured but **not** sent; a token-based rate would need them sent as numbers only.
6. **Sent to the billing server:** random installation id, feature name, operation id, minutes. **Never** prompts, answers, transcripts, screenshots, documents or resumes (tested: a "secret salary" prompt does not appear in any billing request).
7. **Offline:** 3 uncharged uses per feature, then the app asks to reconnect; queued commits are replayed later.
8. **Not tamper-proof.** VEENA is GPL-3.0 software running on the user's computer; anyone can modify it to skip these checks. The server can only enforce what it serves (accounts, balances, checkout).

## Licence audit
VEENA is **GPL-3.0-or-later**. Selling it and charging for access is allowed. But GPL-3.0 guarantees every recipient the right to modify and redistribute the source, **including removing the trial and plan checks**, and you may not add restrictions that forbid this. Practical consequences:
* paid limits are a convenience and honesty mechanism, not DRM;
* anything you want to be truly paid-only must be delivered by the **server** (e.g. future cloud features, sync, support);
* the licence of bundled models (all Apache-2.0) and of Ollama (MIT) permits commercial use.

## Free-trial abuse prevention (no fingerprinting)
* Verified email (6-digit code, hashed, single-use, 10-minute expiry, 5 attempts).
* Trial counted per **account** and per **installation** (random UUID; no MAC, serial or hardware data): a new email on a known installation does not reset; reinstalling with the same account does not reset.
* A third account on one installation gets no trial (appealable via `POST /v1/appeal`; owner reviews the `appeals` table).
* Rate limits: 5 code requests per email and 10 per installation per day.
* **Not guaranteed:** a new email *and* a fresh installation (or deleting the app's data folder) gets a new trial. Preventing that would need invasive fingerprinting, which is deliberately not used.

## Stripe
* Hosted Checkout with inline USD prices (no pre-created products needed), the customer portal for cancellation/payment-method changes, and webhooks: `checkout.session.completed`, `invoice.paid` (activation and renewal), `invoice.payment_failed` (past_due; access continues while Stripe retries), `customer.subscription.updated/deleted` (cancellation), `charge.refunded` (removes the refunded share of credit minutes).
* Webhook signature verified (HMAC-SHA256, 5-minute tolerance), each event id processed once.
* **A success redirect never grants anything**; the page polls the server for the real balance.
* The Worker refuses any non-`sk_test_` key unless `ALLOW_LIVE=yes` is set deliberately.
* No card data is ever stored or seen by VEENA.

## Cost audit (official pricing, checked 2026-11-11)
| # | Item | Cost |
| --- | --- | --- |
| 1 | Stripe account | $0, no setup or monthly fees |
| 2 | Stripe Checkout | Included (optional custom domain US$10/month: **not used**) |
| 3 | Domestic Canadian cards | 2.9% + CA$0.30 per successful payment |
| 4 | International cards | +0.8% |
| 5 | Currency conversion | +2% (prices are in USD, so converting USD payouts to a CAD bank account may incur it; a USD bank account avoids it) |
| 6 | Stripe Billing (subscriptions) | 0.7% of subscription volume, pay-as-you-go |
| 7 | Stripe Tax | Off. If enabled: 0.5% (no-code) or CA$0.50 per transaction (API), where registered |
| 8 | Refunds / disputes | No fee to refund a card (original fee not returned); CA$15 per dispute |
| 9 | Cloudflare Workers + D1 | Free plan: 100,000 requests/day; D1 100,000 writes and 5 M reads/day, 500 MB per database. Over the limit, requests fail; **no charge** |
| 10 | Email codes | **Needs an email-sending provider** (see approvals). Not chosen; no cost incurred |

Example: one $74.95 monthly subscription paid by a Canadian card ≈ 2.9% + CA$0.30 + 0.7% Billing, plus up to 2% conversion if paid out in CAD.

## Tests run (all passing)
| Suite | Result |
| --- | --- |
| `cloud/billing/test/billing.test.mjs` | 11/11: prices, sign-in limits, trial counting incl. failures/cancel/idempotent commit, multi-email abuse, reinstall, checkout test-mode only + live key refused + success redirect grants nothing, webhook signature/stale/tamper/replay, credits in 30-min blocks + concurrent overspend prevention + partial refund, subscription create/renew/failed/cancel + portal, unauthorised access, reservation expiry |
| Mutation checks | removing replay protection → test fails; removing the balance check → test fails; charging on failure → e2e test fails |
| `tests/test_billing_e2e.py` (app API ↔ real Worker) | 8/8: disabled by default, sign-in required, 3 free answers then pricing, failed answer not charged, new email doesn't reset, no content reaches billing, offline grace then blocked, meeting block charged once + credits after trial |
| Backend suite | 162 passed |
| Frontend | typecheck, lint, 18 tests pass |
| Website QA (`site/tools/site_check.mjs`) | all pages incl. pricing on 390/820/1440 px, axe, pricing interactions, no third-party requests |

## Setup (when approved)
1. Stripe **sandbox**: Developers → API keys → `sk_test_…`; Developers → Webhooks → endpoint `https://<billing-worker>/v1/stripe/webhook` with the events above → signing secret `whsec_…`; enable the customer portal (Settings → Billing → Customer portal).
2. Cloudflare: `cd veena-ai/cloud/billing`, create `wrangler.toml` like `cloud/insights/wrangler.example.toml` (D1 binding `DB`, cron `*/30 * * * *` for reservation expiry, vars `SITE_URL=https://florina787.github.io/Data-sets`), `wrangler d1 create veena-billing`, `wrangler d1 execute veena-billing --remote --file schema.sql`, `wrangler secret put STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `CODE_PEPPER`, then wire an email provider into `env.sendEmail`.
3. Set `BILLING_URL` in `apps/desktop/electron/backend.ts` and `billingUrl` in `site/config.js`; rebuild installers; redeploy the site.
4. Run a full test purchase with Stripe test card `4242 4242 4242 4242`, a decline with `4000 0000 0000 0002`, a refund and a cancellation from the portal.

## Needs your approval
1. **Email provider** for sign-in codes (third-party service; free tiers exist but terms and limits must be checked before choosing).
2. **Deploying** the billing Worker and D1 (free plan) and the updated website.
3. **Terms of service, refund policy and privacy-policy update** for paid plans (the pricing page currently says "contact us" for refunds; a written policy is needed before taking money).
4. **Sales tax:** whether and where you are registered (GST/HST in Canada, others); Stripe Tax stays off until you decide.
5. **Credit conversion for Ask anything / Documents / Screen** (proposal: 1 credit = 60 completed answers), or keep them Unlimited-only.
6. **"Credits don't expire"** is stated on the pricing page and is how the ledger works. Confirm it, or choose an expiry.
7. **Going live:** a live key (`sk_live_…`) and `ALLOW_LIVE=yes`, only after test purchases succeed and items 1–4 are done.
8. **Public wording:** the README and Medium article still say "free / no subscription"; the website copy is updated in the repo but not deployed.
