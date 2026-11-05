# Governance, zero-trust security, human-in-the-loop and privacy

## G. Governance enforcement plane

* **Identity**: `governance/identity.py` — `Principal` propagated through API → harness → tools → telemetry. The demo uses
  a mock IdP (short-lived HS256 tokens, roles resolved from the directory at request time, never from client claims).
  Production replaces it with the enterprise OIDC IdP behind the same `IdentityProvider` interface.
* **Policy-as-code**: `policies/*.yaml` (versioned bundle, content hash in every decision). Deny by default:
  1. unauthenticated → deny; 2. `prohibited` actions (trading, shell, raw DB, unrestricted network) → deny;
  3. RBAC grant required; 4. tenant isolation; 5. ABAC rules (client assignment, portfolio access, classification
  clearance, private-wealth segregation for external advisors, model-provider residency); 6. approval obligations.
  Missing attributes fail closed.
* **OPA**: `policies/opa/flo_authz.rego` mirrors the engine; `opa test` passes and `tests/security/test_opa_parity.py`
  compares the Python engine and OPA on ~2,000 decisions (identical allow/deny, denial codes and obligations). With
  `FLO_OPA_URL` set (Docker/K8s) the API uses the OPA sidecar and **fails closed** if OPA is unreachable.
  The parity test found and fixed a real divergence (obligations on denied decisions).
* **Resource-level checks**: clients, portfolios, documents, approvals, exports, jobs, workflows. Unknown ids are denied
  exactly like cross-tenant ids (no existence oracle).
* **Tool-level permissions**: every tool declares a permission and resource resolver; the gateway authorizes the *human*
  principal on each call. Model invocation is authorized for a scoped service identity (`orchestrator`) against provider
  region/classification policy (CA residency).
* **Audit**: append-only, SHA-256 hash-chained log in a separate connection/database (`governance/audit.py`); details are
  PII-redacted before persistence; `GET /api/audit/verify` detects tampering (tested).
* Security never relies on prompts: the injection tests run a **compromised model plan** (exfiltration, trading, e-mail)
  and show every call blocked by the gateway.

## H. Human-in-the-loop approvals

Gated actions: client communications, client recommendations, sensitive exports, board distribution, financial-record
changes, portfolio modifications (`policies/approvals.yaml`). Each approval stores action id, requesting identity,
action type, exact payload, SHA-256 payload hash, evidence, risk class, authorized approver role, expiry and status.
Controls (all tested): requester authorized at request **and re-validated at execution**; approver must hold
`approvals:decide` + an approver role, same tenant, not the requester, and must confirm the hash they reviewed; any
payload change **invalidates** the approval; single use (replay rejected); expiry enforced. The client-communication
workflow is a LangGraph graph with `interrupt()` and a SQLite checkpointer, so approvals survive restarts. Executors write
only to mock outboxes; **securities trading is prohibited**.

## M. Privacy

* Detection: e-mail, phone, SIN (Luhn-validated), account numbers (context + FLO format), client ids, DOB (context),
  street addresses, postal codes, person names (CRM gazetteer, honorifics; Presidio merged when installed), secrets/API
  keys/JWTs, and amounts linked to identified persons.
* Operations: redaction, partial masking, scope-stable tokenization (`[CLIENT_001]`, `[ACCOUNT_001]`), pseudonymization,
  data minimization (investment views drop client identity; contacts masked by default).
* Vault: Fernet-encrypted values, HMAC digests for lookup, per-tenant, TTL from `policies/retention.yaml`; mappings never
  reach the frontend or LLM context. Rehydration requires `privacy:rehydrate` on the underlying client (assigned advisor,
  or privacy/compliance officer with a recorded purpose) and is audited. Ambiguous names (shared by several clients) are
  never linked to a client id.
* Retention & deletion: purge of expired mappings; subject erasure overwrites ciphertext before deleting. Physical
  erasure from database pages/backups depends on the engine and backup policy (limitation).
* Pseudonymized data remains personal information; tokenization never lowers a classification.
* Telemetry/LangSmith receive only redacted inputs/outputs and ids.
