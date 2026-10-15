# Security, privacy and data flow

Workbooks are treated as **potentially confidential**. Cell contents, comments, sheet names and imported text are **untrusted data**.

## Data flow

```
Browser ──(upload .xlsx/.csv, bearer token)──▶ nginx ──▶ FastAPI
   │                                                        │ validate type/size/zip structure (no parsing yet)
   │                                                        │ store original immutable blob, parse, profile
   │◀───── grid windows, profile, answers ───────────────────┤
   │                                                        │ deterministic tools read the immutable version
   │                                                        │ (optional) LLM receives: compact schema (column names,
   │                                                        │ types, ≤3 samples per column), the user's question and
   │                                                        │ bounded tool results — wrapped as untrusted data
   │── approve(op id, version, hash) ──────────────────────▶│ apply → validate → publish new immutable version
   │◀────────────── download (Authorization header) ────────┤
```

* No workbook data leaves the server in demo mode. With an LLM configured, only the items listed above are sent to the provider; the full workbook is never sent by default.
* LibreOffice (optional) runs locally on a temporary copy with an isolated profile and no network (Docker).

## Controls

| Area | Control |
|---|---|
| Secrets | API keys only in server environment / `.env` (git-ignored). Nothing secret in the frontend bundle, exports, screenshots or logs. The browser holds only a demo session token (sessionStorage); downloads use the Authorization header, not tokens in URLs. |
| Authentication | Demo mode: seeded users with hashed bearer tokens. Enterprise mode is an interface (`IdentityProvider`) that refuses requests rather than allowing them when not configured. |
| Authorization | Roles viewer / analyst / admin. Viewers cannot propose, approve, export or restore. Admin adds the operational audit log. |
| Workspace isolation | Every workbook, version, operation, run and conversation access goes through `get_workbook_row`, which checks the caller’s workspace. Other workspaces get the same 404 as a missing id (no existence probing). Runs and conversations are also scoped to their user. |
| File handling | Extension and magic-byte checks; OLE (encrypted/legacy) rejection; macro packages rejected; zip path traversal, compression ratio and uncompressed-size checks; cell and sheet limits; storage keys confined to the storage root; blobs written read-only and atomically. |
| Request limits | Upload size enforced while streaming; nginx `client_max_body_size`; message length ≤ 2,000 chars; per-user chat and upload rate limits; bounded range reads and grid windows. |
| Error responses | Typed `AppError` messages only; unexpected exceptions return a generic message with a correlation id. No stack traces, prompts or paths in responses. |
| Network | In Docker the backend sits on an internal network with no internet egress; LLM egress is an explicit opt-in override. The frontend container only proxies `/api`. |
| Browser hardening | CSP (`script-src 'self'`, `frame-ancestors 'none'`, `connect-src 'self'`), `X-Frame-Options: DENY`, `nosniff`, `no-referrer`. All workbook text is rendered as text (React escaping; no HTML injection; markdown is parsed into elements). |
| Containers | Non-root users, read-only root filesystems, `no-new-privileges`, all capabilities dropped (backend). |
| Supply chain | Pinned dependencies; `make scan` runs pip-audit, npm audit and Trivy (when installed). |

## Prompt injection

* The system prompt states that workbook content is data, not instructions.
* Tool results are wrapped as `{"untrusted_workbook_data": …}` before reaching the model.
* The model can call only `read` and `propose` tools. `apply`, `export` and `restore` are refused by the policy controller even if requested; nothing changes without a person approving an exact change set bound to a version.
* The model cannot run shell commands or code, reach the network, or alter permissions — no such tools exist.
* Numbers in model-written text must appear in tool results, otherwise the text is replaced.
* Instruction-like text inside a workbook (e.g. “ignore previous instructions…”) is flagged in the profile as a data-quality note. The demo workbook’s hidden `Notes` sheet contains such a string and is covered by tests.

## Formula injection

* **CSV import**: text cells that start with `=`, `+`, `-`, `@` are stored as text, never as formulas.
* **CSV export**: text values starting with `= + - @ TAB CR` are prefixed with `'`.
* **Writes**: values written by cleaning operations and report sheets are stored with an explicit text type. Only formulas that are part of an approved change set are written as formulas.
* **Formula policy**: proposed formulas may not use `WEBSERVICE`, `HYPERLINK`, `CALL`, `REGISTER(.ID)`, `RTD`, `EXEC`, `FILTERXML`, `IMAGE`, or reference other workbooks; references to missing sheets are rejected.

## Logging, audit and retention

* `audit_events` record ids, versions, counts, durations, tool outcomes, approvals, exports and token usage. Keys such as `message`, `prompt`, `values`, `before`, `after` are redacted unless `FLOPILOT_LOG_WORKBOOK_CONTENT=true`.
* Users see a filtered activity history for their workbook; the full operational log (`/api/admin/audit`) is admin-only.
* Conversation history and change sets necessarily contain workbook values; they are stored in the metadata database and deleted with the workbook.
* Retention: on startup, workbooks older than `FLOPILOT_RETENTION_DAYS` (default 30; `0` disables) are purged: blobs, chats, change-set payloads and run results. Audit events (without content) are kept.

## Known gaps

* Demo authentication is not suitable for production; deploy behind enterprise SSO (OIDC) before handling real confidential data.
* Rate limits and locks are per process.
* The SQLite file is not encrypted at rest; use encrypted volumes or PostgreSQL with encryption at rest in production.
* Container image scanning was not executed in the build environment (see VALIDATION.md).
