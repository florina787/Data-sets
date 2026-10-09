# Agent and tool contracts

Agents are LangGraph nodes (`backend/app/agents/nodes.py`). In DEMO mode they are deterministic. Every visible output is a concise activity summary with a provenance label. No model chain-of-thought is stored or shown.

## Agents

| Agent | Inputs | Outputs (persisted) | DEMO behaviour | LIVE behaviour | Tools |
|---|---|---|---|---|---|
| **Brief Analyst** | Brief vN (untrusted text) | Brief analysis (objective, constraints, stakeholders); clarifications with retrieved evidence and policy-gap flags | Deterministic 9-dimension promotion checklist: a dimension is ambiguous when the brief invokes it but contains none of its resolving terms. Evidence comes from BM25 retrieval. | `LiveBriefAnalysis` schema via `messages.parse`, validated with Pydantic | retrieval |
| **Requirements Agent** | Resolved decisions, brief | Requirement set vN (requirements, measurable ACs, decision links, test plan file list) | Seeded template (`fixtures/seed/flagship.json`), labelled as a scripted fixture | `LiveRequirementSet`, validated, flagged as not linked to executable tests | requirement persistence |
| **Design Agent** | Approved requirements | Component and API changes, dependencies, rationale | Seeded design (fixture) | not used | – |
| **Implementation Agent** | Design, last-known-good revision | Change set (patch hash, base and candidate revision, files, real diff) | Applies `01-campaign-implementation.patch` (**Fixture proposal**) to the run's worktree and commits | **Disabled**: live patches are not executed without a container sandbox | create workspace, validate/apply patch, diff |
| **QA Agent** | Approved test plan (frozen hashes), revision | Test run (exit code, captured output, per-test outcome with AC and REG IDs) | Runs the protected suite against the exported revision | same | test execution |
| **Repair Agent** | Failing regression IDs | Repair change set | Maps REG-001 → patch 02 and REG-002 → patch 03; bounded to 1 attempt; then re-runs the **unchanged** tests | – | apply patch, test execution |
| **Review Agent** | Revision | Static-check records; blocking findings when checks fail | ruff with the platform-owned policy, plus an AST forbidden-call scan. Interprets results; does not certify | same | static checks |
| **Release Coordinator** | Run, revision | Release manifest and SHA-256; gate evaluation; status awaiting-approval or blocked | Deterministic gates G1–G7 | same | manifest generation |
| **Incident Analyst** | Telemetry since deploy, release diff, fault-control state, standards | Incident with separate evidence and hypotheses, proposed actions, REQ-9 proposal | Threshold rules (checkout 5xx rate ≥ 20 % or p95 ≥ 3 s); diff scan for `timeout=None`; ENG-INV §4 retrieval; scripted-fault disclaimer | not used | telemetry query, diff, retrieval |

Human gates (interrupts): clarification decisions (marketing or product owner), requirement-set approval (product owner), release approval and deploy (release approver), fault cleared (engineer).

## Tools

Agents never get a shell. Each tool builds a **fixed argv** from validated, typed arguments (`backend/app/tools/runner.py`):

| Tool | Request | Validation | Execution | Result |
|---|---|---|---|---|
| Document retrieval | query string | – | in-process BM25 over `## n.` sections | `ref` (`DOC v<version> §n`), heading, excerpt, score |
| Requirement persistence | requirement set | idempotent on (run, version) | SQLite | set version, frozen test-plan hashes on approval |
| Scoped source reading | run ID, relative path | run ID regex; rejects absolute paths, `..`, `.git`; resolved path must stay in the worktree | file read (200 kB cap) | text |
| Workspace creation | run ID, base SHA | 40-hex SHA | `git worktree add -B candidate/<run>` | path |
| Patch validation and application | fixture patch name (`NN-name.patch`) | only text edits under `storefront/`; no binary, mode change, symlink, rename, `..` or absolute paths; `git apply --check` | `git apply --index`, `git commit` | revision, base, SHA-256 of patch, files, `git diff base..rev` |
| Test execution | revision, approved plan | test files hash-checked against the frozen plan; only plan files plus `conftest.py` are copied from the fixture store | `python -m pytest` in `var/test-runs/<id>`, `PYTHONPATH=<exported revision>`, scrubbed env, own HOME, RLIMIT_CPU/FSIZE, 180 s timeout, 200 kB output cap | exit code, status, per-test JSON report |
| Static checks | revision | – | `ruff check --config fixtures/policy/ruff.toml` plus AST scan | exit codes, findings |
| Release manifest | run, revision | – | canonical JSON, then SHA-256 | manifest, hash |
| Local deployment | release, revision | approval bound to SHA and hash; gates re-evaluated | stop previous managed process; port must be free; `uvicorn storefront.main:create_app` from `var/releases/<sha>`; `/health` must report the SHA | deployment record with lifecycle events |
| Rollback | – | release-approver role; a different last-known-good release must exist | redeploys the LKG commit | deployment record |
| Telemetry query | time window, revision | – | JSONL → SQLite ingest; percentile math | request, checkout and dependency statistics |
| Synthetic traffic | journeys (1–10) | – | real HTTP journeys against the storefront | outcomes, latencies, cart preservation |
| Fault control (demo) | active flag | engineer role; demo only | sets the simulator to wait `FOODLAUNCH_FAULT_DELAY_S` and then return 504 | audit and evidence labelled *Injected fault* |

The executable allow-list is the platform's own Python interpreter and `git`. Working directories must resolve inside `var/`. Environment variables whose names contain KEY, TOKEN or SECRET are refused for tool processes, and `ANTHROPIC_API_KEY` is never inherited (this is tested).

## Untrusted input

Briefs, documents and code comments are data. Retrieved text is quoted as evidence, and LIVE prompts wrap it in `<untrusted_brief>` tags with an instruction not to follow embedded instructions. Model output is used only after schema validation, and live-generated code is never executed.
