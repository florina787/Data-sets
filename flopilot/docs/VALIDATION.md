# Validation results

Recorded on 2026-10-15 in the build environment (Linux, Python 3.13, Node 22, Chromium 1194, LibreOffice installed, no LLM API key). These are the actual outcomes; nothing below is estimated.

## Automated tests

| Suite | Command | Result |
|---|---|---|
| Backend (pytest) | `cd backend && python -m pytest` | **121 passed, 0 skipped, 0 failed** in 31.7 s (includes LibreOffice verification tests and the offline Anthropic adapter test) |
| Frontend unit (vitest) | `cd frontend && npm test` | **16 passed** (2 files) |
| TypeScript | `npm run typecheck` | No errors |
| Production build | `npm run build` | OK — JS 287.9 kB (89.4 kB gzip), CSS 18.3 kB |
| Lint | `ruff check app tests scripts --select E,F,W,B` | All checks passed |
| Browser journey (Playwright) | `node e2e/ui_journey.mjs` | **10/10 steps** against the Vite dev server, and 10/10 in three runs against the Docker Compose stack (nginx + production build + strict CSP) |

What the backend suite covers: deterministic aggregations with hand-computed expectations; missing, mixed and text-number handling; date parsing including locale ambiguity; numeric text; display formats; time series gaps; month-over-month; variance; correlation labelling; mixed currency warning; ambiguous columns; empty sheets; malformed, empty, macro, legacy and password-protected files; size limits; CSV formula neutralisation; profiling of every seeded demo issue; formula explanation, diagnosis, consistency, policy (blocked functions, external references, missing sheets), placement, cross-sheet lookups, custom templates and the evaluator; formatting/table/validation/CF preservation; detection of unplanned changes, formula overwrites and totals drift; precondition failures; structural-edit blocking; native report charts; measured fidelity; the full upload → ask → approve → download → reopen journey; stale approvals; idempotent replays; hash mismatch; reject/cancel; restore; access control across workspaces and roles; prompt injection in workbook content; CSV export; rate limiting; deletion purge; state machine; tool permissions; typed input validation; timeouts and retries; mid-run cancellation; step and token budgets; grounding of LLM text; LLM refusal to apply changes; crash recovery; every suggested prompt in the UI.

The browser journey covers: demo sign-in; opening the demo workbook; clarification for “revenue”; grounded answer with source navigation; cleaning proposals with nothing applied; approve → out-of-date proposal → prepare again → approve; formula preview Before/After in the grid and apply; report sheet with native chart; restore version 1 from Activity; viewer restrictions.

## Defects found and fixed during verification

* Cleaning wrote over a custom column width and restyled existing cells — caught by the validation gate (the candidate was rejected, the version kept); fixed.
* openpyxl dropped all cached formula results on save, so later analyses saw blank formula columns — exposed by LibreOffice verification; fixed with `cache_values.py`. After the fix, LibreOffice’s recalculation of 120 inserted margin formulas matched FloPilot’s previews exactly.
* Profit-margin planning chose `Profit` as the revenue column for “profit-margin” (hyphenated) — fixed.
* Evaluator treated `^` as right-associative (Excel is left-to-right) — fixed.
* Whitespace-only category variants (`"Europe "`) were not normalised — fixed.
* Wordmark SVG referenced an external image that browsers block in `<img>` — fixed by inlining.
* Page-level scrolling when the chat grew — fixed.
* A chat response arriving after sign-out could briefly block the next user’s composer — fixed with session scoping.

## Security and supply chain

| Check | Result |
|---|---|
| `pip-audit -r requirements.txt -r requirements-llm.txt` | No known vulnerabilities found |
| `npm audit` (all and `--omit=dev`) | 0 vulnerabilities |
| Container image scan (Trivy) | **Not executed**: Docker Hub returned 429 (anonymous pull limit) for the Trivy image and the release binary could not be downloaded. `make scan` runs it where Trivy is installed. |
| Backend network isolation (Docker) | Verified: outbound request from the backend container fails (`Temporary failure in name resolution`) |
| Containers run as non-root | Verified: backend `uid=10001(flopilot)`; frontend uses nginx-unprivileged |
| CSP and security headers | Verified on responses from nginx |

## Docker deployment

* `docker compose build` and `up` succeeded; backend reported `healthy`; the app was served on `:8080` and answered requests through the nginx proxy; the browser journey passed 10/10 against it.
* The final backend changes (deletion purge, mixed-unit warning, configurable rate limits, `.env` loader) were made after the last full-stack Docker e2e run. The backend image was rebuilt from the final code and started healthy; a final full `docker compose build` could not be repeated because Docker Hub rate-limited the nginx base image (HTTP 429). Those backend changes are covered by the pytest suite.
* Building behind this environment’s TLS-inspecting proxy required the optional `FLOPILOT_EXTRA_CA_FILE` build secret.

## Not verified

* The live Anthropic API (no key available). The adapter was checked offline against a mock HTTP transport, and the agent loop with a scripted provider.
* Opening generated files in desktop Microsoft Excel (files were reopened with openpyxl and recalculated with LibreOffice).
* Performance at the 500k-cell limit; no load testing was done.
* Screen-reader testing; keyboard navigation and contrast were checked, not a full accessibility audit.
