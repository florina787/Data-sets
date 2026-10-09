# Implementation status

Last updated: 2026-10-09.

## Completed

- [x] Deterministic commerce rules: eligibility, recompute, province, DST-safe window, no stacking, once per authenticated customer per campaign, reservation at order creation, idempotent checkout, mock payment failure handling, cancellation and allocated partial refunds
- [x] Storefront revisions v1.0 → v1.2 as stage trees with generated patches and a sync check
- [x] Protected acceptance suite (29 tests) tagged with acceptance criteria and regression IDs, with a JSON evidence report
- [x] Workflow persistence: briefs, clarifications, versioned requirement sets, ACs, designs, change sets, test runs and results, static checks, findings, releases, approvals, deployments, incidents, evidence, audit, activity
- [x] Run and release state machines with rejected transitions audited
- [x] Isolated patch and test runner: git worktrees, patch validation, `git apply`, sandboxed pytest, ruff with platform policy, AST scan
- [x] LangGraph delivery and incident flows: typed state, SQLite checkpoints, interrupts at human gates, pause, step mode, crash resume, bounded repair, recursion and tool limits
- [x] Release gates G1–G7 for exact revisions; approval bound to SHA and manifest hash; separate deployment authorization
- [x] Local demo accounts with server-side permissions
- [x] Real local deployment (process manager, PID file, port-collision check, health check, lifecycle) and rollback to last-known-good
- [x] Inventory simulator, demo fault injection, telemetry ingest and queries, synthetic traffic
- [x] Incident analysis with evidence and hypotheses kept apart, scripted-fault disclaimer, REQ-9 proposal, reproduction on the released revision, repair release, recovery verification
- [x] Control-room UI: overview, brief intake, delivery board, requirements and traceability, engineering diff, quality, release center, incidents, templates, evidence and audit
- [x] Storefront UI: catalog, cart, province, customer fixture, discount codes, free unit, mock checkout, order result, cancel and return
- [x] Guided demo (13 checked steps) with Run, Pause, Continue and Reset
- [x] Local document retrieval with version and section references; gaps surfaced
- [x] Tests: 23 backend, 2 Playwright end-to-end; screenshots reviewed
- [x] Documentation: README, architecture and traceability diagrams, agent and tool contracts, scenario guide, security, test results, production gaps, LinkedIn script and post

## Partially completed

- [~] **LIVE mode.** The Brief Analyst and Requirements Agent call Anthropic through `messages.parse` with Pydantic validation, a call budget and a timeout. Missing credentials fail visibly (tested). Not exercised against the real API, because no key was available. LIVE runs stop before implementation: live requirements are not linked to the protected test suite, and live patches are not executed.
- [~] **Execution sandbox.** Restricted subprocess, not a container, because no container runtime was available. Mitigated by executing only trusted seeded patches.
- [~] **Design Agent and Requirements Agent in DEMO mode** output seeded templates (labelled as fixtures) rather than generating content.
- [~] **Accessibility.** Semantic landmarks, labelled controls, focus-visible styles, reduced-motion support and accessible chart text. Not audited with screen readers.

## Not implemented

- [ ] Optional contextual chat that explains an artifact (the prompt marks it optional)
- [ ] The five secondary scenarios as working applications. They are templates and previews only, and say so in the UI.
- [ ] Mixed-price promotion behaviour (documented simplification)
- [ ] Brief editing and re-versioning after submission (the schema supports versions; there is no UI or API for v2 briefs)
- [ ] Windows support for the process manager (POSIX process groups)
