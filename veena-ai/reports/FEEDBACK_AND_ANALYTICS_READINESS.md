# Feedback, community and analytics: readiness

Date: 2026-11-10 · Branch: `claude/amazing-babbage-qia83y` · Nothing deployed, merged or published.

## Verdict

**Built and tested; waiting on four owner actions.** The feedback page, community links and analytics hooks are
in the website code, and their safe defaults are tested in a browser. Every external service is **off** until
the owner supplies a value created in their own account. The build refuses values it cannot verify. Nothing
was invented: there is no form URL, no Discussions link, no analytics token and no feedback or analytics data.

| Item | State | Evidence |
| --- | --- | --- |
| "Your perspective matters." section (home) | **Done** | `site/index.html`; quiet "Share feedback" link; "Join the conversation" appears only when Discussions is verified |
| Feedback page (`feedback.html`) | **Done, form pending** | Experience · Type · Message · optional Email · privacy notice. Disabled with "being set up" until a form is configured (browser-tested) |
| Google Forms + Sheets hand-off | **Built and tested with an example config; needs the owner's form** | Documented pre-filled-link feature; browser test checks every answer reaches the right `entry.` field, special characters intact, empty email omitted |
| Email notification on new feedback | **Documented**, owner turns it on in Google Forms | `docs/FEEDBACK_AND_COMMUNITY_SETUP.md` §1.3; no address or credential in the website |
| GitHub Discussions | **Enabled** by the owner (API: `has_discussions: true`) | Categories and pinned welcome post still to create; three form templates ready |
| Footer "Community" link | **On** (verified) | Build fails if `discussionsEnabled` is true while the API says false |
| Download-click instrumentation | **Hook only; sends nothing** | Page-local `veena:download` event `{os, version, campaign}`; no cookies, storage or fingerprinting |
| Release download counts | **Done** | `site/tools/release_downloads.py`; today: "No published VEENA release yet" |
| Cloudflare Web Analytics | **Prepared, off** | Beacon loaded only for a valid 32-hex token; free tier and limits checked against Cloudflare's docs |
| Secrets in website JavaScript | **None; guarded** | `check_config.py` fails the build on anything that looks like a password, API key or token |
| README "Feedback & Community" | **Done** | Honest about what is live |

## What the owner needs to do

1. **Create the Google Form** (about 5 minutes) and link it to a Sheet. Turn on email notifications. Copy
   the form link and `entry.` IDs into `site/config.js`. See `docs/FEEDBACK_AND_COMMUNITY_SETUP.md` §1. Then send
   one real test response and check that it arrives in the Sheet and by email.
2. **Enable Issues and Discussions** (Settings → General → Features). **Issues is off today.** The release
   notes, `CONTRIBUTING.md` and the support guide all send people to GitHub Issues, so those links are dead
   until it is on.
3. **Create the Discussion categories and pin the welcome post** (§2.2–2.3). Then set
   `discussionsEnabled: true`.
4. *(Optional)* **Cloudflare Web Analytics.** Add the site, copy the token into `cloudflareToken`, and update
   the privacy page in the same commit (§3).
5. Approve the website deploy (Actions → VEENA.AI website → Run workflow → deploy). It is not deployed.

## Why it is built this way

* **No undocumented Google endpoints.** Posting straight to a form's `formResponse` URL is not a documented
  API. The documented route is the pre-filled link (Google Forms help, "Pre-fill form" → "Get link"). So the
  visitor confirms on Google's own page, which also means Google, not VEENA's site, handles the submission.
* **No secrets on a static site.** Anything in GitHub Pages JavaScript is public. Email notification is a
  Google Forms setting, so no SMTP or API key is needed anywhere.
* **Cloudflare can't count download clicks.** Cloudflare documents that Web Analytics has no custom events
  ("Not yet") and does not log query strings. It is useful for visitors, top pages and referrers only. Download
  totals come from GitHub's per-file `download_count`.

## Four different numbers

| Metric | Source | Meaning | Not |
| --- | --- | --- | --- |
| Visitors / page views | Cloudflare Web Analytics (once on) | Browsers that loaded pages | People, downloads |
| Download clicks | Not collected today (hook ready) | Clicks on a download button | Completed downloads |
| Asset downloads | GitHub `download_count` | Completed file downloads per installer | People, installs |
| Installs | Not measured | | VEENA sends no install ping, by design |

## Privacy review

* No cookies, `localStorage`, fingerprinting or third-party script by default. Verified: the built pages load
  only same-origin files plus `api.github.com` (release list).
* The campaign label is read from the page's own URL (`utm_campaign` or `ref`), limited to 40 characters of
  `[a-z0-9_-]`, and only used in the local event and the optional form "Source" field.
* The feedback page warns against including passwords or private documents. Email is optional, and the
  privacy page has a new "Feedback" section (who processes it, what it is used for, deletion on request).
* The privacy page no longer links to the disabled Issues tracker.

## Tests run

| Check | Result |
| --- | --- |
| `site/tools/check_config.py` on the shipped config | `config OK: feedback form: pending (no form yet); community link: hidden (Discussions not enabled); visitor analytics: off` |
| Same, with a fake token, a `smtpPassword`, bad entry IDs and `discussionsEnabled: true` | Fails with 6 specific problems (exit 1), including "discussionsEnabled is true but Discussions is not enabled on the repository" |
| Same, with a well-formed example form | Passes |
| Browser: shipped feedback page | Form disabled, "being set up" notice visible, no community link |
| Browser: example form config | Empty submit blocked with a message; a valid submit opens `docs.google.com/.../viewform?usp=pp_url&entry.1=Good&entry.2=Feature+request&entry.3=…`; confirmation shown |
| Browser: every page on phone, tablet and desktop | See "Website QA" below |
| `release_downloads.py` | "No published VEENA release yet: there are no download counts to report." |

## Website QA

Run 2026-11-10 on the built site (`site/build.sh`, then `site/tools/site_check.mjs`), Chromium via Playwright:

| Check | Result |
| --- | --- |
| Pages | index, features, feedback, privacy |
| Viewports | 390×844 (phone), 820×1180 (tablet), 1440×900 (desktop) |
| Horizontal scrolling | None (two defects found and fixed first: laptop base 403 px on a 390 px phone; low-contrast benefit numerals) |
| axe-core accessibility, serious or critical | None, on phone and desktop |
| Third-party requests | None besides `api.github.com` (release list) |
| Page errors | None |
| Download panel | "Public beta coming soon" (no published release, so no download link is offered) |
| Feedback flow | Pending state correct; example config hands answers to Google Forms correctly |
| Community link | Shown; Discussions verified enabled through the GitHub API |
| Demo clips privacy (`site/tools/check_media_privacy.py`) | 15 clips, every half second read by OCR: no Home screen (which can show a private local photo) |
| Site size | 45 files, 18.4 MB |

Lighthouse scores have not been measured yet, so none are claimed.
