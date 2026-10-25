# Implementation plan and environment inventory

## Environment inventory (build machine, 2026-10-24)

| Item | Value |
|---|---|
| OS | Linux 6.18 x86_64 container (glibc 2.39) |
| CPU / RAM | 4 vCPU / 15 GB, no GPU |
| Python | 3.13.17 (code is 3.11-compatible; f-string syntax checked by ruff `target-version=py311`) |
| Node / npm | 22.22.0 / 10.9.4 |
| Docker | 29.9.2 available (Compose files provided, not required) |
| Network | Package registries reachable for one-time setup; runtime verified offline |
| Existing repo | Monorepo of datasets and three unrelated demos (`convolens`, `enterprise-agentic-ai`, `lexguard`). Flying_Florina was added as a new self-contained folder; nothing existing was modified except a new CI workflow file |
| Brand assets | Not present (`/mnt/data` absent) → neutral placeholder, no likeness |

## Task board

### P0 – working vertical slice (done)
- [x] Seeded synthetic dataset (seed 20261024), offline startup, DEMO/OFFLINE defaults
- [x] Centered chat (Mission Control) with live execution timeline, session history, replay
- [x] Deterministic intent routing for the 10 sample questions + clarification
- [x] Real multi-agent maintenance flow (Graph 1) with parallel waves, retries, cancel, failure injection, checkpoints
- [x] Legacy X-Ray for SQL and OpenAPI (plus CSV, OData XML, event schema, ZIP)
- [x] Generated read-only API + MCP tool that runs and passes its own tests
- [x] Policy deny-before-execute, exfiltration denial with 0 tool executions
- [x] Dynamic charts from API data
- [x] Approval gate with separation of duties, expiry, idempotency, replay rejection
- [x] Hash-chained audit log + verifier + export
- [x] Tests (pytest, Vitest, Playwright, offline check), docs

### P1 – breadth (done unless noted)
- [x] 10 personas incl. guest and external-org guest
- [x] AOG recovery, parts intelligence, manufacturing quality, compliance evidence pages
- [x] Scenario simulator (deterministic + seeded Monte Carlo + sensitivity), executive studio with editable ROI
- [x] Export formats PDF/HTML/MD/CSV/JSON, workspace export, evidence manifest, audit packet
- [x] Security Test Lab (12 scenarios), kill switch, classification matrix, tool permissions
- [ ] PostgreSQL profile (planned)
- [ ] OPA/Rego integration (planned; Python engine is authoritative)

### P2 – polish
- [x] Light/dark mode, responsive layout, keyboard skip link, chart data tables for screen readers
- [x] Local demo MCP server with pinned tool discovery
- [ ] 3D engine visualization (not built)
- [ ] Local-LLM rephrasing (detection + policy gate exist; no rephrasing step wired in)
- [ ] Connector gallery/plugins (not built)
