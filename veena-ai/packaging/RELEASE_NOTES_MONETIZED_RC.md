<!-- DRAFT for a SEPARATE monetized release candidate (e.g. veena-ai-v0.2.0-rc.1). Do not use for the
     existing 0.1.0 draft, whose free / no-account wording is accurate for that build (billing disabled).
     Use only once BILLING_URL is set, payments are tested in Stripe test mode end to end, and the
     owner has approved the policies in docs/legal/DRAFT_POLICIES.md. -->
## VEENA.AI 0.2.0 · Release candidate

**Your AI. Your computer. Your control.** A private AI companion for conversations, meetings, interview practice, documents and your screen. The AI runs on your own computer; your conversations, documents, screens and recordings never leave it.

### Try it free
Sign in with your email and get **three successful uses of each feature**: Ask anything, Documents, Screen, Meeting sessions and Interview practice. No credit card. Failed or cancelled tasks don't count.

### Plans (USD, plus applicable taxes)
* **Unlimited:** $74.95 a month or $299.95 a year. Unlimited use of every feature above; cancel anytime in the customer portal.
* **Credits** for meeting and interview sessions: 1 credit $19.00 · 3 credits $29.50 · 8 credits $59.00 · 15 credits $88.50. 1 credit = 60 minutes, used in 30-minute blocks, charged only after a session completes. Credits don't expire.

Payments are processed by Stripe; VEENA never sees your card. Only your email, a random installation id, which feature was used and minutes are sent to VEENA's servers, never your content.

### Open source
VEENA remains free software under the GNU GPL-3.0-or-later. You may study, change and share the source. Plans pay for the account and billing service and support the project's development.

(Download table, unsigned-installer instructions, requirements and "How it was tested" carry over from the 0.1.0 notes, with this build's checksums.)

---

### Replacement wording for other places (apply only when this release ships)
| Where | Now (accurate for 0.1.0) | Replace with |
| --- | --- | --- |
| README line 8 | "No account, no subscription, no API key." | "Try every feature free, then choose Unlimited or credits. No API key; your content stays on your computer." |
| README "Free to use" card | "No subscription or account." | "**Try free:** three uses of every feature, no card. Plans from $19." |
| README "What it costs" | "No money is required." | "Three free uses of each feature; then Unlimited ($74.95/month, $299.95/year) or credits. Resources: …" |
| Website | `plansLive: false` | set `plansLive: true` in `site/config.js` (switches all wording and shows Pricing) |
| `site/privacy.html` | "no accounts" | add the paid-plans addendum from `docs/legal/DRAFT_POLICIES.md` §2 |
| App Welcome / About / Setup | "$0 a month, no account" | "Three free uses of each feature, then a plan. Your content never leaves this computer." |
| Customer installation guide | "no account … no payment" | "No payment to install; sign in with email to start your free uses." |
| Medium articles | — | **Unchanged** (published articles are not edited); add a dated note in a new post if needed |
