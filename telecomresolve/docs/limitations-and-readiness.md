# Known limitations, production-readiness checklist and roadmap

## What was verified in this build (2026-10-11)

| Check | Result |
|---|---|
| Backend tests, SQLite | 60 passed |
| Backend tests, PostgreSQL 16 (local) | 59 passed (migration test is SQLite-only and was deselected) |
| Fresh-venv install from pinned `requirements-dev.txt` | Installed; 60 passed |
| Alembic `upgrade head` matches ORM models | Passed (test) |
| Container entrypoint sequence on PostgreSQL (migrate → seed → serve → investigate) | Passed manually |
| Frontend `tsc`, Vitest (4 tests), production build | Passed |
| Playwright e2e in Chromium (4 journeys) | Passed |
| `npm audit --omit=dev` | 0 vulnerabilities |
| Labelled evaluation | 133/133 checks; all 4 release gates pass |

**Not verified:** Docker image builds (Docker Hub returned HTTP 429 for base images), the GitHub Actions workflow
(not run here), `pip-audit` and gitleaks (configured in CI only), LIVE/HYBRID generation against the real
Anthropic API (no key available; covered only by scripted fake-provider tests), pgvector (extension not installed
locally), and a full backup/restore drill.

## Known limitations

1. **Diagnosis is rule-based in DEMO mode** and the rules and evaluation labels were written by the same author.
   The 11/11 diagnosis result shows the workflow behaves as designed on its own scenarios; it says nothing about
   accuracy on real cases.
2. **LIVE mode is untested against a real model.** Prompt quality, latency, cost and refusal behaviour are
   unmeasured. Model-quality thresholds should be set after a baseline on independently labelled data.
3. **No semantic retrieval.** BM25 over 9 short documents; pgvector is provisioned in Compose but unused.
4. **No SSO**; production mode refuses requests by design.
5. **Simulated connectors and simulated time.** Post-action telemetry is generated from per-case profiles and
   fast-forwarded; dispatch "appointments" are records in a local table.
6. **Pattern-based injection detection** (see security notes).
7. **Single-process concurrency controls.** Compare-and-set transitions and unique constraints are enforced in the
   database, but the background job runner is an in-process thread pool, not a durable queue.
8. **Audit is tamper-evident only** (hash chain inside the same database).
9. **Clarifications do not create measurements**: in C-1004 the case stays in NEEDS_INFORMATION until a fresh line
   test is possible, which the simulation never provides.
10. **Small topology and catalog** — one product (home internet), five fault categories, eight actions.
11. **Time zones**: customer-reported times ("around 8pm") are not converted or matched to sample hours.
12. The `evaluation_runs` table is defined but unused; reports are files under `evaluation/results/`.

## Production-readiness checklist

| # | Missing capability | Why it matters | Done when |
|---|---|---|---|
| 1 | SSO (OIDC/SAML) and IdP group → role mapping | Personas are not authentication | Token verification with issuer/audience/expiry/key rotation; production mode serves requests |
| 2 | Real connectors behind service identities | All data is synthetic | Per-connector contracts, least-privilege credentials, contract tests against sandboxes |
| 3 | Durable job queue and workers | Thread pool loses queued (not running) jobs on restart | Queue-backed workers, visibility timeouts, dead-letter handling |
| 4 | Immutable audit sink | Same-DB hash chain can be rewritten wholesale | Events mirrored to WORM storage; chain heads anchored |
| 5 | LIVE-mode evaluation | Model quality unmeasured | Opt-in, budget-limited eval runs recording dataset, model id, prompts, config, date; thresholds set from baseline |
| 6 | Independent labels | Labels share an author with the rules | ≥ 2 domain reviewers, disagreement resolution, larger realistic case set |
| 7 | Semantic retrieval with region-pinned embeddings | Lexical search misses paraphrase | pgvector index, hybrid ranking, re-index on document version change |
| 8 | Data residency verification | Sovereignty claims need end-to-end evidence | Every component (inference, embeddings, DB, logs, backups, support access) verified for the required region |
| 9 | Secure session handling | Bearer tokens in sessionStorage; SSE token in query | HttpOnly cookies/BFF, CSRF protection, short-lived stream tokens |
| 10 | Rate limits, request size limits, WAF | Abuse protection | Configured and load-tested |
| 11 | Field-level encryption and retention jobs | Privacy obligations | Encrypted contact fields; retention/deletion jobs with audit |
| 12 | Backup/restore drill | Recovery not rehearsed | Documented RPO/RTO met in a drill |
| 13 | Observability stack | Only structured logs + audit today | Traces, metrics, alerting on escalations, connector errors, approval waits, budget exhaustion |
| 14 | Load and concurrency testing | Untested beyond unit-level races | Target throughput with multiple workers and replicas |
| 15 | Accessibility audit | Built to WCAG intent, not audited | Screen-reader and contrast audit with fixes |

## Roadmap

- **Phase 2 (partly done):** realistic case variations ✔ (13 cases), supervisor review ✔, optional live LLM mode
  ✔ (untested against a real model), comparative evaluation ✔ (heuristic baseline only), incident correlation
  across cases — *not done* (peer-health aggregation exists; cross-case clustering does not).
- **Phase 3 (stubs only):** enterprise connector interfaces ✔ as `UNCONFIGURED` stubs; deployment design ✔
  ([architecture.md](architecture.md)). No real system connections — they stay disabled until credentials,
  contracts, data access and action authorization are supplied.
- **Future extensions (not built):** mobile connectivity, provisioning failures, appointment coordination,
  billing disputes, change-impact investigation.
