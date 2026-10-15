# Supported formats, fidelity and limitations

## Formats

| Format | Support |
|---|---|
| `.xlsx` | Supported (analysis and editing). Must be an Office Open XML workbook. |
| `.csv` | Supported. Converted to a one-sheet `.xlsx` working copy; the original CSV is kept unchanged. Plain numbers become numbers; everything else stays text (including text that looks like a formula, which is stored as text). Delimiters `, ; \| tab` are detected; UTF-8, UTF-16 and Windows-1252 are accepted. |
| `.xls`, `.xlsb`, `.ods`, `.numbers`, `.xltx`, `.tsv` | Rejected with a message explaining how to save as `.xlsx`/`.csv`. |
| `.xlsm` and any package containing `vbaProject.bin` | Rejected. Macros are never run. |
| Password-protected / encrypted workbooks | Detected (OLE container) and rejected with instructions to remove the password. |

## Limits (defaults, configurable)

| Limit | Default | Variable |
|---|---|---|
| Upload size | 10 MB | `FLOPILOT_MAX_UPLOAD_MB` |
| Uncompressed package size | 150 MB (zip-bomb guard) | `FLOPILOT_MAX_UNCOMPRESSED_MB` |
| Cells (sum of used ranges) | 500,000 | `FLOPILOT_MAX_CELLS` |
| Sheets | 50 | `FLOPILOT_MAX_SHEETS` |
| Range read per tool call | 400 cells | – |
| Grid window per request | 500 rows × 120 columns (grid shows up to 120 columns) | – |

These keep the in-memory openpyxl pipeline responsive on one machine. Larger workbooks need streaming (read-only mode) and a job queue; see DEPLOYMENT.md.

## Workbook fidelity

FloPilot edits with openpyxl, which rewrites the whole file. It **preserves**: sheet names and order, cell values and formulas, number formats, basic styling (fonts, fills, borders, alignment), row heights and column widths, merged cells, frozen panes, auto-filters, Excel tables, defined names, data validation and conditional formatting.

It **may not preserve**: native charts it cannot fully parse, images/shapes/form controls, pivot tables and caches, slicers and timelines, sparklines and other `x14` extensions, threaded comments, Power Query / data connections, custom ribbon UI, external-link caches.

How FloPilot handles this:

1. On upload it inventories these features (`fidelity.detect_features`) and shows them in the Data quality panel.
2. Every proposal is dry-run; the package inventory before and after is **compared**, not assumed.
3. If anything would be lost, approval is blocked until the user explicitly acknowledges it; the earlier version always remains available for download and restore.
4. After applying, validation gates confirm frozen panes, merged cells, filters, tables, validation, conditional formats and widths per sheet.

Lossless round-tripping is never promised.

### Cached formula results

openpyxl does not store calculated results. After an edit FloPilot restores them: formulas within its evaluator subset are recomputed, other formulas keep Excel’s saved value only if their direct inputs did not change, and the rest are left uncalculated (shown as “(not calculated)” in the grid). Every edited version has `fullCalcOnLoad` set so Excel recalculates everything when the file is opened.

### Formula evaluation

* **Preview values** come from FloPilot’s limited evaluator: arithmetic, comparisons, `&`, references (incl. other sheets) and `SUM AVERAGE MIN MAX COUNT COUNTA IF IFERROR IFNA ROUND ABS AND OR NOT YEAR MONTH DAY LEN UPPER LOWER TRIM CONCAT CONCATENATE ISBLANK INDEX MATCH(exact) SUMIF COUNTIF(equality)`. Anything else is reported as “not evaluated”, never guessed.
* **Verification** uses LibreOffice when installed. LibreOffice versions without a function (e.g. `XLOOKUP` in older releases) return `#NAME?`; FloPilot reports such cells as “cannot evaluate” rather than as errors.
* Inserting a formula is distinct from verifying its result; the proposal states which happened.

### Structural edits

Row deletion is refused when formulas reference rows that would shift, when the sheet has merged cells below the first deleted row, or when it has data-validation or conditional-formatting rules (openpyxl would not shift them). The non-destructive alternative (a review flag column) is offered instead.

## Other known limitations

* **Natural language in demo mode** is rule-based: it covers the documented intents (summaries, totals/averages/counts by group with simple filters, month-over-month change, actual vs budget, missing values, duplicates, outliers, correlation, distribution, trend charts, formula creation/explanation/diagnosis/consistency, cleaning, report sheets, restore). Other phrasings get a help message unless an LLM is configured.
* **Dates**: text dates are parsed for ISO, `/`, `-`, `.` and month-name formats; ambiguous day/month order is resolved from unambiguous values in the same column or by asking the user. Times and time zones are not analysed.
* **Units**: values are aggregated as stored; mixed currency formats in one column produce a warning, never a conversion.
* **Header detection** uses the first mostly-text row in the top 10 rows (or an Excel table); unusual layouts (multiple tables per sheet, multi-row headers) are flagged with low confidence and only the first table is analysed.
* **Charts in chat** are rendered by FloPilot only; only report sheets added through an approved operation contain native Excel charts.
* **Concurrency**: one backend process; version publication uses an in-process lock (see DEPLOYMENT.md for multi-instance requirements).
* **Authentication** is local demo authentication.
* The LLM provider path was verified offline (mock transport, scripted provider) but not against the live API in this build.
