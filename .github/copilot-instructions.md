# Repository conventions for GitHub Copilot and Claude Code

This repository holds several independent projects (`convolens/`, `enterprise-agentic-ai/`, `lexguard/`, `femora/`).
Change only the project a task is about.

## FEMORA AI (`femora/`)

FEMORA Muse: a women's health and life companion. Web app on GitHub Pages first, mobile later. Plan: `femora/docs/MUSE_PLAN.md`.

### Hard rules
- **No invented data**: never fabricate events, discounts, appointments, free consultations, screening eligibility, lab values or citations. Listings need a verified source (`verifiedAt` + https URL) or must be user-added.
- Bea and Nancy are example configurations only; never assign them diagnoses, stages, beliefs or health details.
- Never put secrets or API keys in the frontend. Hosted AI goes through a server-side gateway; local AI via the user's own llama.cpp server.
- Numbers, schedules, notification decisions, triage and safety come from deterministic code (`logic.ts`, `engine.ts`, `safety.ts`), never from a model.
- No default screening intervals; only user/clinician/guideline-entered schedules. Never suggest changing medication.
- Nothing is sent, shared or saved externally without the user's explicit action.
- Label availability honestly with `StatusBadge` (`demonstrated` = available, `planned` = coming).
- Keep the creator credit (`src/components/Credit.tsx`) in the footer.

### Architecture
- `src/theme/tokens.css`: all colours, radii, shadows, fonts (luxury presets: onyx, emerald, midnight). Re-theme here only; components use token classes (`bg-surface`, `text-primary`, …).
- `src/modules/notifications/engine.ts`: every notification goes through `app.notify()` → `decide()`.
- `src/modules/muse/proactive.ts`: proactive suggestions from real records only.
- `src/modules/journey/logic.ts`: cycle maths and STRAW+10 educational hints (never a diagnosis or final-period prediction). Symptoms share `app.symptoms` with the copilot's log actions.
- `femora/ml/`: reproducible open-source training on public NHANES data → `src/modules/forecast/model.json`. Population context only; never predict an individual's final period. Report metrics honestly, including null results.
- `src/modules/body/logic.ts`: user-entered health records; guideline ranges (ACC/AHA, ADA) are explained, never scored.
- `src/modules/guardian/`: safety tools. Never claim a message or alert was sent or delivered; mark server/mobile-only capabilities in `CAPABILITIES`.
- `femora/evals/`: promptfoo agent evals (must stay green; add a case for every safety bug).
- New modules give the copilot facts via `ReplyContext` (deterministic), never raw guesses.
- `src/components/ui.tsx`: theme-agnostic primitives. `src/modules/navigation.ts`: the single navigation registry.
- `src/modules/<domain>/`: one folder per domain (`conversation`, `nutrition`, …), each with pure logic (`engine.ts`) separate from UI (`*Page.tsx`).
- `src/modules/conversation/types.ts` defines `ChatProvider`. To add a model, implement it and call `setProvider`; the UI is untouched.
- `src/lib/storage.ts`: versioned browser-local demo storage plus `resetDemo()`.
- Routing uses `HashRouter` so deep links work on static hosting.

### Workflow
1. Inspect the relevant files first and reuse what exists.
2. Make the smallest safe change on a feature branch. No unrelated refactors.
3. Add or update tests (`npm test`), then run `npm run typecheck` and `npm run build` in `femora/web`.
4. Report changed files and limitations. Don't deploy without the owner's approval (the Pages workflow is manual).
