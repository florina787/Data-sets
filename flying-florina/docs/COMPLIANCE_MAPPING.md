# Compliance mapping (informational, requires qualified compliance review)

Flying_Florina makes **no certification claims**. The table maps demo controls to references so a
qualified reviewer can see what exists; the same data is served at `/api/compliance/matrix` and shown in the Trust Center.

| Control | Implementation in this repo | Status | References (informational) |
|---|---|---|---|
| Deny-by-default RBAC/ABAC | `app/core/policy.py` POL-001/002/003 | implemented (demo) | NIST SP 800-171 3.1.1–3.1.3; NIST AI RMF GOVERN 1.4 |
| Separation of duties | POL-013 | implemented (demo) | NIST SP 800-171 3.1.4 |
| Least privilege for agents | agent ∩ human grants | implemented (demo) | NIST SP 800-171 3.1.5; AI RMF MAP 3.5 |
| Audit and integrity | hash chain + verifier | partial (tamper-evident) | NIST SP 800-171 3.3.1, 3.3.8 |
| Identification & authentication | demo tokens | demo only | NIST SP 800-171 3.5.1–3.5.3 |
| Boundary protection | POL-004 + egress guard | process-level | NIST SP 800-171 3.13.1 |
| Human oversight | approval gate, dry-run drafts | implemented (demo) | NIST AI RMF MANAGE 2.4, GOVERN 3.2 |
| Prompt injection | sanitization + POL-011 | pattern-based | OWASP LLM01; AI RMF MEASURE 2.7 |
| Incident response | kill switch POL-009 | implemented (demo) | NIST SP 800-171 3.6.1; AI RMF MANAGE 2.3 |
| CMMC | configurable reference only | not assessed | Verify current CMMC program rules and level with an assessor |
| ITAR / EAR | informational screening checklist (fictional DOC-018) | informational only | Requires export-compliance professionals |
| Privacy / contracts | synthetic data, log redaction | partial | Customer-specific |
