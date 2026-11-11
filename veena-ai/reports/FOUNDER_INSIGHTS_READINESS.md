# VEENA Insights (founder dashboard + opt-in statistics) — readiness

Date: 2026-11-11 · Branch `claude/amazing-babbage-qia83y` · **Nothing deployed. No Cloudflare resources created. No billing changed.**

## Verdict
Built and tested end to end with **synthetic, labelled data**. Ready for the owner to deploy on the Cloudflare Workers Free plan after approval (steps below). Until then the app and website send nothing: the app's `INSIGHTS_URL` and the site's `insightsUrl` are empty, so the Settings toggle reads "Not available in this version".

## Audit of what existed (reused, not duplicated)
| Existing piece | Use |
| --- | --- |
| `backend/analytics/metrics.py` (on-device latency/score metrics) | Unchanged; stays local, never uploaded |
| Settings store (`DEFAULT_SETTINGS`) | Holds the consent flag and the random installation id |
| Settings page `Row`/`Switch`/`Card` components | New "Anonymous usage statistics" card |
| Website `site.js` download-click hook and `config.js` switches | Feed the website counters (off until configured) |
| GitHub release `download_count` (`site/tools/release_downloads.py`) | Snapshotted daily by the Worker |
| Privacy page, About page | About text updated; privacy page to be updated in the same commit that switches anything on |

## Architecture
* **Cloudflare Worker + D1** (`cloud/insights`), no dependencies. Free-plan limits verified on Cloudflare's docs (2026-11-10): Workers 100,000 requests/day, 10 ms CPU per request, 5 cron triggers; D1 100,000 rows written and 5 million read per day, 500 MB per database, 5 GB total, 50 queries per invocation. **On the free plan, exceeding a limit makes requests fail; it does not charge.**
* One cron trigger a day: retention purge + GitHub download snapshot.
* Capacity estimate: an opted-in installation writes about 2–8 rows a day (active + a few features), so ~10,000 active opted-in installs stay under the 100,000 writes/day limit; website counters are 1 upsert per page view.

## Privacy guarantees (enforced in code and tests)
* App: **off by default**; nothing is even recorded until the user opts in; consent can't be changed through the generic settings API.
* Only allow-listed fields: random install UUID, OS, app version, UTC day, event (first_launch, ai_first_success, active, feature, error), feature name (6 values), error code (8 values). The server **rejects** any other field (tested with a prompt, an email field, a free-text error with a file path).
* Never collected: prompts, answers, screenshots, documents, file names, audio, transcripts, resumes, error messages, IP addresses or user agents (the Worker stores none).
* Website: cookieless counters with **no identifier**; skipped when the browser sends Global Privacy Control or Do Not Track; counts only from the site's own origin.
* The dashboard says what each number is **not**: page views are not people, downloads include repeats, installations are not people, declined installs are never counted.

## Abuse prevention
Strict schema; 8 KB body limit; ≤50 events per request; days must be within the last 7 days; per-installation limit of 300 events/hour (429 above); de-duplication of once-only and daily events; website endpoint restricted to the site origin (CORS). Limitation: anyone can still send well-formed fake events with random ids — the data is directional, not audited.

## Dashboard access
`/dashboard` page + `/api/summary` data. Data requires `Authorization: Bearer <DASHBOARD_TOKEN>` (a Worker **secret**, ≥32 characters, compared in constant time; the API refuses to work with a shorter token). The token is kept in the browser tab's session storage only. Page served with `noindex`, `frame-ancestors 'none'`, `no-referrer`, strict CSP. Optional extra layer: Cloudflare Access in front of `/dashboard` (I could not confirm from Cloudflare's docs whether its free plan covers a `workers.dev` hostname, so it is not relied on).

## Retention and deletion
* Desktop events and website counters: deleted after **395 days** (`RETENTION_DAYS`, `WEB_RETENTION_DAYS`) by the daily job; rate rows after 2 days.
* **User withdrawal**: turning the toggle off deletes the local id and queue at once and sends `POST /v1/delete`; retried until it succeeds if offline.
* **Owner deletion on request** (support): `POST /api/delete {"install_id": "..."}` with the dashboard token. The user finds their id in Settings → "Show exactly what is waiting to be sent" while the toggle is on.
* Every deletion is logged in `deletions` (date, source, row count) without keeping the deleted id.

## Tests (all passing)
| Suite | Result |
| --- | --- |
| `cloud/insights/test/pipeline.test.mjs` (real Worker code on SQLite) | 9/9: schema rejection, body limit, rate limit, dedup, withdrawal deletion, origin check, token auth incl. weak-token refusal, retention purge, full synthetic pipeline |
| `tests/test_telemetry.py` | 9/9: off by default, unavailable without server, allow-listed fields only, dedup, offline keeps queue, withdrawal deletion, consent not patchable, chat records nothing when off, opted-in chat records "chat" but none of the question |
| Backend suite | 154 passed |
| Frontend typecheck, lint, tests | pass (18 tests) |

Synthetic data: 160 installations, 90 days of website traffic, all rows `is_test = 1`; the "Real data" view was asserted to show zero.

## To go live (needs your approval)
1. `npm i -g wrangler` → `wrangler login` (free Cloudflare account; no paid plan).
2. `cd veena-ai/cloud/insights && cp wrangler.example.toml wrangler.toml`
3. `wrangler d1 create veena-insights` → paste the id into `wrangler.toml`.
4. `wrangler d1 execute veena-insights --remote --file schema.sql`
5. `wrangler secret put DASHBOARD_TOKEN` (generate: `openssl rand -base64 36`).
6. `wrangler deploy` → note the `https://veena-insights.<you>.workers.dev` URL.
7. Set it in `apps/desktop/electron/backend.ts` (`INSIGHTS_URL`) and `site/config.js` (`insightsUrl`), **update `site/privacy.html`** in the same commit, rebuild installers and redeploy the site.
