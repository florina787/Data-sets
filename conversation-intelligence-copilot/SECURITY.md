# Security and AI governance

Proportionate controls for a local prototype, with the production gaps stated plainly. The Governance page in the app shows the same controls with live status.

## Implemented

| ID | Control | How | Verified by |
|---|---|---|---|
| GOV-001 | Secrets only in environment | `GEMINI_API_KEY` is read by `pydantic-settings` from env/`.env` (field `repr=False`); `.env` is git-ignored; the browser never receives keys; no key in responses or logs. | `test_secrets_never_leak` |
| GOV-002 | PII masking | Email, UPI ID, card, phone, account number and IP patterns masked at ingestion into `masked_text`, which is the only text used by labelling prompts, the index, evidence, the UI and logs; re-checked on outputs by the governance node. | `test_pii_masking`, `test_pipeline_outputs`, API test on C0000011 |
| GOV-003 | Pseudonymisation | Customer handles → salted SHA-256 IDs; not used in analysis. | `test_normalize_and_quality_checks_detect_problems` |
| GOV-004 | Prompt-injection controls | Structural: the model fills typed schemas with closed enums, cannot call tools or write SQL/code; transcripts and questions are passed inside delimiters and labelled as data; IDs from model output are re-validated. Heuristic: instruction-like patterns in questions are flagged in the audit log. | `test_unsupported_and_injection_are_safe` |
| GOV-005 | Tool safety | Only registered read-only operations; Pydantic-validated arguments (enums, ranges); values bound as SQL parameters; 5,000-row cap; read-only DuckDB connection. | `test_registry_rejects_unknown_ops_and_bad_args`, `test_sql_injection_in_filter_values_is_inert` |
| GOV-006 | Numeric grounding | A model explanation containing any number not present in the verified results is discarded for the deterministic narrative, and the rejection is recorded. | `test_with_gemini_ungrounded_numbers_are_rejected` |
| GOV-007 | Coaching safeguards | Minimum conversations per agent; decision-support notice; human-review flag on coaching and leadership answers; questions asking for personnel decisions (fire, discipline, demote…) are refused; no protected attributes exist or are inferred. | `test_q2_coaching_requires_human_review`, `test_personnel_decisions_are_refused` |
| GOV-008 | Synthetic data isolation | Tagged `synthetic_demo`; excluded unless `ENABLE_SYNTHETIC_DEMO=true` and the mode is chosen explicitly. | supervisor and API tests |
| GOV-009 | Retention | Sessions purged after `SESSION_RETENTION_DAYS`; per-session delete endpoint (audited). | `test_sessions_clear` |
| — | Input limits | Question ≤ 1,000 chars (truncated with a finding), control characters stripped; request IDs and session IDs validated by pattern. | `test_chat_validates_input` |
| — | CSV export safety | Cells starting with `= + - @` are prefixed to prevent spreadsheet formula injection. | `lib.test.ts` |
| — | Audit trail | Requests, cancellations, session clears, human-review labels and circuit resets are written to `audit_events`. | Governance page |

## Human review

* Coaching and leadership outputs carry `human_review_required = true`, a visible notice and named decision owners. The system recommends reviews; it never makes personnel decisions.
* A blind review panel (Governance page) samples masked messages, hides the system label, and computes accuracy, per-class P/R/F1, a confusion matrix, Cohen's κ and inter-annotator agreement from submitted labels only.

## Not implemented (production gaps)

| Gap | Production approach |
|---|---|
| Authentication, RBAC, tenant isolation | SSO (OIDC/SAML), role-based access to coaching data, row-level tenant filters |
| Encryption at rest | Encrypted volumes / managed DB encryption; KMS-managed keys |
| Secrets management | Vault / cloud secret manager with rotation instead of `.env` |
| Network policy for the model | Egress allow-list, private endpoints / Vertex AI with data-residency controls |
| Central audit retention | Ship audit and telemetry to an append-only store with retention policy |
| PII detection beyond regex | Named-entity PII detection (e.g. Presidio/DLP) for free-text names and addresses |
| Rate limiting of the public API | Gateway-level quotas per user |

## Reporting

This is a prototype; report issues to the repository owner.
