# Test evidence

Recorded 2026-11-11 on Linux x86_64 (4 vCPU), Python 3.13, Node 22.

## Backend: 113 passed (64 Operations + 35 Shield + 14 Assistant)

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
| test_shield_research.py | 14 | Real Opengrep/Bandit/Trivy runs, source-derived graph with provenance, every labelled site adjudicated correctly, false positives rejected by execution, reproducible isolated evidence, dedupe, incidents, patch regression and independent review, incremental re-ingest, agent records, tenant isolation |
| test_shield_control.py | 11 | Dual-engine (built-in + OPA) decisions, scope and symlink escape, roles, OPA missing/erroring fails closed, emergency stop, quotas, rate limits, HMAC plan signatures, visible partial scans |
| test_shield_containment.py | 4 | Seven synthetic agent scenarios, credential revocation, decoy key never leaked, namespace blocks egress without the guard, audit |
| test_shield_mcp_adversarial.py | 5 | Server manifest pinning and drift revocation, emergency revoke, instructions hidden in target source, hostile tool output, deny-by-default |
| test_assistant.py | 14 | Every starter and reachable follow-up answers in the contract; grounding vs stored data; free-text routing incl. report-trigger regression; memory; page context; user/tenant privacy; injection; redaction; validation; Shield focus |
| test_shield_evaluation.py | 1 | Three pipelines scored on the labelled corpus; LLM-only recorded as not run |

Run with:

```bash
cd florome/backend && pytest
```

## Frontend: 19 passed, typecheck clean, production build OK

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

## Shield measurements (LedgerLite, 2026-11-20)

| Pipeline | Found (of 5) | False alarms | Missed | Precision | Recall |
|---|---|---|---|---|---|
| Scanners only | 4 | 2 (`echo`, a module-level import) | 1 (`get_invoice` access control) | 0.667 | 0.8 |
| Code graph, no lab | 5 | 0 | 0 | 1.0 | 1.0 |
| Graph + lab (hybrid) | 5 | 0 | 0 | 1.0 | 1.0 |
| LLM only | not run | | | | |

Scan 4.4 s; scan + 22 isolated lab runs 13.7 s; 5/5 template patches blocked the exploit in 2/2 retests and passed functional checks (5.2 s). Containment: violations stopped in 32-41 ms; the infinite loop was killed by RLIMIT_CPU at 3.0 s. Sample size is 9 labelled sites written by the same team: a regression benchmark, not a real-world claim.

## Assistant browser review (2026-11-20)

Playwright drove the dock on RCA, FinOps, Shield (dark), Governance (dark) and a 390×844 phone viewport: starters, follow-ups, free text, the honest fallback, a selected Shield finding and a page brief, with no page errors. Two defects found and fixed: the RCA page defaulted to a Shield incident while the assistant answered about the outage (the page now defaults to the latest operational incident and writes it to the URL), and answer text was cut mid-word (word-boundary truncation; evidence links now show record summaries instead of IDs).
