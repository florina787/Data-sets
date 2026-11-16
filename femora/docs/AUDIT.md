# FEMORA AI: Milestone 0 audit and plan

> **Superseded** by [MUSE_PLAN.md](MUSE_PLAN.md). The leadership-demo scope (synthetic data, simulations) was retired at the creator's request; this file is kept for history.

*Prepared 16 Nov 2026. Scope: the `florina787/Data-sets` repository, which is the only repository this build session can access.*

## 1. Existing architecture inventory

| Project | What it is (verified from source) | Stack | Tests / CI |
|---|---|---|---|
| `convolens/` | Agentic conversation-analysis system with "Flo", a chat analyst over 3,000 Kaggle support conversations | FastAPI + LangGraph + LangChain (Python 3.11+), React 19 + Vite + TypeScript + Tailwind 4 + Vitest | 101 tests; `.github/workflows/convolens-ci.yml` |
| `enterprise-agentic-ai/` | Enterprise copilot: LangGraph supervisor, RAG (ChromaDB), tool agent, guardrail, tracing, DEMO mode with no API key | FastAPI, LangGraph, ChromaDB, Streamlit UI | pytest |
| `lexguard/` | Legal AI control tower: 15 agents, deterministic control layer, citation verification, hash-chained audit, synthetic data | Python backend, Next.js 15 frontend | Vitest + pytest |
| Root | Classic ML datasets (CSV), notebooks | n/a | n/a |

**MedAccess AI was not found.** It isn't in this repository, and this session's GitHub access lists only `florina787/Data-sets`. To reuse its provider-discovery code, attach that repository to a session (or copy it into this repo) and Milestone 7 will build on it. Nothing in FEMORA assumes MedAccess capabilities exist.

## 2. Reusable components

| Reuse | From | How it's used in FEMORA |
|---|---|---|
| Frontend stack and tooling (React 19, Vite, TS, Tailwind 4, Vitest, lucide) | ConvoLens | Same versions, so knowledge and CI patterns carry over |
| XSS-safe Markdown renderer | `convolens/frontend/src/lib/markdown.tsx` | Adapted to `femora/web/src/lib/markdown.tsx` with `[S1]` source citations |
| Card / Button / Badge / Notice primitives pattern | `convolens/frontend/src/components/ui.tsx` | Re-implemented on design tokens so they're themeable |
| CI workflow shape (npm ci → typecheck → test → build) | `.github/workflows/convolens-ci.yml` | `.github/workflows/femora-ci.yml` |
| Gemini free-tier integration, scripted test models | ConvoLens backend | Pattern for the future AI gateway (server-side, never in the browser) |
| Supervisor routing, guardrail, citation validation, DEMO mode | enterprise-agentic-ai | Pattern for FEMORA's router (`router.ts`) and future live mode |
| Deterministic control layer before any model, audit trail, synthetic-data discipline | LexGuard | Safety rules run before providers; honest status labels |

The ConvoLens `Flo` chat component itself is tightly coupled to the ConvoLens API and analytics, so FEMORA reuses its patterns rather than the component.

## 3. Missing features (versus the master prompt)

Built in this first increment: app shell, theming, executive showcase, copilot (simulated), food and nutrition, Joy Map, profile and privacy settings.
Still missing: menstrual, ovulation and symptom tracking (M3); body health, walking, sleep and mood (M5); sisterhood map (M6); healthcare and Guardian (M7); guided 5-minute demo mode (M8); environmental data; live AI; the 100-paper review; PWA offline caching; multilingual UI.

## 4. FEMORA module structure

The master prompt suggests a monorepo with `packages/`. To avoid empty scaffolding, the first increment keeps one Vite app with **domain modules shaped like future packages**:

```
femora/
├── docs/AUDIT.md               ← this document
└── web/src/
    ├── theme/tokens.css        ← design tokens and theme presets (sky, forest, indigo; light and dark)
    ├── components/             ← theme-agnostic UI primitives, AppShell, Credit
    ├── lib/                    ← storage (versioned, resettable), markdown, app state
    ├── data/demo/              ← fictional personas (Bea, Nancy)
    ├── modules/
    │   ├── navigation.ts       ← single navigation registry with status per module
    │   ├── conversation/       ← types (ChatProvider), safety, router, scripted provider, sources, store, UI
    │   └── nutrition/          ← foods DB, deterministic engine, store, summary for the copilot, UI
    └── pages/                  ← showcase, home, joy, settings, planned
```

Each `modules/<domain>` folder keeps pure logic separate from UI, so it can move into `packages/<domain>` when the mobile app needs to share it. A UI redesign touches `tokens.css` and page components only. A model change touches only a `ChatProvider` implementation.

## 5. GitHub Pages deployment plan

- `HashRouter`, so deep links work without a server fallback. The base path is injected via `FEMORA_BASE=/<repo>/` at build.
- `.github/workflows/femora-ci.yml` runs on PRs and on push to `master`: npm audit, typecheck, tests, build, and a secrets scan of the bundle.
- `.github/workflows/femora-pages.yml` is **manual (workflow_dispatch)** because deployment needs owner approval. One-time setup: *Settings → Pages → Source: GitHub Actions*. The site will be at `https://florina787.github.io/Data-sets/`.
- Verified locally: production build served under `/Data-sets/`, walked through in Chromium (desktop and iPhone 13 viewport) with no console errors.

## 6. AI model strategy

- **Provider-independent.** The UI talks to a `ChatProvider` interface; `router.ts` runs safety rules first, then the active provider, and falls back to the offline scripted provider on failure.
- **Demo now:** a scripted provider with reviewed templates, clearly labelled "Simulation".
- **Live next:** a small server-side AI gateway (for example a serverless function) holding keys, with rate limits and cost caps. A hosted free-tier model (Gemini, already integrated in ConvoLens) is the fastest path. The browser never holds keys.
- **Offline later:** benchmark compact open-weight models (for example Qwen2.5 1.5B, Llama 3.2 1B/3B, Gemma 3 1B/4B, Phi-4-mini, SmolLM2 1.7B) in GGUF via llama.cpp on mobile, and WebLLM or wllama in the browser. Score them on conversation quality, multilingual ability, health-misinformation rate, safety, latency, memory and **licence**. Licences differ per model and size, so confirm them during benchmarking. Don't default to 7B.
- **RAG** over a graded evidence base (§14) for education. Numbers always come from deterministic code. Safety decisions use rules.

## 7. Demo-data strategy

Two personas named for the CEO (**Bea**) and partner (**Nancy**), at the creator's request. Their health stories are explicitly **fictional** in the UI, data and code comments. Between them they cover the late menopausal transition and postmenopause, vegetarian and omnivore diets, living alone versus with family, and cuisines from South Asia, Europe, the Middle East, East Asia, Latin America, North America and West Africa. Six days of food logs are seeded per persona. Everything is stored in browser localStorage with a **Reset demo** button. A banner on every app page says data is fictional and AI is simulated.

## 8. Global sisterhood map plan (Milestone 6)

MapLibre GL JS with a free, keyless OpenStreetMap-based tile source (for example OpenFreeMap), with an attribution footer. Data comes from a GeoJSON file with two clearly separated layers:
1. **Real organisations** (for example The Menopause Society, British Menopause Society, International Menopause Society) at **headquarters-city level**, with a source URL and "verified on" date.
2. **Synthetic circles and events**, labelled "Example".

Features: clustering, search, filters (country, language, online or in-person, free or paid, topic, accessibility), and an accessible list view. No home addresses or precise personal locations.

## 9. Nutrition engine plan

Built: curated sample database of 42 dishes across 10 regions, 14 nutrients, editable portions, a deterministic natural-language matcher, missing data labelled rather than counted as zero, editable targets, and evidence-strength labels. The copilot quotes weekly protein, alcohol days, caffeine and calcium from the engine. Default reference targets for women over 50 come from US Dietary Reference Intakes (calcium 1,200 mg; vitamin D 15 µg; iron 8 mg; B12 2.4 µg; fiber 21 g), WHO free-sugar guidance (about 25 g) and the FDA caffeine guidance (400 mg). Protein is set to 60 g as an editable placeholder pending review. Next steps: replace the sample values with national food-composition tables (USDA FoodData Central, IFCT India and others) with per-item provenance, recipes and saved meals, barcode lookup, and photo estimation.

## 10. Clinical and privacy safeguards

- Rule-based safety layer before any AI: crisis and self-harm, abuse, and urgent symptoms such as postmenopausal bleeding or chest pain lead to emergency guidance and findahelpline.com.
- No diagnoses, no universal health score, no "cure" claims, uncertainty stated (for example "nobody can predict the exact final period").
- Memory is **off by default**. Facts are proposed and saved only on approval, and can be reviewed and deleted.
- Conversations can be exported and deleted. Demo storage is local and unencrypted, and the app warns against entering real data.
- Production: encrypted local store, authentication, consent records, separate stores for health records, conversations, communities and emergency contacts, audit logs, retention policies, DPIA and regulatory assessment (for example GDPR, HIPAA where applicable, medical-device classification review).

## 11. Development milestones

| # | Milestone | Status |
|---|---|---|
| 0 | Repository audit and architecture | ✅ this document |
| 1 | Pages foundation, responsive shell, navigation, theme system | ✅ built; Pages deploy awaiting approval |
| 2 | Conversational copilot (simulated) | ✅ built |
| 3 | Menopause tracking: cycles, ovulation, symptoms, staging education | ⏳ next |
| 4 | Food logging and nutrition intelligence | ✅ built (sample database) |
| 5 | Body health, wellbeing, walking, sleep | ⏳ |
| 6 | Sisterhood map and communities | ⏳ |
| 7 | Healthcare navigation (MedAccess reuse) and Guardian simulation | ⏳ needs MedAccess repo access |
| 8 | Showcase polish, guided 5-minute demo, accessibility and performance testing | ⏳ |
| 9 | Leadership-demo release candidate | ⏳ |

## 12. First implementation changes (this increment)

- New `femora/web` app (see §4) with 62 passing tests (nutrition engine, safety, copilot routing and citations, navigation of every route, multi-message chat, natural-language food logging, personas).
- `.github/workflows/femora-ci.yml`, `.github/workflows/femora-pages.yml`, `.github/copilot-instructions.md`.
- Existing projects untouched.

## 14. Research workstream (not started)

The 100-paper evidence review hasn't been done and isn't claimed. It will search PubMed, PubMed Central and Crossref across the 20 topics in the master prompt. Each study is recorded with title, DOI, year, design, population, sample size, findings, limitations, evidence quality and the FEMORA feature it applies to, stored in `femora/data/research/`. The copilot currently cites three sources: WHO menopause fact sheet, STRAW+10 (Harlow et al., 2012) and NICE NG23.
