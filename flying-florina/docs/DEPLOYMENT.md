# Deployment and offline installation

Flying Florina 3.0 supports three modes. All of them keep the model on loopback (policy POL-008) and need no paid service.

| Mode | What | Status in this repository |
|---|---|---|
| A — Local development | `make demo` / two terminals on a workstation | Verified (tests, e2e, benchmarks run this way) |
| B — Docker Compose | `docker-compose.yml`: backend + frontend, optional in-process Qwen | `docker compose config` validated; images **not built here** (no Docker daemon in the build container) |
| C — Kubernetes reference | `deploy/k8s/` (namespace, config, secret example, PVCs, backend, frontend, ingress gateway, network policies, optional Qwen sidecar) | YAML parsed and checked for probes/resources; **not applied to a live cluster**; not production-ready without validation |

## Mode A — local (recommended for the demo)
See README quick start. Defaults: `DEMO_MODE=true`, `OFFLINE_MODE=true`, `LLM_ENABLED=on` (your local Qwen is required; use `auto` to
run without it). Data in `backend/data/` (git-ignored). First start fits the forecasting models (~11 s on 4 CPUs) and caches the
results in the data folder.

## Offline installation strategy
1. On a connected machine with the same OS/arch:
   ```bash
   cd flying-florina/backend && python3 -m venv .venv && .venv/bin/pip download -r requirements.txt -d ../offline/wheels
   cd ../frontend && npm ci && tar czf ../offline/node_modules.tgz node_modules
   ```
2. Copy the repository and `offline/` to the target machine.
3. Install without network:
   ```bash
   cd flying-florina/backend && python3 -m venv .venv && .venv/bin/pip install --no-index --find-links ../offline/wheels -r requirements.txt
   cd ../frontend && tar xzf ../offline/node_modules.tgz
   ```
4. `make demo` (or the two commands in the README). Verify with `make offline` and `make smoke`.

For Playwright, download the browser once (`npx playwright install chromium`) and copy `~/.cache/ms-playwright`.

## Mode B — Docker Compose
```bash
docker compose build            # while connected
docker save -o ff-images.tar flying-florina-backend flying-florina-frontend
docker load -i ff-images.tar    # on the offline host
docker compose up               # UI http://127.0.0.1:4173, API :8000
```
With your existing Qwen file (in-process llama.cpp; the model directory is mounted read-only and nothing is downloaded):
```bash
QWEN_MODEL_DIR=/path/to/models FF_QWEN_MODEL_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf INSTALL_LLAMA=true docker compose up --build
```
Ports are bound to 127.0.0.1. The backend runs read-only as an unprivileged user with resource limits, a `/ready` health check and a
graceful-shutdown window; the frontend waits for the backend to be healthy.

## Mode C — Kubernetes reference
```bash
kubectl apply -k deploy/k8s                       # after creating ff-secrets from your secrets manager and loading images
# optional: Ollama as a same-pod sidecar instead of in-process llama.cpp (keeps the model on 127.0.0.1)
kubectl -n flying-florina patch deployment ff-backend --patch-file deploy/k8s/60-qwen-sidecar.optional.yaml
```
* **One backend replica, `Recreate` strategy, ReadWriteOnce volume.** SQLite is single-writer: never run several replicas against
  the same database file, and never put it on shared network storage between writers.
* Requests/limits, startup/readiness (`/ready`: database + migrations)/liveness (`/health`) probes, `preStop` delay and a 30 s grace
  period, non-root, read-only root filesystem, dropped capabilities, no service-account token.
* Secrets: `FF_SESSION_SECRET` from `ff-secrets` (the file in the repo is a placeholder).
* Network policies: default deny; ingress controller → UI/API; UI → API; **no egress for the backend**.
* The ingress is the API gateway: `/api`, `/ready` → backend; everything else → UI. Observability: JSON request logs with request IDs,
  `/api/llm/metrics`, `/api/harness/control-tower`; ship logs with your cluster's collector.

## PostgreSQL migration path (for horizontal scaling)
1. Keep the schema and the numbered migrations; port `db.SCHEMA` + `migrations.MIGRATIONS` to PostgreSQL DDL (FTS5 tables →
   `tsvector` columns with GIN indexes).
2. Replace `app/core/db.py` connection handling with a pooled driver (e.g. psycopg 3) behind the same `query/execute/session` helpers.
3. Move the hash-chained audit append into a serialisable transaction (or an advisory lock) so concurrent writers keep the chain.
4. Move the forecast result cache from a local file to a table or object store; fit models in one worker and publish results.
5. Only then raise backend replicas above 1 and switch the Deployment strategy to RollingUpdate.

## Local Qwen
Flying Florina reuses the Qwen model already on your machine (see [QWEN_LOCAL_LLM.md](QWEN_LOCAL_LLM.md) and
[QWEN_INTEGRATION.md](QWEN_INTEGRATION.md)). Non-loopback model URLs are denied (POL-008). Qwen explains verified results; it never
decides, approves or produces forecast numbers.

## Production (out of scope)
Enterprise IdP + MFA, managed PostgreSQL with encryption, WORM/externally anchored audit, container sandboxing for
generated-code tests, reverse proxy with rate limiting/WAF, secrets manager, SBOM and vulnerability scanning,
and a formal security and compliance assessment. See SECURITY_LIMITATIONS.md.
