# Security and privacy notes

## Implemented in the prototype

| Control | Where | Tested by |
|---|---|---|
| Server-issued, HMAC-signed sessions; role/tenant read from DB per request | `app/auth/session.py` | `test_auth_scope.py::test_identity_cannot_be_asserted_by_body`, `test_requires_authentication` |
| Role permissions on every route (not hidden buttons) | `app/auth/permissions.py`, `require()` | auditor/field-coordinator direct-API tests |
| Tenant isolation and account-segment scope before retrieval | `app/workflows/scope.py`, tenant filters in every connector query | `test_cross_tenant_case_denied_before_retrieval`, `test_account_segment_scope`, eval `no_evidence_retrieved` |
| Knowledge filtered by tenant (SQL) and role before scoring | `app/retrieval/knowledge.py` | `test_knowledge_scoped_by_tenant_and_role` |
| Field minimisation (contact details hidden from auditors, field coordinators, analysts) | `app/api/serializers.py` | `test_auditor_is_read_only` |
| Redaction of emails, phone numbers, keys and sensitive keys in logs and audit detail | `app/observability/redaction.py` | `test_redaction` |
| Consequential writes require policy + approval + executor authorization, re-checked at execution | `app/workflows/service.py`, `app/policies/engine.py` | `test_approvals_execution.py` |
| Separation of duties for dispatch | catalog + `can_approve` | `test_separation_of_duties`, eval `proposer_cannot_self_approve` |
| Retrieved text treated as data; instruction-like content quarantined and never sent to a model | `app/agents/evidence.py` | `test_prompt_injection_quarantined` |
| Model output validated; cannot grant permissions, choose non-permitted actions, or change payloads | `app/agents/*`, policy engine | `test_llm_modes.py` |
| Provider credentials server-side only; no provider switching or silent fallback | `app/agents/providers.py` | `test_provider_outage_is_explicit_not_silent` |
| Append-only audit with per-case hash chain | `app/observability/audit.py`, ORM guards | `test_audit_is_append_only`, `test_hash_chain_detects_out_of_band_edit` |
| Demo seed/reset refused outside demo mode; production refuses requests without an IdP | `app/seed.py`, `app/auth/session.py` | `test_production_mode_disables_personas` |
| Secret scanning (gitleaks) and dependency audit in CI | `.github/workflows/telecomresolve.yml` | CI (not run in this build environment) |

## Known gaps (do not deploy as-is)

- **No SSO.** Production mode is deliberately non-functional until an OIDC/SAML verifier with audience, issuer,
  expiry and key-rotation checks is added and roles are mapped from IdP groups.
- **Prompt-injection detection is pattern-based.** It catches the seeded attack and common phrasings, not
  paraphrased or encoded instructions. The stronger guarantees come from the architecture: models never approve,
  never choose payloads and only pick among policy-permitted actions.
- **Audit is tamper-evident, not tamper-proof.** Someone with database write access can rewrite the whole chain.
  Production needs an external immutable sink (WORM storage or a ledger service) and periodic anchoring of chain
  heads.
- **Session tokens** are bearer tokens in `sessionStorage` (demo convenience). Production should use
  HttpOnly, Secure, SameSite cookies or a BFF pattern, plus CSRF protection.
- **SSE token in query string** (see [api.md](api.md)).
- **Rate limiting, request size limits and WAF rules** are not implemented.
- **Field-level encryption** of contact data is not implemented (SQLite has no encryption at rest).

## Production design requirements

- **Identity:** enterprise SSO for people; separate workload identities per connector with least privilege;
  no shared service accounts.
- **Transport:** TLS 1.2+ everywhere, including database and model endpoints; mTLS for internal services.
- **Secrets:** a secret manager / KMS; no secrets in environment files or images; rotation runbook.
- **Retention and deletion:** define per-record retention (cases, transcripts, telemetry excerpts, audit);
  deletion requests must cascade to snapshots and chat messages while the audit keeps non-personal metadata.
- **Encryption:** at rest for database, backups and object storage; customer contact fields encrypted at field
  level.
- **Data residency:** if Canadian hosting is required, *every* component that touches customer data must be
  verified: model inference, embedding generation, database, vector index, logs, traces, backups, support and
  operator access paths. Hosting one component in Canada does not make the system sovereign or compliant;
  claims require that end-to-end verification and the relevant legal review.
- **Model use:** an approved endpoint with contractual no-training, logging and retention terms; region pinning;
  prompts minimised to the fields needed (the prototype already sends evidence excerpts, never raw contact data).
