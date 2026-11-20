# Security model

| Control | Implementation | Status |
|---|---|---|
| Authentication | Demo bearer tokens (demo tenants only) | **Live OIDC not implemented.** Live tenants cannot log in, so they fail closed. |
| RBAC | viewer, operator, approver, admin; checked server-side on every route | Done, tested |
| Tenant isolation | `owned()` returns 404 for other tenants' rows; lists filtered by tenant | Done, tested |
| Audit | Per-tenant SHA-256 hash chain; `/governance/audit/verify` | Done, tamper-detection tested |
| Evidence integrity | Content hash per evidence row, RCA report hash | Done, tested |
| Credential handling | Tokens only in server settings, never accepted via the API, never logged; redaction of tokens, keys, passwords, JWTs and connection strings | Done, tested |
| Prompt injection | Untrusted text is flagged, stored as data, never executed; injection-flagged MCP tools are quarantined | Done, tested |
| Approvals | Hash binding, SoD (cannot be disabled by policy), nonce, TTL | Done, tested |
| Emergency stop / budgets | Per-tenant stop; `max_actions_per_hour` | Done, tested |
| Rate limiting (HTTP) | n/a | **Not implemented** |
| Secrets manager | Env vars only | **Not implemented** (Key Vault, Secrets Manager, etc.) |
| Data retention | n/a | **Not implemented** |

No SOC 2 or ISO 27001 claim is made.
