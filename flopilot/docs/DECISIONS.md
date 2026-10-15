# Decisions, defaults and assumptions

## Inputs and the defaults chosen

| Input | Value used | Notes |
|---|---|---|
| Product name | **FloPilot — Florina’s Excel Copilot** | Mascot FloMin; independent product, not Microsoft |
| Audience | Business analysts, finance, operations, managers | Language avoids jargon; “How this was calculated” is collapsible |
| Primary use cases | Analysis, cleaning, formulas, reporting | |
| Industry | General business | Demo data: sales, expenses, inventory, customers |
| Deployment | Local Docker first | `docker-compose.yml`; dev mode without Docker |
| LLM provider | Configurable; default **none (demo)** | Anthropic adapter included; `claude-opus-5-5` default when enabled, effort `medium` |
| Authentication | Local demo authentication | Enterprise identity is an interface |
| Theme / colours | Emerald `#107C41`, dark `#0B4F35`, light `#E2F0D9`, white, grid `#E5E7EB`, text `#1F2937`/`#6B7280` | Contrast verified: lowest text pair 4.63:1 |
| Font | Aptos → Calibri → Segoe UI → system sans-serif | Worksheet text ≈ 11 pt (14.5 px) |
| Workbook size | 10 MB upload, 500k cells, 50 sheets | In-memory openpyxl pipeline on one machine |
| Data sensitivity | Potentially confidential | No egress by default, redacted audit, retention 30 days |
| Budget priority | Cost-conscious | Deterministic first, LLM only when needed; LibreOffice optional |
| Excel version for proposed formulas | Microsoft 365 (XLOOKUP) | Compatibility notes shown; INDEX/MATCH builder exists |
| Date order when ambiguous | Ask the user, unless the column proves the order | |
| Currency display | From the cell number format | No conversion between currencies |

No question blocked implementation, so none was asked.

## Architectural decisions

1. **Standalone web app first; no live Excel connection.** The add-in is an extension point. Every screen says the user is working on an uploaded copy.
2. **Deterministic numbers.** All computations live in `workbook/`; narration and the LLM only describe results. LLM text with untraceable numbers is replaced.
3. **Immutable versions + change sets.** Edits never modify a stored file. Approval is bound to (operation id, base version, change-set hash). Restores are new versions.
4. **Measure fidelity instead of trusting the library.** Dry-run every change and compare package inventories; block on loss unless acknowledged.
5. **Restore cached formula results after edits.** openpyxl drops them; without this, later analysis would see blank formula columns. Discovered during verification (LibreOffice mismatch) and fixed.
6. **Verification is separate from insertion.** The preview evaluator is labelled as such; LibreOffice is the optional real engine; neither is presented as Excel.
7. **One orchestrated workflow with logical roles**, not multiple autonomous agents — cheaper, deterministic, easier to audit.
8. **Deterministic planner as the zero-cost router.** It also makes the demo fully functional without a key. The trade-off is limited phrasing coverage in demo mode.
9. **Separate proposals for multi-step cleaning.** Each change is reviewable on its own; when one is applied, the others become out of date and can be re-prepared from their stored builder in one click.
10. **Refuse unsafe structural edits** (row deletion with dependent formulas, merged cells, validation/CF rules) and offer a non-destructive flag column.
11. **SQLite + local blobs now, interfaces for PostgreSQL/object storage later.**
12. **Custom virtualised grid** for an Excel-faithful look without a commercial grid dependency.
13. **Docker network isolation by default**; LLM egress is opt-in.

## Assumptions

* Uploaded workbooks have one main table per sheet with a header row in the top 10 rows (or an Excel table).
* “Actual” spending is the `Amount` column when no `Actual` column exists (stated as an assumption in the answer).
* “Transactions”/“orders” are rows; “invoices” are rows when no invoice column exists (stated).
* Duplicate candidates compare all non-identifier columns (re-keyed copies are the common case), plus repeated identifiers.
* Outliers use Tukey’s far-out fences (3×IQR) because business amounts are skewed; results are candidates for review.
