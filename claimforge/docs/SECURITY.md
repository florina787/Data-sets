# Security, Privacy & Agent Safety

> Advisory engineering controls for a **synthetic demo**. No formal compliance assessment or certification is claimed.

## Data safety
- Only **synthetic data** is used. IDs are `MBR-SYN-*`, `PRV-SYN-*`, `CLM-SYN-*`, and there are no names, addresses or real clinical records.
- Every UI page, API response (`/health`, `X-Synthetic-Data: true` header) and data file carries the label
  *SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION.*

## Secrets
- `ANTHROPIC_API_KEY` is read from the environment, or from a git-ignored `.env`. It is never hardcoded.
- It is held on `Settings._anthropic_api_key` with `repr=False`. Only `LLMClient` reads it, through `secret_api_key()`.
- `Settings.public_dict()` exposes only `anthropic_api_key_configured: bool`, and `/health`, `/metrics` and the UI use that view.
- A `RedactingFilter` and `JsonFormatter` scrub `sk-ant-…`, `api_key=…`, bearer tokens and private keys from all logs.
- `.gitignore` excludes `.env*` (except `.env.example`), `*.key`, `*.pem` and `secrets/`.
- The repository was scanned for keys, tokens and private keys before commit.

## Input validation
- Pydantic request models use `extra="forbid"`, bounded string lengths, enum and literal claim counts, and a persona allowlist.
- Claim IDs are pattern-checked, billed amounts must be > 0 and ≤ 10,000, and claims carry 1–10 lines.
- A 2.5 MB request-body limit is enforced by middleware (413).
- Uploads must be `.md` or `.txt`, use a safe filename (no path traversal), be UTF-8 with no NUL bytes, and stay
  under the `MAX_UPLOAD_BYTES` limit.
- Error responses never echo stack traces. Unhandled errors return a generic 500.

## Prompt injection (direct & indirect)
- User requests are screened (`app/security/sanitizer.py`). A flagged request raises security finding
  `SEC-PI-01`, but it **does not change routing, tool permissions or deterministic decisions**.
- Uploaded documents are screened, instruction-like lines are quarantined (not indexed), and the docs get an
  `UPLOAD-` id prefix so they cannot override curated policy.
- In live mode, retrieved or user content is passed inside `<untrusted_data>` tags. The system prompt forbids following it,
  and LLM output is narrative only.

## Agent safety
| Control | Implementation |
|---|---|
| Tool allowlists / least privilege | `ToolRegistry`: each tool lists its allowed agents. Investigation tools are open only to `root_cause` |
| Consequential actions | `deploy_release` is consequential, with an **empty allowlist**, and needs a human approval token (`ApprovalRequiredError`) |
| Runaway loops | `MAX_AGENT_ITERATIONS` (agent loops and per-node re-invocation), `MAX_WORKFLOW_STEPS`, LangGraph `recursion_limit` |
| Excessive usage | `MAX_TOOL_CALLS` per agent run. Live-mode `max_tokens` is bounded, and calls time out (`LLM_TIMEOUT_SECONDS`) |
| Timeouts | `AGENT_TIMEOUT_SECONDS` is checked between tool calls (`AgentTimeoutError`) |
| Hallucinated parameters | Tools take structured kwargs, with optional Pydantic input models. Ruleset IDs are validated |
| Unauthorized actions | No agent can deploy, modify production, change policy or adjudicate claims |
| Audit | `AuditLog` records agent start/end, tool calls, denials, approvals and errors, with IDs and counts only |

## Human-in-the-loop
These steps require a human:
- clarifying a requirement ambiguity
- reviewing ADD/REPLACE architecture changes
- approving a release
- approving remediation and reprocessing

## Logging policy
Logs contain request IDs, actor, action, latency and counts. Claim payloads, PHI-like fields and secrets are never logged.

## Dependency hygiene
The dependency set is minimal and listed in `requirements.txt`. The `anthropic` SDK is optional, and it is imported
lazily, only in live mode. The Docker image runs as a non-root user (`uid 10001`).

## Known gaps (demo scope)
- There is no authentication or RBAC on the demo API or UI. Production would need OIDC and role-based scopes.
- State is held in memory, with no encryption at rest. Platform-level controls are assumed and not verified.
- The security agent is rule-based. There is no SAST, DAST or dependency-vulnerability scanning.
