# Production gaps

This is a single-machine portfolio prototype. Before any real use it would need:

| Area | Prototype | Production need |
|---|---|---|
| Identity | Seeded local accounts, bearer tokens in SQLite | Enterprise SSO (OIDC/SAML), MFA for approvers, SCIM, short-lived tokens |
| Code execution | Restricted subprocess; seeded patches only | Ephemeral containers or VMs with no network, read-only root, seccomp, quotas; signed build provenance (SLSA) |
| Generated code | Not executed | Sandboxed execution, mandatory human review of diffs, policy-as-code for allowed changes |
| Audit integrity | Append-only through the API; SQLite | WORM storage or a hash-chained audit log, external SIEM export |
| Persistence | SQLite files | Managed Postgres, migrations, backups, retention policies |
| Orchestration | In-process LangGraph with a thread pool | Durable workers, queue, retries with backoff, idempotency keys across services |
| Deployment | One local uvicorn process, brief swap downtime | CI/CD with artifact registry, blue/green or canary, automatic rollback on SLO breach |
| Telemetry | JSONL file, threshold rules | OpenTelemetry traces and metrics, SLOs, alerting, anomaly detection with on-call workflow |
| Incident analysis | Deterministic rules over a scripted fault | Correlation across services and changes, human-led postmortems; no claim of autonomous RCA |
| Inventory / payments | Simulator and mock tokens | Real integrations with contract tests, PCI scope isolation |
| Promotions | One campaign hard-coded as configuration from approved requirements | Campaign configuration service, mixed-price rules, stacking matrices, regional tax |
| Returns | Seeded allocation policy | Finance-approved refund rules, ledger integration |
| Static analysis | ruff and an AST forbidden-call scan | SAST/DAST, dependency and secret scanning, licence checks |
| LIVE AI | Two advisory agents, call budget, schema validation | Evaluation suite, red-teaming, cost and latency monitoring, data governance review |
| Accessibility | Semantic HTML, focus styles, reduced motion, role and label queries | WCAG 2.2 AA audit with assistive-technology testing |
| Localisation | English only | en-CA / fr-CA content (see the multilingual template) |
