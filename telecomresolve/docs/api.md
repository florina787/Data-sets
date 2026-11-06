# API contract

The machine-readable contract is [`openapi.json`](openapi.json) (regenerate with `make openapi`); the running
backend also serves it at `/openapi.json` and an interactive view at `/docs`.

## Conventions

- **Authentication:** `Authorization: Bearer <session token>`. In demo mode tokens come from
  `POST /api/auth/demo-login`. Actor, role and tenant are always loaded from the server-side user record; identity
  fields in request bodies are ignored. In production mode every authenticated route returns
  `503 IDP_NOT_CONFIGURED` until an SSO verifier is implemented.
- **Scope:** a case outside the caller's tenant or account segments returns `404 CASE_NOT_FOUND` (existence is
  not disclosed) and writes an `ACCESS_DENIED` audit event, before any evidence is retrieved.
- **Errors:** `{"detail": {"code": "...", "message": "..."}}`. Validation errors use `422 VALIDATION_ERROR`.
- **Request IDs:** send `X-Request-ID` or one is generated; it is echoed in the response and stored on audit events.
- **Idempotency:** `POST /api/cases/{id}/execute` requires an `Idempotency-Key` header. The same key returns the
  original execution (`replayed: true`); after a lost response it reconciles with the simulated system of record
  before retrying. A different key for an already-used approval returns `409 APPROVAL_ALREADY_USED`.

## Routes

| Method & path | Permission | Purpose |
|---|---|---|
| `GET /health` | none | Liveness |
| `GET /ready` | none | Database, seed and workflow readiness; 503 when not ready |
| `GET /api/system` | none | Disclaimer, app/generation/connector modes, policy & dataset versions, state machine |
| `GET /api/auth/personas`, `POST /api/auth/demo-login` | demo only | Persona list and session issue |
| `GET /api/auth/me` | session | Current principal and permissions |
| `GET /api/connectors` | session | Tool specs (schema, timeout, idempotency, errors, audit fields) and enterprise connector status |
| `GET /api/cases` | `case:read` | Cases in tenant and account scope |
| `POST /api/cases` | `case:create` | New intake for an in-scope account |
| `GET /api/cases/{id}` | `case:read` | Case detail (field-minimised by role) |
| `POST /api/cases/{id}/investigate?wait=` | `case:investigate` | Start the graph (202). Returns 409 if another investigation holds the case |
| `POST /api/cases/{id}/clarifications` | `case:clarify` | Add a customer clarification in `NEEDS_INFORMATION` and re-run |
| `GET/POST /api/cases/{id}/messages` | `case:read` / `evidence:read` | Grounded chat; answers carry citations and a generation-mode label |
| `GET /api/cases/{id}/evidence?snapshot_id=` | `evidence:read` | Snapshot items, hypotheses, diagnosis |
| `GET /api/cases/{id}/evidence/{ref_id}` | `evidence:read` | Exact source record/excerpt and whether it still resolves (URL-encode `ref_id`) |
| `GET /api/cases/{id}/citations/validate` | `evidence:read` | Re-validate every citation used by the case |
| `GET /api/cases/{id}/recommendations` | `recommendation:read` | Current and historical recommendations |
| `POST /api/cases/{id}/recommendations` | `case:investigate` | Propose a policy-permitted alternative (supersedes the current one and requests a new approval) |
| `POST /api/cases/{id}/approvals` | `case:investigate` (request) / `approval:decide` | `{"action": "request"|"approve"|"reject", ...}`; approve/reject require `approval_id` and the reviewed `payload_hash` |
| `GET /api/approvals` | `case:read` | Approval queue in scope with `can_decide` per caller |
| `POST /api/cases/{id}/execute` | `action:execute` | Execute an approved action (simulated connector) |
| `POST /api/cases/{id}/verify` | `recovery:verify` | Recovery check; optional `customer_report` keeps the case open on conflict |
| `POST /api/cases/{id}/cancel` | `case:cancel` | Cancel and supersede open approvals |
| `GET /api/cases/{id}/audit` | `case:read` | Case audit events |
| `GET /api/cases/{id}/audit/replay` | `case:read` | Replays transitions, verifies hash chain, reconstructs recommendations from snapshots |
| `GET /api/cases/{id}/events?access_token=` | `case:read` | Server-sent events streamed from persisted audit rows |
| `GET /api/audit` | `audit:read` | Tenant audit (auditor, supervisor) |
| `GET /api/dashboard` | `dashboard:read` | Operational metrics derived from persisted records |
| `GET /api/knowledge/search?q=` | `knowledge:read` | Scope-filtered lexical search |
| `GET /api/evaluations` | `evaluation:read` | Stored evaluation reports |
| `POST /api/demo/reset` | `evaluation:run`, demo only | Restore the known demo state |

### Error codes worth handling

`ILLEGAL_TRANSITION`, `CONCURRENT_MODIFICATION`, `INVESTIGATION_IN_PROGRESS`, `APPROVAL_NOT_PENDING`,
`APPROVAL_EXPIRED`, `PAYLOAD_MISMATCH`, `PAYLOAD_CHANGED`, `PAYLOAD_TAMPERED`, `STALE_APPROVAL`,
`APPROVER_NOT_AUTHORIZED`, `EXECUTOR_NOT_AUTHORIZED`, `NOT_APPROVED`, `APPROVAL_ALREADY_USED`,
`IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_KEY_REUSED`, `POLICY_BLOCKED`, `NO_ACTIVE_RECOMMENDATION`,
`CONNECTOR_UNAVAILABLE`, `IDP_NOT_CONFIGURED`.

### Note on the SSE token

Browsers' `EventSource` cannot send headers, so the events route accepts the session token as a query parameter.
Query strings can end up in proxy logs; a production build should use short-lived, single-purpose stream tokens or
a fetch-based stream with headers.
