# Operations: non-functional requirements, capacity, resilience, evaluation and load testing

## N. Service objectives (engineering targets, not guaranteed SLAs)

| Objective | Target | Status in this demonstration (measured) |
|---|---|---|
| API availability | 99.9% (future production design) | Design: ≥3 API replicas, PDB, HPA, multi-AZ DB (K8s/Terraform). Not measured over time. |
| Dashboard p95 (seeded data) | < 2 s | **Met at 50 users: p95 50 ms** (dashboards), 40 ms (detail). **Not met at ≥500 users on one host** (see below). |
| Standard AI workflow p95 | < 15 s (provider-dependent) | **Met at 50 users: p95 195 ms** with the in-process mock model. Real-LLM latency not measured. |
| Long-running analytics | asynchronous | `POST /api/jobs` + worker (scenario comparison, sensitivity, data quality, portfolio metrics). |
| Authorization on every protected operation | mandatory | Enforced by route dependencies, resource checks and the tool gateway; covered by security tests. |
| Cross-tenant leakage | zero tolerated | 0 in tests (data access, retrieval, approvals, vault, jobs, exports). |
| Unauthorized tool execution | zero tolerated | 0 in tests, including a compromised model plan. |

Resilience mechanisms: horizontal scaling (stateless API, HPA), **backpressure** (per-process in-flight cap → 503 +
`Retry-After`; DB pool timeout → 503; job-queue cap → 503), request **cancellation** (`/api/ask/{id}/cancel`),
**load shedding** (harness admission semaphore + HTTP in-flight cap), **queue-depth monitoring** (`flo_job_queue_depth`),
**circuit breakers** per upstream, **graceful degradation** (a failing market-data provider only affects the market
agents; other agents and dashboards keep working — tested), retries with exponential backoff and jitter.

## Load testing (`tests/load/loadtest.py`) — measured results

Environment: Docker Compose on **one 4-vCPU / 15 GB cloud container**; API = 2 uvicorn workers, `FLO_MAX_INFLIGHT=32`
per worker, DB pool 20+20; PostgreSQL, Redis, OPA, UI and the **load generator on the same host**. Workload: role-appropriate
mix — 65% dashboard reads, 15% detail reads, 15% Ask Flo workflows (mock model), 5% document search; think time 0.5–2 s;
45 s per run; seed 7. Raw data: [`evidence/load_test_report.json`](evidence/load_test_report.json).

| Virtual users | Requests | Throughput (req/s) | Success (2xx) | 503 load-shed | p50 / p95 latency (ms) by kind |
|---|---|---|---|---|---|
| 50 | 1,752 | 37.5 | 100.0% | 0 | ask 58 / 195 · dashboard 21 / 50 · detail 19 / 40 · search 142 / 206 |
| 500 | 3,197 | 60.0 | 79.8% | 645 | ask 6,342 / 15,105 · dashboard 4,759 / 12,412 · detail 4,554 / 12,505 · search 6,101 / 13,992 |
| 1,000 | 3,492 | 58.0 | 93.9% | 212 | ask 11,823 / 32,287 · dashboard 10,525 / 37,968 · detail 9,997 / 38,403 · search 10,277 / 37,984 |
| 5,000 | 7,247 | 55.5 | 90.7% | 673 | ask 66,724 / 116,893 · dashboard 66,091 / 116,763 · detail 65,630 / 113,745 · search 58,291 / 112,695 |

Interpretation (no extrapolation beyond what was measured):
* The host saturates at **~55–60 req/s**. Beyond that, demand at 500+ users (≈250–600 req/s offered) queues; latency
  targets are **not met** on a single host. Meeting them at those user counts requires horizontal scaling (more API
  replicas / nodes), which was **not** measured here.
* Every non-2xx response at saturation was a deliberate **503 with `Retry-After`** — no 500s, no crashes, no dropped
  connections — after two fixes made during testing:
  1. **Connection-pool exhaustion** (first 500-user run produced 500s and 60 s gateway timeouts): admission is now sized
     to the DB pool, pool timeout is 5 s, and pool exhaustion maps to 503 backpressure.
  2. **Search post-filter** made one policy (OPA) call per candidate chunk; now one per document (search p50 290 → 142 ms).
* The load test also exposed an RBAC gap (CIO/analyst lacked `product_research:read`), fixed in policy bundle 1.3.2.

Reproduce: `make up` then `make load-test USERS=50` (or 500, 1000, 5000).

## Y. Cost & capacity engineering

AI Operations dashboard: cost per workflow and per successful workflow, tokens, model latency, agent execution time,
agent-result cache and response cache hit rates, tool failure rate, queue depth, active workflows, concurrency
utilization, model utilization. Mechanisms: deterministic routing to the cheapest capable path (mock/in-process by
default; external model only where policy allows), context optimization (agents pass compact facts, not documents),
**permission-aware caching** (cache keys include tenant, roles, dataset version; authorization is evaluated before any
cache lookup), Redis shared cache with local fallback, async jobs, worker autoscaling (HPA; queue-depth metric
exported), provider failover limited by policy (non-compliant providers fall back to the in-process model, never to
another region). Mock-model cost is 0; historical synthetic traces use illustrative per-token prices.

## Disaster recovery

* Design: managed PostgreSQL with PITR ≥ 7 days (Terraform contract), multi-AZ, daily logical dumps, audit DB separable.
* **Backup/restore drill** (`scripts/backup_restore_drill.sh`, executed): `pg_dump` of the live stack → restore into a
  fresh database → row counts identical for every table → **audit hash chain valid on the restored copy (8,823 events)**.
* RPO/RTO targets (proposed): RPO ≤ 5 min (PITR), RTO ≤ 1 h. Not tested as a regional failover.

## Q. Quality engineering & evaluation

| Suite | Tooling | Result |
|---|---|---|
| Financial correctness | pytest (hand-computed expectations) | pass |
| Security & authorization (RBAC/ABAC, tenant, OPA parity, audit, privacy, approvals) | pytest | pass |
| Adversarial: cross-client, cross-tenant, tool bypass, prompt injection, malicious documents, exfiltration, approval replay & payload change, oversized input, provider failure | pytest | pass |
| End-to-end journeys (8 demos) | pytest + FastAPI TestClient | pass |
| Browser journeys | Playwright (Chromium) | 6/6 (dev and Docker stacks) |
| Evaluation set (groundedness, citations, retrieval relevance, tool selection, completion, authorization, privacy leakage, injection, multilingual, latency, cost) | `tests/evals/run_evals.py` | 10/10 — [`evidence/eval_report.json`](evidence/eval_report.json) |
| Static analysis / security lint / dependency audit / secret scan / TypeScript | ruff, bandit, pip-audit, regex scanner, tsc | pass — [`evidence/release_gate.json`](evidence/release_gate.json) |

`scripts/release_gate.py` blocks the release on any failing critical security or financial-correctness check. The gate
itself caught three real defects during development (an ungrounded template number, a classification error that broke
external-advisor product research, unused imports) — each fixed with a regression test.
