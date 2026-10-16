# Deployment & Capacity Planning

## Local (Profile A)

```bash
cd medaccess-ai
docker compose up --build                       # http://localhost:8080 (UI), :8000 (API, /docs)
docker compose --profile monitoring up --build  # + Prometheus :9090, Grafana :3001 (admin / GRAFANA_ADMIN_PASSWORD)
```

Behind a TLS-intercepting proxy, pass its CA as a BuildKit secret (it is never baked into the image):

```bash
docker build --secret id=extra_ca,src=/path/to/ca.crt -f backend/Dockerfile  -t medaccess-ai-backend  .
docker build --secret id=extra_ca,src=/path/to/ca.crt -f frontend/Dockerfile -t medaccess-ai-frontend .
docker compose up        # uses the pre-built images
```

The backend container runs `alembic upgrade head` and then seeds synthetic data on start. Without Docker,
see the README "Local development" section (SQLite, no services needed).

## Measured baseline (this repository, sandbox host)

Measured with `infrastructure/ci-cd/load_test.py` against **one** uvicorn worker, SQLite, synthetic data,
deterministic copilot (no LLM), on a 4-vCPU / 16 GB Linux container. Each request runs the full 13-node
patient LangGraph with checkpointing, audit writes and result persistence.

| Scenario | Requests | Throughput | p50 | p95 | p99 | Errors |
|---|---:|---:|---:|---:|---:|---:|
| concurrency 1 | 50 | 6.5 req/s | 149 ms | 204 ms | 224 ms | 0 |
| concurrency 8 | 200 | 5.5 req/s | 1430 ms | 1640 ms | 1683 ms | 0 |

Backend resident memory after ~250 searches: ≈ 148 MB. Throughput does not scale with concurrency on a single
worker: the workflow is CPU-bound Python plus serialised SQLite writes (audit hash chain, checkpoints).
Re-measure on your hardware before using these numbers; they are not portable benchmarks.

## Profile A — local demonstration

* 1 user, synthetic data. Measured footprint above fits comfortably in **2 vCPU / 4 GB RAM** with Docker Desktop
  (backend ≈150 MB, PostgreSQL + Redis + nginx typically a few hundred MB; Docker Desktop overhead extra).
* Storage: images ≈1–2 GB; data volume < 100 MB for demo use. No inbound network needed; outbound only to pull images
  (and optionally the LLM / LangSmith APIs).

## Profile B — small pilot

* Assumption to validate: ≤ 2 searches/s peak. From the measured ~6 req/s per worker at p95 ≈ 0.2 s (concurrency 1),
  2–3 uvicorn workers on 2 replicas give headroom: `workers_needed = ceil(peak_rps / measured_rps_per_worker × 1.5 safety)`.
* Managed PostgreSQL (small instance), Redis for the shared rate limiter, **PostgresSaver for LangGraph checkpoints**
  (required before >1 replica — the SQLite checkpoint file is per-container).
* Centralised OTel collector + Prometheus/Grafana; LangSmith only with redaction and an approved privacy basis.
* Authorized integrations only (Mode C), each behind its own circuit breaker.

## Profile C — enterprise

* Horizontal scaling behind a load balancer with TLS; stateless API pods (state in PostgreSQL / checkpoint store).
* Managed secrets (External Secrets / cloud KMS), OIDC SSO, WAF.
* High availability: multi-AZ PostgreSQL with PITR backups; Redis HA; ≥ 3 API replicas with PodDisruptionBudgets.
* Disaster recovery: documented RPO/RTO, restore drills, infrastructure as code (`infrastructure/kubernetes/` is a
  starting point — **not verified against a cluster**).
* Alerting from `infrastructure/monitoring/alerts.yml` routed to on-call.
* Capacity: re-run the load script per release; scale on p95 latency and CPU, not on request count alone.

## Backups

* PostgreSQL: `pg_dump -Fc medaccess > medaccess-$(date +%F).dump` (local) / managed snapshots + PITR (cloud).
* Checkpoint store: back up alongside the database (it holds paused workflows awaiting approval).
* Restore drill: `pg_restore -d medaccess_restore …` then `alembic current` and `GET /api/v1/governance/audit/verify`.
