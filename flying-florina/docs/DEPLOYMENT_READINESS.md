# Defense and disconnected deployment readiness

What works **today** (verified by tests or measurement) versus what a production deployment would still need. "Uses a local model"
does not by itself make a system air-gapped; this checklist is what would.

| Area | Today (demo) | Evidence | Needed for production |
|---|---|---|---|
| Local model inference | Your existing Qwen via llama.cpp / Ollama / local server; no external fallback | `app/llm/gateway.py`, `scripts/check_qwen.py`, tests with a test-only fake server | Hardware sizing, model provenance & license review, model change control |
| Offline data | Synthetic SQLite seeded locally (seed 20261024) | `scripts/offline_check.py`: 0 egress attempts | Real data ingestion only in an approved environment |
| Network restriction | Process-level egress guard blocks non-loopback sockets/DNS; LLM URL must be loopback (POL-008) | `test_offline_guard_blocks_external_egress`, Playwright aborts external requests | Host/network firewalls, egress proxies, network segmentation |
| Runtime dependencies | Python/npm packages and the llama.cpp wheel fetched once at setup | `scripts/setup.sh`, `docs/DEPLOYMENT.md` (offline wheel/npm bundle procedure) | Internal package mirror, SBOM, vulnerability scanning, signed artifacts |
| Telemetry | Local SQLite only (`llm_calls`, `workflow_events`, `audit_events`) | No external telemetry code paths | Central log shipping inside the enclave, retention policy |
| Authentication | Demo persona login (signed tokens, audience/expiry) | `test_typed_errors`, `test_wrong_audience_token_rejected` | Enterprise IdP (OIDC/SAML), MFA, real clearance attributes |
| Authorization | Deny-by-default policy engine, 13 policies, approvals with separation of duties | `tests/test_policy.py`, Security Lab 12/12 | Policy review by security, formal access reviews |
| Approved integrations only | Local mock adapters and a local MCP server; tool allowlist with schema pinning | `test_untrusted_tool_cannot_register` | Customer-approved connectors, data-sharing agreements |
| Data retention | Demo reset regenerates everything; reports and audit stay in the data folder | `POST /api/demo/reset` | Configurable retention and deletion, legal hold |
| Controlled synchronization | Not implemented | — | One-way transfer procedures, review before import/export |
| Local audit storage | Hash-chained audit log, export with verification | `test_audit_chain_verifies_and_detects_tampering` | WORM storage or external signing anchor (tamper-proof, not only tamper-evident) |
| Export control (ITAR/EAR), NIST 800-171, CMMC, aviation recordkeeping | Informational mapping only | `docs/COMPLIANCE_MAPPING.md` | Qualified compliance assessment; no certification is claimed |
| Container isolation for generated code | Subprocess with minimal env and timeout | `test_bridge_generate_and_run_generated_tests` | Container/VM sandbox with seccomp/AppArmor |

Bottom line: the demo runs disconnected with your local Qwen and synthetic data, and it is honest about the boundaries. It is not
accredited, not production-secure, and must not hold real controlled data.
