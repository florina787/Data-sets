# Security & Privacy

> This prototype implements privacy-by-design controls, but **that does not make it legally compliant**.
> A formal privacy impact assessment, PHIPA analysis (Ontario), PIPEDA review where applicable, threat model
> and legal review are required before processing any real patient information.

## Implemented controls (with evidence)

| Control | Implementation | Test evidence |
|---|---|---|
| Authentication | HS256 JWT (aud/iss/exp checked) for synthetic demo users; demo login refused in staging/production | `tests/security/test_security.py::test_tampered_and_expired_tokens_rejected`, `test_demo_login_disabled_in_production` |
| RBAC | Role → permission map (`database/session.py`), `require()` dependency on every route; frontend role-based nav + route guards | `test_patient_cannot_reach_engineering_or_admin`, frontend `components.test.tsx` |
| Object-level access | Workflows, bookings, approvals scoped to the owning user | `test_cross_patient_access_denied` |
| Human approval | Bookings, radius expansion, clarifications, production deploys; separation of duties for releases | `tests/agents/*`, `test_engineer_cannot_deploy_to_production` |
| Side-effect tools | Require an *approved* approval id present in the run context | `tests/unit/test_harness.py::test_side_effect_requires_approval` |
| Prompt-injection | User text and untrusted tool/MCP output screened; instruction-like output removed; never grants tool authority | `test_untrusted_output_sanitized`, `test_prompt_injection_cannot_trigger_booking` |
| Data minimisation | Only allow-listed intake fields used; extra fields flagged; no free text in DB or checkpoints; FSA only from postal codes | `test_excess_data_ignored_and_flagged`, `test_state_contains_no_free_text` |
| Redaction | Emails, phones, health-card-like numbers, postal codes, DOBs, names; sensitive keys dropped. Applied to audit log, agent explanations and LangSmith (`hide_inputs/hide_outputs`) | `test_redaction`, `test_langsmith_redaction_hook`, `test_audit_log_is_redacted_and_tamper_evident` |
| Audit | Append-only, SHA-256 hash-chained; `GET /governance/audit/verify` | tamper test above |
| Encryption at rest | Fernet field encryption for booking notes; key required in staging/production. Disk/DB encryption is the platform's responsibility | `test_field_encryption_roundtrip`, `test_production_config_requires_secrets` |
| Secrets | Env vars / secret store only; `.env` git-ignored; startup validation; frontend never receives keys | `test_repository_secret_scan_clean`, e2e `no API keys or secrets in the served frontend` |
| Rate limiting | Sliding window per client + route group (in-process) | `test_rate_limiting` |
| Input/output validation | Pydantic on every request and tool input/output | `test_harness.py::test_ok_and_validation` |
| Consent | Notification, voice, booking-handoff consents recorded; notifications skipped without consent | `test_booking_needs_consent`, API booking test |
| Retention & deletion | `POST /admin/retention/run`, `DELETE /me/data` | API test `test_preferences_history_and_deletion` |
| Clinical safety | Conservative red-flag screen interrupts search; 911 / Health811 / 988 guidance; never diagnoses | `tests/unit/test_nlu_safety_rag.py` |
| HTTP hardening | nosniff, frame deny, no-referrer, no-store; nginx CSP + Permissions-Policy | `test_request_id_and_security_headers` |

## Not implemented / gaps (honest)

* OAuth 2.0 / OIDC with an external IdP (planned). Demo JWT login only.
* TLS termination is expected at the ingress/load balancer; local compose is plain HTTP.
* Rate limiter is per-process (use Redis for multiple replicas).
* `pip-audit` / `npm audit` run in CI; not executed in this sandbox run.
* No WAF, no formal threat model, no penetration test, no access-review tooling.
* Browser speech recognition (Chrome) may send audio to the browser vendor; disclosed in the UI, off by default.
* LangGraph checkpoints use SQLite even when the app DB is PostgreSQL (switch to `PostgresSaver` before multi-replica).

## Incident response (outline)

1. Detect (anomaly rules, Prometheus alerts, audit chain verification).
2. Contain: disable affected integration (`provider_integrations.authorized=false` → status `UNKNOWN`), roll back build via release API.
3. Investigate with correlated IDs (workflow ID ↔ request ID ↔ OTel trace ID ↔ LangSmith tags).
4. Notify per PHIPA breach obligations once real data is in scope (privacy officer + legal).
5. Post-incident: regression test, release approval, audit record.
