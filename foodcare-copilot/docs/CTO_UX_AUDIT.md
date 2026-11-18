# Flo & Jerry 2.0 → 3.0 — UX and capability audit

Date: 2026-11-17 · Branch `claude/new-session-pahp8j` · Method: source reading + running the app + existing tests.
README claims were checked against code and tests; "Verified by" names the evidence.

## 1. Capability inventory

| Capability | State | Verified by | Notes for 3.0 |
|---|---|---|---|
| Executive Command dashboard | Implemented | `screens/Executive.tsx`, `e2e/enterprise.spec.ts` | 17 cards/charts on one page; no "what changed" or priority ordering |
| Ask Copilot (Jerry), deterministic + citations | Implemented | `copilot/engine.py`, `test_enterprise.py` | Strong evidence model; no answer feedback; suggestions not page-aware |
| Local Qwen (OpenAI-compatible) | Implemented, tested against a mock | `llm/local.py`, `test_local_llm.py` | No real Qwen in CI — say so in Jerry's status |
| Global supply-chain globe, OriginTrace | Implemented (synthetic scenario) | `geo.py`, `test_geo.py`, `e2e/geo.spec.ts` | Reuse as-is inside "Global Network" and as an optional module on the Pulse |
| Potato inspection + Quality Intelligence | Implemented (classical CV, not a trained model) | `vision/*`, `test_vision.py`, `e2e/inspection.spec.ts` | Keep wording "not a trained model" |
| Sales, inventory, compliance | Implemented (synthetic data) | `enterprise/queries.py`, `test_enterprise.py` | Source for business health + priorities |
| Agent Intelligence graphs | Implemented | `graphs.py`, `e2e/agents.spec.ts` | Technical — belongs in Technology workspace |
| Observability, token usage, `/metrics` | Implemented | `observability.py`, `test_observability.py` | Source for AI-service health and cost |
| Model Evaluation Lab | Implemented | `ml/*`, `e2e/evaluation.spec.ts` | Technology workspace |
| SQLite memory + audit | Implemented | `memory/*`, `test_memory.py` | Extend with visits, decisions, investigations, feedback (migration 7) |
| Roles & permissions | Implemented server-side (5 roles) | `auth.py PERMISSIONS`, `test_workflow.py` | **No CTO/CEO/factory/quality/supply/sales/admin roles exist** |
| "Since last visit", decision journal, investigations, weekly review | **Missing** | — | Build (Phase 5) |
| Enterprise time machine | **Partial data**: 16 weeks of synthetic weekly sales; inspection history; agent-run history | `ent_sales`, `inspection_batches`, `agent_runs` | Build a week-over-week comparison on these; document gaps |
| Real ERP/sensor/tracking integrations | **Not connected** | data-sources panel | Unchanged; shown honestly |

## 2. UX problems found

| # | Problem | Evidence | Research link | Fix in 3.0 |
|---|---|---|---|---|
| U1 | **20 flat navigation links** in 6 groups; delivery jargon ("Brief intake", "Engineering") visible to every role | `components/Layout.tsx NAV` | Progressive disclosure (Nielsen 2006) | 7 primary items, one secondary level, role lenses |
| U2 | **Developer controls in the global header** (guided demo, run selector, storefront URL, release SHA) | `Layout.tsx` header | Cognitive load (Sweller 1988); [H] executives | Move to Technology › Digital delivery |
| U3 | Home page answers *what is*, not *what changed / why / what next* | `Executive.tsx` (17 cards) | Hjelle et al. 2024 (perceived complexity) | Enterprise Pulse: briefing, ≤ 3 priorities, ≤ 5 health indicators |
| U4 | No memory of the user's previous visit, decisions or investigations | schema has no such tables | Bhattacherjee 2001; Amershi G12/G18 | Visits, Decision Journal, Investigations |
| U5 | Alerts (bell, "Needs attention") link to pages, not to an explanation → evidence → action path | `Layout.tsx Notifications` | Amershi G11 | Guided investigation panel |
| U6 | Jerry's answers cannot be rated or corrected | `Copilot.tsx` | Amershi G9/G15 | Helpful / Not helpful + comment, stored |
| U7 | Jerry is not page-aware (same examples everywhere) | `/api/copilot/examples` | Amershi G4 | Page-specific suggested questions |
| U8 | Technology health requires reading raw metrics | `Observability.tsx` | Progressive disclosure | Five plain questions with "Show diagnostics" |
| U9 | Small type in many tables (`text-xs`) | multiple screens | WCAG 2.2 | Larger base sizes on new screens; existing screens unchanged where dense tables are intended |
| U10 | Light/dark token names are inverted ("navy" = ink) — confusing for maintainers | `tailwind.config.js` | — | Documented; new tokens use semantic names (`ink`, `midnight`, `champagne`, `teal`) |

## 3. Constraints carried forward
* All demo scenarios, endpoints and tests must keep working; permissions stay server-side and unchanged.
* Synthetic / modelled / operational / verified labelling must stay visible.
* Local-first: no new cloud services, fonts are system/Inter fallbacks (no font CDN at runtime).
