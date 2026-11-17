# FEMORA Muse: architecture and implementation plan

*Supersedes the leadership-demo scope in [AUDIT.md](AUDIT.md) (kept for history). Updated 16 Nov 2026.*

## Status after Muse Milestone 1

| Area | State | Notes |
|---|---|---|
| Honest data model | ✅ | No seeded health data, generated events, deals, sample lab reports or simulated bookings. Bea (37, US, city unset) and Nancy (Nashville) are example configurations with no assumed health details. |
| Muse conversation | ✅ | Offline rule-based library + safety rules; **llama.cpp adapter** (OpenAI-compatible) with connection test; falls back offline on failure. No artificial streaming delay. |
| Proactive Muse | ✅ | `modules/muse/proactive.ts`: suggestions built only from her records (appointments, saved questions, due doses, city, interests). |
| Notification engine | ✅ | `modules/notifications/engine.ts`: 7 categories, immediate/digest, quiet hours, daily limits, priorities, snooze, dismiss, mute, relevance feedback, private medication text, browser alerts with permission. |
| Health planner | ✅ | Medication & supplements: dose, frequency, times, start/end, prescriber, refill, notes, taken/skipped/snoozed, adherence, export. Check-ups: next/last date, **no default intervals**, saved questions. |
| MedScan | ✅ | User-entered results vs **her report's** range; rule-based symptom triage. OCR not connected. |
| Discover | ✅ | Verified official resources (HTTP-checked 16 Nov 2026), verified-feed adapter (`public/data/opportunities.json`, empty until partners exist), user-saved events, spiritual preferences incl. "none", commercial offers opt-in. |
| Food | ✅ | Unchanged module; starts empty; photo-assisted logging (she picks the dish). |
| Connections | ✅ | Contacts (picker/manual), WhatsApp/email/SMS/share-sheet links, .ics. OAuth sync planned. |
| Luxury design system | ✅ step 1 | Tokens: Onyx & Champagne (default), Emerald & Ivory, Midnight & Pearl × light/dark; editorial type (Cormorant Garamond + Outfit); route code-splitting. |
| Menopause journey | ✅ | Cycle calendar, period log (flow, pain, notes), cycle-length chart (21–35 day band), weekly symptom chart with date range, ovulation observations with contraception warning, STRAW+10 educational pattern notes with confounders that switch staging off, doctor-ready summary, Muse answers cycle questions from records only. |
| Forecasting (real data) | ✅ | NHANES 2013–2018 (10,375 women): lifelines KM (median 51, bootstrap CI), Weibull AFT, scikit-learn classifiers vs age baseline, statsmodels generational test; personal next-period time-series forecast with backtest. See `ml/README.md`. |
| Agent evaluation | ✅ | promptfoo 12/12, runs in CI; found and fixed a crisis-detection gap. See `evals/README.md`. |
| Health dashboard | ✅ | 14 user-entered measures (weight, waist, BP, glucose, HbA1c, sleep, steps, exercise, joint/hip pain with location, brain fog, mood, skin, hair, nails); 7d–all date ranges, metric comparison, expandable insights, ACC/AHA and ADA guideline-range notes with urgent alerts, CSV export. No scores or diagnoses. Muse answers from these records. |
| Guardian | ✅ partial | Works now: one-tap emergency call (country number), SOS drafts via SMS/WhatsApp with optional one-time location (never claims delivery), trusted contacts, scheduled check-ins with in-app alerts, emergency card (print/save). Needs a server: automatic missed-check-in alerts, live location. Needs the mobile app: closed-app alerts, fall detection. |
| Global sisterhood map | ✅ | MapLibre (BSD) + OpenFreeMap/OpenStreetMap tiles, lazy-loaded; 15 organisations verified on 17 Nov 2026 (HTTP 200 + page title); country/region/city-level markers only, online resources list-only; clustering, search, category and free filters, map/list switch, detail panel, optional OpenStreetMap city search on request; list fallback without WebGL. Member circles wait for accounts and moderation. |
| Onboarding & help | ✅ | 5-step welcome (skippable, restartable), 8 spotlight tours bound to real elements, 12 searchable help articles with 4 short WebM animations recorded from the app, "Ask Muse how to" answers from the help centre and launches tours. |
| Cinematic media, Lighthouse, Healthcare/MedAccess | ⏳ | Needs licensed imagery; Lighthouse run pending; MedAccess repo not accessible. |

## 1. Architecture
UI (`pages`, `*Page.tsx`) → domain logic (`modules/*/logic.ts`, `engine.ts`; pure, tested) → storage adapter (`lib/storage.ts`, versioned) → AI gateway (`modules/conversation/router.ts` + `ChatProvider`). Safety, scheduling, eligibility and numbers are deterministic; the LLM only writes conversation.

## 2. Existing copilot reuse
ConvoLens (React/Vite/TS stack, XSS-safe Markdown, CI shape, Gemini free-tier pattern); enterprise-agentic-ai and LexGuard (supervisor routing, guardrail-before-model, honest status). MedAccess AI isn't accessible from this session. Attach it to reuse provider discovery in the Healthcare phase.

## 3. llama.cpp integration
Web: `llamaProvider.ts` calls a user-run `llama-server` (`/v1/models`, `/v1/chat/completions`) with persona + deterministic context. Static hosting can't run llama.cpp. Next: SSE streaming, tool calls for reminders/food facts, context limits. Mobile: llama.cpp via native bindings with GGUF models downloaded from Hugging Face.

## 4. Model selection & evaluation
Candidates to benchmark (not chosen): Qwen2.5 1.5B/3B, Llama 3.2 1B/3B, Gemma 3 1B/4B, Phi-4-mini, SmolLM2 1.7B (GGUF Q4/Q5). Eval set: `training/companion-dialogues.jsonl` + automated companion checks (`companion.test.ts`), extended with misinformation, medication-safety, prompt-injection, privacy-leakage and multilingual cases. Licences to be confirmed per model. **No fine-tuning** until evaluations show a specific need.

## 5–6. Health reminders & medication scheduling
Deterministic (`reminders/logic.ts`). The watcher raises reminders through the notification engine every minute while open. Reliable closed-app delivery requires the mobile app's OS notifications or Web Push with a service worker and a push server; not claimed today.

## 7–9. Campaigns, consultations, spiritual & yoga events
Verified registry schema (organization, title, city, venue, dates, eligibility, cost, registration, URL, `verifiedAt`, provenance). Sources: public-health departments, registered clinics, recognised NGOs. Ingestion via reviewed PRs to the feed file now, then a backend crawler with human verification. Screening campaigns are kept separate from diagnostic consultations. Eligibility is never computed without consent and guidelines.

## 10. Global sisterhood map
MapLibre GL + keyless OSM-based tiles, lazy-loaded; organisation-level markers only; list view parity; accounts, moderation and reporting before any member-to-member features.

## 11. Contacts, email, WhatsApp
Today: user-initiated links and the Contact Picker. Next: OAuth (Google/Microsoft) via a backend with separated read/write scopes; email parsing limited to appointment confirmations she approves; WhatsApp only via share flows or the official Business API for opt-in reminders.

## 12. Notification permissions
Browser permission requested only from Settings; categories off by default for spiritual, lifestyle (commercial) and joy; privacy mode on by default.

## 13. Offline
Everything implemented works offline (local storage). The connectivity indicator distinguishes online and offline. Next: service worker for offline app shell and cached education content.

## 14. GitHub Pages
`femora-ci.yml` (audit, typecheck, tests, build, bundle secret scan) and manual `femora-pages.yml`. **Not deployed**; awaiting approval and *Settings → Pages → Source: GitHub Actions*.

## 15. Mobile
Expo/React Native app reusing `modules/*/logic.ts` (pure TS). Platform adapters for encrypted storage, notifications, contacts, calendar, location and on-device llama.cpp; HealthKit / Health Connect adapters later.

## 16. Security & clinical safeguards
Consent-first memory; no hidden contact upload; nothing sent without her tap; private notification text; export and delete all data; rule-based crisis and urgent-symptom handling; no diagnoses, dose changes or invented intervals. Before production: clinical review of triage and copy, security testing, privacy/regulatory assessment, encrypted storage, audit logs.

## Next milestones
1. ~~Menopause journey~~ ✅
2. ~~Health dashboard~~ ✅
3. ~~Guardian~~ ✅ (server/mobile parts pending)
4. ~~Sisterhood map~~ ✅
5. ~~Onboarding tour + help centre~~ ✅; cinematic homepage media once licensed imagery or video is supplied.
6. Service worker / PWA offline shell; Lighthouse measurement.
