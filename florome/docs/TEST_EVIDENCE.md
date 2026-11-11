# Test evidence

Recorded 2026-11-11 on Linux x86_64 (4 vCPU), Python 3.13, Node 22.

## Backend: 64 passed

| File | Tests | Covers |
|---|---|---|
| test_rca_engine.py | 9 | Classification rules, competing explanations, challenger downgrade, no numeric confidence |
| test_e2e.py | 3 | Full 10-step lifecycle through the API; learning (similar incidents); step-progress persistence regression |
| test_approvals.py | 7 | Roles, SoD, hash binding, replay, rejection, expiry, tampered plan |
| test_execution.py | 7 | Retry, permanent failure + resume, timeout, concurrency, idempotency, causal order, validation |
| test_governance.py | 9 | Modes, emergency stop, budgets, live/simulated separation, policy validation, inconclusive → no action |
| test_mcp.py | 7 | Real stdio discovery and invocation, argument validation, write denial, RBAC, allow-list, hostile server (quarantine, redaction), schema drift, env isolation |
| test_connectors.py | 9 | Contract, action validation, GitHub REST against a mocked transport, error classification, token never leaked |
| test_security.py | 7 | Authn, redaction, injection in logs, audit tamper, evidence integrity, RBAC matrix, measured metrics |
| test_tenant_isolation.py | 4 | Cross-tenant reads/writes return 404, scoped lists, per-tenant audit chains, evidence pagination |
| test_architecture_adapter.py | 2 | Project B engine reused unchanged (skipped if its deps are absent) |

Run with:

```bash
cd florome/backend && pytest
```

## Frontend: 12 passed, typecheck clean, production build OK

`src/tests/app.test.tsx` covers navigation, the demo banner, KPIs, honest copilot-layer status, error and retry states, the topology layout and incident roles, constellation filtering and dashed contradictions, timeline markers, the approval request (hash plus a fresh 32-hex nonce plus the role token), surfacing of SoD denials, required plan fields, and the rule that planned platforms are never shown as verified.

## Browser end to end

`docs/screenshots/*.png` were captured by Playwright driving the real UI against the real API. The flow ran RCA, plan, approval as the approver, execution as the operator, MCP discovery and invocation, and visits to every page, with no page errors. This capture found a real bug: step statuses were not persisted after the first step. It is now fixed and covered by `test_step_progress_is_persisted_not_just_in_memory`.

## Measured performance

`python scripts/benchmark.py`: 10 runs, SQLite, in-process, sandbox connector.

| Workflow | Median |
|---|---|
| RCA (collect 18 evidence items + analyse 9 hypotheses + challenge) | 76.1 ms |
| Plan + policy | 46.6 ms |
| Execute 5 steps + verify + validate | 119.2 ms |
| Detect → validated total | 267.7 ms (max 364.1 ms) |
| Python peak traced memory | 19.2 MB |

These numbers come from a local dev box with a simulated target. Real connectors will be dominated by provider API latency.

## Pre-existing projects

Project A: 163 passed, 2 failed (pre-existing; see the audit). Project B: 76 passed.
