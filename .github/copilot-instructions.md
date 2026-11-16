# Repository conventions for GitHub Copilot and Claude Code

This repository holds several independent projects (`convolens/`, `enterprise-agentic-ai/`, `lexguard/`, `femora/`).
Change only the project a task is about.

## FEMORA AI (`femora/`)

Menopause-first women's health platform. The current milestone is a **static leadership demo** on GitHub Pages.

### Hard rules
- Synthetic data only. Demo personas are **Bea** and **Nancy**; their health details are fictional and must be labelled so.
- Label every capability honestly with `StatusBadge`: `demonstrated`, `simulated`, `planned`, or `validated` (nothing is validated yet).
- Never put secrets or API keys in the frontend. Live AI calls must go through a server-side gateway.
- Never fabricate citations. Every cited source lives in `src/modules/conversation/sources.ts` and must be real and retrievable.
- Numbers (nutrients, cycle lengths, totals) come from deterministic code, never from a model.
- Safety rules (`src/modules/conversation/safety.ts`) run before any provider. Don't bypass them.
- No universal "menopause score" or health-risk score.
- Never diagnose (depression, dementia, anxiety disorders) and never claim a food cures menopause.
- Keep the creator credit (`src/components/Credit.tsx`) in the footer.

### Architecture
- `src/theme/tokens.css`: all colours, radii, shadows, fonts. Re-theme here only; components use token classes (`bg-surface`, `text-primary`, …).
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
