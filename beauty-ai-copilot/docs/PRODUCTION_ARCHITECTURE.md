# Production architecture (DESIGN ONLY — not deployed)

Nothing in this document has been provisioned, purchased or connected. It records the design a real deployment would
need, so that prototype shortcuts are explicit.

```mermaid
flowchart TB
  U[Reviewers] -->|OIDC/SAML SSO| GW[API gateway / WAF]
  GW --> FE[Static UI CDN]
  GW --> API[API pods (stateless)]
  API --> PG[(Managed PostgreSQL<br/>PITR, encrypted, restricted roles)]
  API --> Q[[Durable job queue]]
  Q --> W[Evaluation workers<br/>isolated network]
  W --> MR[Model registry]
  W --> MH[Authorized model hosting<br/>no image egress]
  W --> OS[(Private object storage<br/>consented images, object lock for audit)]
  API --> SEC[Secrets manager / KMS]
  API --> OBS[Observability: logs (redacted), metrics, traces]
  API --> DEP[Progressive delivery controller]
  API --> INC[Incident management]
  API -. optional, server-side .-> LLM[Approved LLM provider<br/>no images, redacted inputs]
```

| Area | Design |
|---|---|
| Identity | SSO (OIDC). Group-to-role mapping is owned by IAM. Persona selector disabled (`APP_ENV=production` already enforces this). Short-lived sessions; step-up auth for release and rollback approvals |
| Secrets | Secrets manager plus KMS. No secrets in images or environment files. The LLM key exists only server-side |
| Database | Managed PostgreSQL with point-in-time recovery and encryption at rest. Application role cannot UPDATE/DELETE `audit_events`. Alembic migrations run in the pipeline |
| Audit | Append-only table plus periodic export of chain heads to object-locked storage (WORM) and an external timestamp |
| Queue / jobs | Durable queue for evaluations, with visibility timeouts, bounded retries, dead-letter queue and idempotent workers. Cancellation flags in the database |
| Object storage | Private buckets per tenant, short-lived signed URLs, lifecycle rules matching consent retention, and inventory of derived artifacts (thumbnails, embeddings, annotations) for deletion |
| Model registry / hosting | Registry provides immutable artifacts and digests. Hosting is in an authorized environment; images never leave it and are never sent to LLMs |
| Deployment | Progressive delivery with configurable stages. Ambiguous outcomes are reconciled before retry. Automated rollback only under a separately approved policy |
| Observability | Structured logs with redaction (already implemented), trace IDs propagated, SLOs on readiness and job latency, alert routing to incident management |
| Retention | Consent-driven retention per record. Backups expire on a stated schedule (35-day design value), are not edited in place, and are documented in deletion reports |
| Disaster recovery | RPO ≤ 15 min (PITR) and RTO ≤ 4 h targets, to be validated. Restore drills use the tested restore path; the prototype has a logical restore test |
| Tenancy | Tenant ID on every row and query (implemented). Add row-level security in PostgreSQL as defence in depth |
| Supply chain | Pinned dependencies, SBOM, image scanning (Trivy in CI), signed images, dependency audit (pip-audit / npm audit in CI), secret scanning (gitleaks) |
