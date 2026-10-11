# Status matrix

Legend: **Implemented**: working code with tests. **Simulated**: works, but stands in for a real system and is
labelled in the UI. **Optional**: implemented, off by default. **Unconfigured**: interface exists and fails loudly
until real access is supplied. **Planned**: documented, not built.

| Capability | Status | Evidence / notes |
|---|---|---|
| BR-101 vertical slice (requirement → rollback) | Implemented | `tests/test_journey.py`, `frontend/e2e/journey.spec.ts` |
| 17-state lifecycle, permitted transitions, backend prerequisites | Implemented | `app/lifecycle/state_machine.py`; every legal and listed illegal transition tested |
| Requirements agent: ambiguity detection, versioned requirements, acceptance criteria | Implemented (deterministic rules) | 8 ambiguity types; criteria map to gates |
| Configurable synthetic clarifications | Implemented (demo only) | `data/synthetic/demo_clarifications.json`; refused in production mode |
| Evidence agent: cited, validated, outdated/conflict and injection flags, unknown claims | Implemented | Lexical BM25; authorization filter applied before scoring |
| Embedding retrieval (pgvector) | Unconfigured | Mode is shown as such; no adapter |
| Impact agent | Implemented | System map is a fictional fixture |
| Development agent: plan, diff analysis, traceability, risks | Implemented | Diffs are fixture revisions; nothing is executed |
| Isolated build workspace / CI for candidates | Unconfigured | `connectors/interfaces.py` (`ci`, `git`) |
| Evaluation: paired top-1/top-3, abstention, coverage, conditional accuracy, Wilson, paired bootstrap, family confusion | Implemented | `app/evaluation/metrics.py` with unit tests |
| Beauty predictions | **Simulated** (synthetic fixtures) | Not computer-vision inference; no training occurred |
| Real prediction adapter | Unconfigured | Raises `integration_unavailable` (tested) |
| Policy engine PASS/FAIL/INCONCLUSIVE, gate owners, evidence | Implemented | `policies/release-policy-v2.1.json` (illustrative thresholds) |
| Privacy and authorization control tests | Implemented | Executed during every evaluation |
| Reviews, release approval, binding, expiry, single use, replay prevention, invalidation, revalidation | Implemented | `tests/test_release_guards.py` |
| Separation of duties (author ≠ code reviewer ≠ release approver; rollback requester ≠ approver) | Implemented | Server-side checks |
| Rollout 5/25/100% | **Simulated** | Prototype stage settings; no traffic |
| Monitoring observations and reference labels | **Simulated** | Seeded; `monitoring/simulator.py` documents its parameters |
| Seeded runtime defect (DEV-T3 lighting-map entry) and investigation | Implemented on simulated data | Investigation cites a configuration diff and states its caveats |
| Rollback with compatibility check; failed rollback path | Implemented (simulated execution) | Tested |
| Automated production rollback | Planned (needs a separate policy decision) | Not built, on purpose |
| Audit trail (append-only, hash chain) and traceability; exportable report | Implemented | Tamper detection tested |
| Copilot conversation | Implemented (deterministic intents over persisted state) | Status, next steps, blockers, worst cells, evidence lookup |
| Live LLM summaries (Anthropic) | Optional | `LLM_MODE=live` + key; schema-validated; contradiction filter; token budget; usage and cost recorded |
| Telemetry: latency, invocations, tool calls, tokens, cost (dated prices) | Implemented | Zero tokens and cost in deterministic mode (real zeros, not fabricated) |
| Process metrics with definitions | Implemented | Synthetic records only; see METRICS.md |
| Tenancy isolation | Implemented | Scoped getters; cross-tenant requests return 404 |
| Demo persona selector | Implemented (demo only) | Disabled in production mode (tested) |
| SSO / identity | Unconfigured | Production mode returns 401 `identity_unconfigured` |
| Image sandbox: consent, purpose, retention, validation, metadata stripping, deletion report | Optional (off by default) | `IMAGE_SANDBOX_ENABLED=true`; private local storage; no inference |
| Object storage, signed URLs, backup expiry automation | Planned (design in PRODUCTION_ARCHITECTURE.md) | — |
| Docker Compose (PostgreSQL), migrations, seed, reset | Implemented | Verified build, start, and persistence across restart |
| CI: backend tests, typecheck/build, e2e, secret scan, dependency audit, container scan | Implemented (workflow file) | Not yet run on GitHub at time of writing |
| Scenarios: lipstick AR, hair colour, recommendations, skincare guardrails, provider migration | Planned (backlog contracts) | Listed in the UI as backlog, not working |
| Photo deletion scenario | Partial | Sandbox deletion only |
