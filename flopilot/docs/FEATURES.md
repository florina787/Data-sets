# Feature checklist

Status legend: **Implemented** (works and is tested) · **Partially implemented** (works with stated gaps) · **Demo only** (works for the demo/local setup, not production-grade) · **Not implemented**.

## A–C Product and journeys
| Feature | Status | Notes |
|---|---|---|
| Upload `.xlsx` / `.csv` | Implemented | Size, structure, zip-safety validation; original kept immutable |
| Explore sheets, tables, formulas, data quality | Implemented | Left panel, profile endpoint, grid |
| Plain-English questions with grounded answers | Implemented (demo planner) | Deterministic planner covers analysis/cleaning/formula/chart/restore intents; free-form questions need an LLM key |
| Generate / explain formulas | Implemented | Ratio, margin, difference, sum, product, conditional, date part, cross-sheet lookup, custom template; explanation of any formula |
| Clean and transform data | Implemented | Trim, normalize categories, standardize dates, convert text numbers, fill blanks (text columns), flag/remove duplicates, flag outliers |
| Summaries, charts, reports | Implemented | Web charts (bar, line, scatter, histogram, table); report sheet with native Excel chart; markdown analysis summary |
| Preview → approve → apply | Implemented | Diff, affected count, destructive flags, grid before/after |
| Download updated workbook | Implemented | Any version; CSV per sheet |
| Evidence and execution history | Implemented | Sources, method, assumptions; Activity drawer (versions, changes, runs with steps/tokens, audit trail) |
| Recover (restore version) | Implemented | Restore is itself an approved operation creating a new version |
| Loading / empty / error / retry / cancel / success states | Implemented | Retry for retryable errors; cancel button while running |
| Excel task-pane add-in | Not implemented | Interface only (`ExcelHostBridge`) |

## D–E Ingestion and fidelity
| Feature | Status | Notes |
|---|---|---|
| Detect sheets, used ranges, tables, headers | Implemented | Excel tables (ListObjects) preferred; header guess with confidence |
| Type inference, semantics (date/currency/%/id/category) | Implemented | Mixed-type and low-confidence flags |
| Missing values, duplicates, formula cells, errors | Implemented | |
| Merged cells, hidden sheets/rows/columns | Implemented | Reported in profile |
| Formula expressions vs cached results | Implemented | Loaded separately; uncalculated formulas flagged |
| `.xls`, `.xlsm`, `.xlsb`, `.ods`, password-protected | Implemented (as explicit rejection) | Clear message before processing |
| No macros / no external links / no connection refresh | Implemented | Macro packages rejected; links never followed |
| Preservation of supported features | Implemented | Verified per edit by validation gates |
| Fidelity risk detection + acknowledgement | Implemented | Package inventory before; measured loss after dry run; approval blocked until acknowledged |
| Lossless round-tripping of charts/pivots/slicers | Not implemented | openpyxl limitation; measured and disclosed instead |

## F–G Formulas and grounding
| Feature | Status | Notes |
|---|---|---|
| Formula error diagnosis | Implemented | #DIV/0! divisor analysis, generic IF/IFERROR fix proposal |
| Consistency checks | Implemented | R1C1-style comparison; typed-over cells |
| Relative/absolute, cross-sheet references | Implemented | Explained per reference |
| Modern functions | Partially implemented | XLOOKUP proposed when the target is Microsoft 365 (default); legacy INDEX/MATCH variant available in code; compatibility notes shown |
| Real calculation | Partially implemented | LibreOffice verification when installed; limited evaluator previews otherwise (labelled) |
| Deterministic numbers with references | Implemented | |
| LLM number grounding check | Implemented | Ungrounded text replaced by deterministic narration |

## H–K Harness, roles, contracts, context
| Feature | Status | Notes |
|---|---|---|
| Run state machine with all states | Implemented | |
| Tool registry, typed I/O, validation, permissions | Implemented | |
| Timeouts, retries, max steps, token & cost budgets | Implemented | |
| Cancellation, checkpoints, approval gates, logs | Implemented | |
| Idempotent approvals / duplicate-write prevention | Implemented | |
| Logical roles | Implemented | Modules, not autonomous agents |
| Versioned JSON contracts | Implemented | `GET /api/schemas` |
| Scoped conversation context and invalidation | Implemented | Selection, confirmed business rules, last result, pending clarification |
| Vector retrieval | Not implemented | Not needed for current features |

## L–O UX, mutations, NL analytics, observability
| Feature | Status | Notes |
|---|---|---|
| Excel-style workspace, FloPilot panel, activity drawer | Implemented | Virtualised grid, formula bar, name box, sheet tabs, status bar stats |
| Keyboard navigation, focus states, contrast | Implemented | Arrow/Shift/Enter/Tab/PageUp/PageDown in grid; AA contrast checked |
| Filtering rows | Implemented | Server-side “Filter rows containing…” |
| Stale approval rejection | Implemented | |
| Ambiguity handling (clarification) | Implemented | Remembered per conversation as a confirmed business rule |
| Association vs causation; anomalies as candidates | Implemented | |
| Run/correlation ids, tool outcomes, approvals, durations, tokens, cost | Implemented | Audit table + run steps |
| Redacted audit logs, admin-only operational log | Implemented | |
| Retention and deletion | Implemented | Startup purge after `FLOPILOT_RETENTION_DAYS`; `DELETE /api/workbooks/{id}` (API only, no UI button) removes blobs, chats and change sets; audit events are kept |

## P–S Security, QA, reliability, stack
| Feature | Status | Notes |
|---|---|---|
| Server-side keys, env secrets | Implemented | |
| Authentication | Demo only | Local demo tokens; OIDC interface not implemented |
| Workspace isolation, per-operation access checks | Implemented | Cross-workspace requests return 404 |
| Upload/request limits, rate limits | Implemented | Per-user chat/upload limits |
| Restricted network for backend | Implemented (Docker) | Internal network without egress by default |
| Prompt-injection handling | Implemented | Untrusted-data wrapping, policy-blocked tools, instruction-like text flagged |
| Formula-injection protection | Implemented | CSV export, CSV import, text writes |
| Dependency scanning | Implemented | `make scan` (pip-audit, npm audit) |
| Container scanning | Partially implemented | `make scan` runs Trivy if installed; not executed in the build environment (see VALIDATION.md) |
| Background jobs | Implemented | Thread pool; no external queue |
| Atomic version publication, temp cleanup, crash recovery | Implemented | |
| PostgreSQL / object storage | Not implemented | Interfaces and migration path documented |

## T–X Cost, charts, demo, extensions
| Feature | Status | Notes |
|---|---|---|
| Schema-first, bounded tool output, cached profiles | Implemented | |
| Measured token usage, labelled cost estimate | Implemented | Zero in demo mode |
| Small-model routing | Partially implemented | Deterministic planner is the zero-cost classifier; single configurable model for the rest |
| Charts with titles, units, filters, references, gaps, category caps | Implemented | |
| Synthetic demo workbook with seeded issues | Implemented | Sales, Expenses, Inventory, Customers, Summary (+ hidden Notes) |
| Works without a model key | Implemented | Clearly labelled demo mode |
| Anthropic provider | Implemented (not exercised live) | Verified offline with a mock transport; no key available during the build |
| OneDrive/SharePoint, Graph, enterprise identity, data dictionaries, org calculation rules | Not implemented | Extension interfaces only |
