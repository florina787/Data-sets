# FloPilot architecture

## Overview

```
 Browser (React + TS)                         FastAPI service (Python)                           Storage
┌───────────────────────┐   /api (JSON)   ┌──────────────────────────────────────────────┐   ┌──────────────────────┐
│ Header / Activity      │───────────────▶│ api/routes      auth (demo tokens, roles)    │   │ blobs/  immutable    │
│ Left: workbooks,sheets │                │   │                                          │   │  original.<ext>,     │
│   data quality, chats  │                │   ▼                                          │   │  v1.xlsx, v2.xlsx …  │
│ Center: virtual grid,  │◀── polling ────│ agent/supervisor ── background run thread    │   │ (atomic temp+rename) │
│   formula bar, tabs,   │   /runs/{id}   │   │  planner (deterministic)  │ llm_agent     │   ├──────────────────────┤
│   before/after preview │                │   ▼                          ▼ (optional)     │   │ SQLite metadata      │
│ Right: FloPilot panel  │                │ harness/runtime: typed tools, permissions,   │──▶│ workbooks, versions, │
│   answers, sources,    │                │   timeouts, retries, budgets, cancellation,  │   │ operations,approvals,│
│   proposals, approve   │                │   checkpoints, audit                         │   │ runs, conversations, │
└───────────────────────┘                │   │                                          │   │ messages, audit      │
                                           │   ▼                                          │   └──────────────────────┘
                                           │ workbook/: ingest, model, profile, quality,  │
                                           │   query, formulas, evaluator, changes,       │──▶ LibreOffice (optional,
                                           │   cleaning, validate, fidelity, cache_values │    verification only)
                                           │ services/: workbooks (versions), operations  │
                                           └──────────────────────────────────────────────┘
```

Workbook operations are pure Python modules with no dependency on any LLM provider. The LLM (when configured) can only call registered tools.

## Request lifecycle and run state

Every chat request creates a **run** and executes on a background worker. The UI polls `GET /api/runs/{id}`.

```
RECEIVED → INSPECTING → PLANNING → EXECUTING_READS → COMPLETED                        (read-only)
                              └──→ COMPLETED (clarification / info)
                                          └→ PREVIEW_READY → AWAITING_APPROVAL → APPLYING → VALIDATING → COMPLETED
                                                                       │                        └─→ ROLLED_BACK (validation failed)
any non-terminal ──→ FAILED | CANCELLED
```

Transitions are validated (`harness/state.py`) and written to the database after every step (checkpoints). On startup, runs left in a non-terminal state by a crash are marked `FAILED` ("interrupted"); because versions are published atomically, an interrupted apply never leaves a partial version.

1. **INSPECTING** – load the cached profile for the current immutable version (`inspect_workbook` tool), refresh conversation context if the version changed (earlier results marked out of date, business rules revalidated).
2. **PLANNING** – the deterministic planner maps the request to a bounded plan of tool calls, or returns a clarification. If it cannot classify the request and an LLM is configured, the LLM loop plans with the same tools.
3. **EXECUTING_READS** – tools run through the harness. Proposal tools create `PROPOSED` operations; nothing is applied.
4. **AWAITING_APPROVAL** – the user approves a specific operation. The approval request carries the operation id, the expected workbook version and the change-set hash.
5. **APPLYING / VALIDATING** – the change set is re-applied to the immutable base version, validated, and only then published as the next version.

## Harness

`harness/runtime.py` wraps every tool call:

| Concern | Implementation |
|---|---|
| Registry | `ToolSpec(name, description, input_model, permission, handler, role, timeout_s, retries, idempotent)` |
| Typed inputs/outputs | Pydantic models with `extra="forbid"`; outputs are JSON dicts with a `kind` |
| Validation | Inputs validated before execution; unknown fields rejected |
| Permissions | `read`, `propose` are model-invocable; `mutate`, `export`, `restore` are user-only (policy controller refuses model calls). Role checks: viewer = read; analyst = read/propose/approve/export/restore; admin = + audit |
| Timeouts | Per tool (default 30 s) via a worker pool; timed-out results are discarded |
| Retries | Only for idempotent tools and errors marked retryable; writes are never retried blindly |
| Budgets | Max steps (8), max tokens (60k) and max estimated cost ($0.50) per run |
| Cancellation | Cooperative: checked between steps and inside long tools; cancelling an awaiting run withdraws its proposals |
| Logs / checkpoints | Each step (state, tool, role, duration, status, bounded argument summary) appended to the run |
| Output bounds | Lists in tool output capped (default 50 items) before reaching the model or UI |
| Final validation | For LLM-written text, every number must appear in a tool result (`agent/grounding.py`), otherwise the text is replaced by deterministic narration |

## Roles

Logical roles are modules inside one orchestrated workflow (multiple autonomous agents would add cost and nondeterminism without a measured benefit):

| Role | Where | Responsibility |
|---|---|---|
| Supervisor | `agent/supervisor.py`, `agent/planner.py` | Classify request, build bounded plan, drive run state, compose answer |
| Workbook analyst | `workbook/query.py`, tools `calculate_aggregate`, `time_series`, … | Structure, deterministic analytics |
| Formula specialist | `workbook/formulas.py`, `evaluator.py`, `recalc.py` | Explain, diagnose, consistency, propose formulas |
| Data-quality specialist | `workbook/quality.py`, `cleaning.py` | Detect issues, propose transformations |
| Visualization specialist | `harness/viz.py`, report sheets in `changes.py` | Chart choice and validated chart data |
| Validator | `workbook/validate.py`, `fidelity.py`, `cache_values.py` | Gates before publishing a version |
| Policy controller | `harness/runtime.py` (`call`), `auth.py` | Permissions, approval-only mutations |

Requests only touch the roles their plan needs.

## Tools

| Tool | Permission | Role |
|---|---|---|
| `inspect_workbook`, `profile_sheet`, `read_range`, `query_table` | read | workbook analyst |
| `calculate_aggregate`, `time_series`, `period_change`, `compare_measures`, `correlation` | read | workbook analyst |
| `missing_by_column`, `find_duplicates`, `find_outliers` | read | data quality |
| `explain_formula`, `diagnose_formula`, `check_formula_consistency` | read | formula specialist |
| `propose_formula`, `propose_formula_fix` | propose | formula specialist |
| `propose_cleaning` (trim, normalize categories, standardize dates, convert text numbers, fill blanks, flag/remove duplicates, flag outliers) | propose | data quality |
| `create_chart`, `histogram` | read | visualization |
| `propose_report_sheet` | propose | visualization |
| `preview_changes`, `validate_workbook`, `propose_restore` | read / propose | validator |
| `apply_approved_changes`, `export_workbook`, `restore_version` | mutate / export / restore | user-only (applied through the approval / download endpoints) |

## Contracts (schema_version "1.0")

Published at `GET /api/schemas` (`app/schemas.py`): **Plan**, **Operation**, **Approval**, **Error**, **Result**, **CellChange**, **Source**, **ChatRequest**.

An **operation** (change set) contains: operation id, workbook id and base version, action type, target sheet and range, parameters (`details`, including the builder used so it can be re-prepared), preconditions, every affected cell with its before/after state, structural edits (row deletion, new sheet), flags (overwrites, formula replacements, clears, deletions, added sheet), affected-cell count, approval requirement, validation rules, status (`PROPOSED → APPLYING → APPLIED | FAILED | REJECTED | STALE`) and the resulting version.

## Grounded answers

Numbers come only from `workbook/query.py` (and the formula/quality modules). Each result includes: rows/values, `method`, `filters`, `missing_treatment`, `excluded` counts (blank, text, numbers stored as text, errors), `warnings` (spelling variants, mixed currency formats, gaps) and `sources`. A **source** is `{workbook_id, version, sheet, range, header}` with a stable hash id. After a structural edit, sources in the conversation context are revalidated by header: relocated, or marked stale.

Deterministic narration (`agent/narrate.py`) writes text only from those values. In LLM mode the model's text is checked against tool outputs before it is shown.

## Mutations

1. A builder produces a concrete change set from the current immutable version.
2. **Dry run**: the change set is applied to a copy, validated, and the package inventory compared (measured fidelity). Formula results are previewed with the limited evaluator and, if LibreOffice is installed, recalculated for real.
3. The operation is stored as `PROPOSED` with its change-set hash.
4. **Approve**: the request must carry the operation id, the expected version and the hash; the operation is claimed atomically (`PROPOSED → APPLYING`), so two approvals cannot both apply it. An `Idempotency-Key` makes retries return the first result.
5. **Apply**: start from the base version bytes, check every cell still holds its “before” value, apply, refresh cached formula results, validate.
6. **Publish**: under a per-workbook lock, check the base version is still current, write the blob atomically (temp file + `os.replace`), insert the version row and bump `current_version` in one transaction.
7. If validation fails the candidate is discarded, the operation is `FAILED` and the run is `ROLLED_BACK`; the previous version stays current.

Validation gates (`workbook/validate.py`): reopens; no sheet removed; sheet names/order preserved (plus planned new sheet); only planned cells changed; no unplanned formula overwrites; every planned change present exactly; rows deleted exactly as planned; numeric column totals move only by the planned deltas; frozen panes, merged cells, filters, tables, data validation, conditional formats and column widths preserved per sheet; package features not lost unless acknowledged.

## Data model (SQLite → PostgreSQL)

`workspaces`, `users` (hashed demo tokens), `workbooks`, `versions` (storage key, sha256, kind: original / converted_from_csv / edit / restore), `operations`, `approvals`, `runs` (state, plan, steps, tokens, cost estimate, model, prompt version, cancel flag), `conversations` (scoped context), `messages`, `audit_events`.

## Library trade-offs

| Need | Choice | Why / trade-off |
|---|---|---|
| Read/write `.xlsx` | **openpyxl 3.1.5** | Pure Python, preserves values, formulas, styles, number formats, widths, merged cells, panes, filters, tables, defined names, validation and conditional formatting. It does **not** keep cached formula results on save, and drops or simplifies some features (pivot caches, slicers, sparklines, some charts/drawings). FloPilot measures this per edit instead of assuming. |
| Cached results after edits | **FloPilot evaluator + carry-over** (`cache_values.py`) | Restores `<v>` values so new versions read correctly without Excel; formulas outside the evaluator keep Excel’s saved value only when their inputs did not change; everything else is reported as uncalculated. `fullCalcOnLoad` is set so Excel recalculates on open. |
| Formula verification | **LibreOffice headless (optional)** | A real calculation engine, used only to verify; its output file is discarded (it would change fidelity). Functions it lacks show `#NAME?` and are reported as “cannot evaluate”. ~600 MB, so off by default in Docker. Alternatives considered: `formulas`/`pycel` (Python engines; partial function coverage, extra dependency weight). |
| Tabular analytics | Plain Python over detected tables | Small dependency surface, exact control of missing-data treatment; pandas would add ~40 MB for little gain at the current 500k-cell limit. |
| LLM | Anthropic Python SDK behind `LLMProvider` | Optional; manual tool loop so the harness controls permissions, budgets and approval. Other providers implement one method. |
| Frontend grid | Custom virtualised grid | Excel-like look, row virtualisation in 100-row blocks, no third-party grid licence. |
| Metadata | stdlib `sqlite3`, portable SQL | Zero setup; schema uses portable types for PostgreSQL migration. |

## Caching and cost

* Profiles and loaded models are cached per **immutable** `(workbook, version)`; a new version is a new key, so invalidation is automatic.
* The deterministic planner handles recognised requests with **zero model tokens**; the LLM is called only for requests it cannot classify, with a compact schema (column names, types, three samples per column) instead of the workbook.
* Tool outputs are bounded; token usage is measured from provider responses and shown with a clearly labelled cost **estimate** (configured per-token prices).

## Extension points (not implemented)

`app/extensions.py`: `WorkbookSource` (OneDrive/SharePoint via Microsoft Graph), `ExcelHostBridge` (Excel task-pane add-in), `DataDictionary`, `CalculationRules`; `auth.IdentityProvider` (OIDC / Entra ID); `storage.Storage` (S3 / Azure Blob); `llm.providers.LLMProvider`. None is connected in this build.
