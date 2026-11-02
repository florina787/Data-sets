# Flying Florina 3.0 — architecture audit (Phase 0)

Audited before any 3.0 code was written. Repository `florina787/Data-sets`, application folder `flying-florina/`, working branch
`claude/new-session-yijwxb` (clean, in sync with `origin`, last commit `bef7b48` + README commit). Other folders in the repository
(`convolens`, `enterprise-agentic-ai`, `lexguard`, data files) are unrelated and are not touched.

## 1. Inventory

| # | Area | What exists (2.0) | Classification | 3.0 action |
|---|---|---|---|---|
| 1 | Frontend | React 18 + TypeScript + Vite + Tailwind 4, TanStack Query, Zustand, ECharts, React Flow, framer-motion; 18 pages; CIC design tokens in `index.css` | Existing, reusable | Re-theme tokens (navy/cyan/teal), 10-section navigation, new feature pages |
| 2 | Backend | FastAPI + Pydantic v2, 4 routers (`routes_core`, `routes_trust`, `routes_llm`, `routes_insights`), typed error envelope, security headers | Existing, reusable | New routers for 3.0 modules |
| 3 | Qwen integration | `app/llm/gateway.py` single gateway: discovery, llama.cpp / Ollama / OpenAI-compatible runtimes, cache, concurrency 1, context budget, timeout, schema validation, telemetry | Existing, reusable | Add capability probe (text vs vision, context, quantization); reuse unchanged for explanations |
| 4 | Local model files / endpoints | Auto-discovery of `*qwen*.gguf` and loopback servers. No model present in the build container | Existing; model not present here | Keep; report honestly |
| 5 | Agent orchestration | Own typed DAG engine (`workflows/engine.py`): waves, retries, timeouts, cancellation, checkpoints, real event log. LangGraph not used | Existing, reusable | Wrap in a governed **harness**: agent registry, planner, budgets, trace |
| 6 | Chatbot | Mission Control + hybrid router (policy → greeting → follow-up → rules → semantic → Qwen → fallback), four question cards | Existing, needs enhancement | New 3.0 intents (forecast, map, supply chain, twin, change impact, visual lab, history) |
| 7 | Dashboards / charts | ECharts wrapper (`Chart.tsx`: line/bar/area/pie/heatmap/scatter), Command Center, Predictive, Observability | Existing, reusable | Add gauges, interval bands, map |
| 8 | Database / memory | SQLite (WAL), `sessions`, `workflow_runs`, `workflow_events`, `conversation_context`; DB persists across restarts (seeded only when missing) | Existing, needs enhancement | Versioned migrations, `messages`, `conversations` view, preferences, forecast runs, saved scenarios, memory API + delete |
| 9 | API endpoints | 61+ OpenAPI paths | Existing, reusable | Additive only |
| 10 | Simulation | `simulation/engine.py`: delay scenarios, seeded Monte Carlo, ROI | Existing, reusable | Reuse pattern for resilience simulator |
| 11 | Auth & governance | Demo personas + signed tokens, policy engine POL-001…013 deny-by-default, tool allowlist with schema-hash pins, approvals with separation of duties, kill switch, hash-chained audit, egress guard | Existing, reusable | New tools pinned in the allowlist; harness budget policy |
| 12 | Docker | `docker-compose.yml`, backend + frontend Dockerfiles | Existing, needs enhancement | Add optional local-Qwen service profile, health checks, resource limits |
| 13 | Kubernetes | None | Missing | Reference manifests (single-writer SQLite) |
| 14 | Tests | pytest 131, Vitest 9, Playwright 18, generated adapter 14 | Existing, reusable | Add 3.0 tests; keep all existing passing |
| 15 | Documentation | 20 docs incl. Qwen, four-question, readiness, eval | Existing | Add 9 required 3.0 docs (update `DEPLOYMENT.md`) |
| 16 | Branch / uncommitted | Clean working tree | — | Continue on the designated branch |
| 17 | Reusable visual components | `ui.tsx` (Card, Stat, Badge, Skeleton…), `Chart`, `DataTable`, `AgentGraph`, `AgentTimeline`, `Workspace` renderer, `QwenBlocks` | Existing, reusable | Reuse in every 3.0 page |
| 18 | Aerospace datasets | Seeded synthetic fleet (aircraft, telemetry, work orders, parts, inventory, suppliers, documents, legacy apps) | Existing, reusable | Add a separate, seeded **global** dataset (facilities, components, suppliers, history) |
| 19 | Performance optimizations | Compact fact packs, one Qwen call per answer, exact-prompt cache, warm model, workspace rendered before explanation | Existing, reusable | Keep; forecasts cached per run in SQLite |
| 20 | Conversation persistence | `sessions` + `workflow_runs` + `conversation_context` survive restarts | Existing, needs enhancement | Explicit messages, summaries, context budgeting, slot memory (category/region/horizon) |

Experimental/incomplete: none found. Deprecated: none (nothing removed in 3.0).

## 2. Dependency analysis

| New dependency | Why | Licence | Cost |
|---|---|---|---|
| `numpy`, `scikit-learn` (pulls `scipy`, `joblib`, `threadpoolctl`) | Genuine models: gradient-boosted quantile regression, random forest, isolation forest, calibration metrics | BSD-3 | Free, local, CPU |
| `Pillow` | Read uploaded images / animated GIF frames for the visual lab | MIT-CMU | Free, local |
| `maplibre-gl` (v6) | Interactive map with globe projection, no tile service required | BSD-3 | Free |
| `world-atlas` + `topojson-client` | Bundled Natural Earth country outlines (public domain) so the map works offline | ISC | Free |

Not added: XGBoost (scikit-learn's `HistGradientBoostingRegressor` covers it without a native dependency), deck.gl (MapLibre layers are
sufficient for 12 facilities and a few dozen links), LangGraph (the existing engine already provides the needed semantics), any paid
map/tile/LLM API, any vision model download. `ffmpeg` is used for video frame sampling **only if it is already installed**.

## 3. Implementation plan (vertical slices)

| Priority | Slice | Reuses |
|---|---|---|
| P0 | This audit; preserve everything | — |
| P1 | Global synthetic dataset → forecasting engine (temporal split, baselines, intervals, metrics) → global map with 6 layers and the +0…+90 day timeline → chat intents calling the same functions | DAG engine, workspace blocks, Chart, policy gateway |
| P2 | Migrations + persistent memory with slot follow-ups; agent harness (registry, planner, budgets, trace); Control Tower | engine events, llm_calls, policy_decisions, approvals |
| P3 | Component digital twin; supply-chain delay impact; resilience simulator (baseline vs disruption vs recovery) | simulation engine pattern |
| P4 | Civilian visual-analysis lab (capability-honest); software change-impact analysis of this repository + a synthetic requirements set | Qwen gateway, egress guard |
| P5 | Docker/K8s reference, benchmarks, docs, README, tests | existing compose, measure scripts |

## 4. Risks and boundaries

* No Qwen model and no vision model exist in the build container: Qwen-dependent features are tested with the test-only fake server; the
  visual lab reports "no vision model found" and runs a labelled, classical (non-AI) baseline on synthetic labelled frames.
* SQLite is single-writer: the Kubernetes reference runs one backend replica with `Recreate` strategy.
* Defense-related locations are fictional; the map shows no military assets and no drone routes; the visual lab has no tracking,
  targeting, interception or intent features.
