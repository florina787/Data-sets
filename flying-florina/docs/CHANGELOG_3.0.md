# Flying Florina 3.0: what changed

Enhancement of 2.0 (nothing rebuilt, no functionality removed; every 1.0/2.0 route, API, workflow and test still works).
Phase-0 audit: [FLYING_FLORINA_3_ARCHITECTURE_AUDIT.md](FLYING_FLORINA_3_ARCHITECTURE_AUDIT.md).

## Delivered

| Area | What | Docs |
|---|---|---|
| Global Intelligence | MapLibre globe / 2D / SVG-lite map, 6 layers, TODAY→+90-day timeline, search, category filter, region comparison, drill-downs, report export; no tile service | [GLOBAL_MAP.md](GLOBAL_MAP.md) |
| Component forecasting | Poisson gradient boosting + split-conformal intervals, Weibull survival RUL, RandomForest failure risk, IsolationForest anomalies, quantile lead-time model, repair TAT, reorder-policy inventory simulation, workload and cost; held-out evaluation vs baselines | [FORECASTING_ENGINE.md](FORECASTING_ENGINE.md) |
| Digital twin | Unit metadata, installation/maintenance/replacement history, telemetry, flags with reasons, uncertainty over time, documents to review; advisory only | — |
| Supply chain | Supplier trends, lead-time distributions, variability, concentration (HHI), repair capacity, dependency graph, delay-impact simulator with planning alternatives | — |
| Operational resilience | 8 scenarios, baseline vs disruption vs recovery, backlog P10/P50/P90, recovery time, availability, cost, mitigation sliders, saved scenarios | — |
| Agent harness | 12 specialist agents with tool allowlists, 11 pinned typed tools, planner, atomic budgets, evidence validation, plan records | [AGENT_HARNESS.md](AGENT_HARNESS.md) |
| Control Tower | 6 panels from recorded events: graph, timeline, governance, model performance, evaluation, recovery | [AGENT_HARNESS.md](AGENT_HARNESS.md) |
| Persistent memory | Versioned migrations, messages + FTS, structured summaries, slot-carrying follow-ups, bounded model context, owner-only deletion | [FLYING_FLORINA_3_ARCHITECTURE.md](FLYING_FLORINA_3_ARCHITECTURE.md) |
| Airspace Safety Lab | Capability detection (text-only Qwen, no vision model), labelled synthetic frames and clips, classical non-AI baseline with FP/FN statistics, uploads (hash-only storage), evidence reports; civilian scope only | [SECURITY_GOVERNANCE.md](SECURITY_GOVERNANCE.md) |
| Software change impact | Real static analysis of this repository: affected modules, routes, screens, regression tests, requirements traceability with missing-evidence detection, config comparison, release report | — |
| Chat | 12 suggested 3.0 questions running real planned workflows, memory panel with restore/delete | — |
| Deployment | Hardened Compose (read-only, limits, health), Kubernetes reference (single-writer backend, probes, network policies, ingress gateway, optional Qwen sidecar) | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Design | Navy/cyan/teal theme, glass panels, illuminated borders; 10 primary sections, every 2.0 page under Workspace | — |

## Measured (build machine, 2026-11-02)

| Check | Result |
|---|---|
| Backend pytest | 160 passed (2.0: 131) |
| Vitest | 9 passed |
| Playwright e2e | 22 passed (2.0: 18; +4 for 3.0 pages and chat) |
| Lint / typecheck / build | clean |
| 3.0 intent routing, fresh held-out (rules only) | 90.3% (56/62), follow-ups 3/4 — below the 95% target |
| 2.0 held-out v2 routing after 3.0 | 95.8%, macro-F1 0.958 (unchanged) |
| Demand forecast, 90 days | MAE 2.86 vs 4.03 moving average; 80% interval coverage 66.7% (under-covers) |
| Anomaly detection | IsolationForest F1 0.869 < z-score rule F1 0.974 (baseline wins; reported) |
| 2.0 workflow latency on 3.0 | median ~1.2× the 2.0 code measured the same day |

## Known limitations

* No Qwen or vision model on the build machine: Qwen-dependent paths are tested with a test-only fake server; no model latency is claimed.
* Docker images were not built (no Docker daemon here); the Kubernetes manifests were parsed but not applied to a cluster.
* 3.0 intent routing is below target on rules alone; supplier names without the word "supplier" are a known gap.
* Long-horizon forecast intervals under-cover; RUL evaluation favours early failures.
* All data is synthetic; disruption notices are synthetic scenario events.
* `npm audit` reports advisories in the frontend dependency tree (dev tooling and transitive packages); not addressed in this release.
