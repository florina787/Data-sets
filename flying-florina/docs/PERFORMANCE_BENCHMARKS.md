# Performance benchmarks (measured)

Every number below was measured on the build machine (Linux container, 4 CPUs, no GPU, Python 3.13) on 2026-11-02. Raw data:
[`performance_3_0_measured.json`](performance_3_0_measured.json) (`scripts/benchmark_3.py`), [`latency_measured.json`](latency_measured.json)
(3.0 code) and [`latency_measured_2_0_rerun.json`](latency_measured_2_0_rerun.json) (2.0 commit `bef7b48`, same machine, same day,
same script). **No local Qwen model exists on this machine**, so no model latency is included or claimed; run the same scripts on
your hardware with Qwen connected.

## Baseline (2.0) vs post-upgrade (3.0): the existing workflows

Warm median per request (routing + agents + tools + workspace; `scripts/measure_latency.py`, model fitting disabled during the run):

| Workflow | 2.0 code | 3.0 code | Ratio |
|---|---|---|---|
| Q1 aircraft diagnostics | 217 ms | 243 ms | 1.12 |
| Q2 aircraft recovery | 472 ms | 421 ms | 0.89 |
| Q3 legacy assessment | 261 ms | 324 ms | 1.24 |
| Q4 executive readiness | 212 ms | 265 ms | 1.25 |
| maintenance investigation | 415 ms | 402 ms | 0.97 |
| scenario compare | 155 ms | 207 ms | 1.34 |
| downtime analysis | 1,191 ms | 1,431 ms | 1.20 |
| bridge generation | 142 ms | 175 ms | 1.23 |
| governance review | 113 ms | 155 ms | 1.37 |
| executive pitch | 237 ms | 274 ms | 1.16 |
| document freshness | 101 ms | 125 ms | 1.24 |
| recovery options | 410 ms | 487 ms | 1.19 |
| data export (denied) | 71 ms | 89 ms | 1.25 |
| **startup incl. seeding** | 1.73 s | 2.29 s | 1.32 |

3.0 adds a median ~20% (20–60 ms) to 2.0 workflows: two persisted memory messages + structured summary per turn, the 3.0 router
stage, and a larger tool allowlist. Two regressions found during this measurement were fixed before the numbers above: the pinned tool
allowlist is now cached by file modification time (it was re-parsed on every tool call and doubled in size), and scikit-learn/SciPy
load only while fitting (app import 2.1 s → 0.9 s). Note that the 2.0 numbers recorded on 2026-10-31 (163 ms for Q1) were measured on a
less loaded machine; only same-day comparisons are meaningful.

## 3.0 features

| Measurement | Result |
|---|---|
| Cold start → `/health` (fresh data folder, seeding included) | 2.14 s |
| Forecast model fit (background, cold) | 16.8 s this run (11–17 s across runs; up to ~45 s when it overlaps first-run seeding on a busy machine) |
| Warm restart → `/ready`, results loaded from cache | 1.08 s; first map request 0.03 s; 1 conversation restored |
| Backend memory (RSS) after the full run / after warm restart | 220 MB / 77 MB (scikit-learn not loaded when the cache exists) |
| Backend CPU | 57 s CPU over 31 s wall (model fit uses several cores) |
| Chat, 12 suggested 3.0 questions (first call each) | p50 251 ms, p95 1,515 ms, max 1,694 ms |
| Slowest 3.0 chats | resilience scenario 1.69 s (3 × 200 Monte Carlo paths), visual capabilities 1.51 s (re-evaluates 58 frames), change impact 0.80 s (first graph build, then cached) |
| Chat, four 2.0 questions in the same run | p50 408 ms, max 588 ms |

### API latency and concurrency (8 parallel clients, 40 requests)

| Endpoint | Sequential p50 | Concurrent p50 | Concurrent p95 | Throughput |
|---|---|---|---|---|
| `/api/global/map?horizon=60` | 15.8 ms | 110 ms | 151 ms | 67 req/s |
| `/api/forecast/components?horizon=90` | 16.5 ms | 110 ms | 135 ms | 73 req/s |
| `/api/global/timeline` (all 6 horizons, ~240 KB) | 40.3 ms | 280 ms | 328 ms | 27 req/s |
| `/api/harness/control-tower` | 31.8 ms | 231 ms | 268 ms | 34 req/s |

Single uvicorn worker (SQLite single-writer); concurrency is bounded by the GIL and the workflow semaphore, not by locks.

### Map rendering (headless Chromium, software WebGL)

| Mode | Navigation → data + map drawn | Horizon switch |
|---|---|---|
| Globe (MapLibre, SwiftShader CPU rendering) | 3.8 s | 2.0 s |
| Lite (SVG) | 4.0 s | 0.37 s |

Software WebGL is far slower than a GPU; on phones the page defaults to the Lite map for this reason. The 3.8–4.0 s includes the
dev server's module loading and the timeline request.

## Resource protection in place

Bounded Qwen context (2,400-character memory window, 4,096-token context) and output (320 tokens), one generation at a time, warm
single model instance, exact-prompt cache, one explanation per answer; tool-call and wall-clock budgets per plan; finite DAGs (no
loops); one fit of the forecasting models per dataset version, cached on disk; lazy loading of heavy ML libraries.

## Not measured here

Qwen latency, time to first token, tokens/s and Qwen-routed accuracy (no model on this machine); GPU rendering; multi-replica
deployments (not supported with SQLite). No response-time promise is made beyond these measurements.
