# Security and governance (3.0)

Deterministic controls are authoritative. A language model may explain or classify; it never authorizes, approves, executes or exports.

| Control | Implementation | Evidence |
|---|---|---|
| Authentication | Signed demo tokens with audience and expiry (`app/core/security.py`) | `test_wrong_audience_token_rejected` |
| Deny-by-default authorization | 13 policies (POL-001…013) evaluated before every tool call and endpoint | `tests/test_policy.py` |
| Least privilege for agents | Agent rights = agent role ∩ human role; plus per-agent tool allowlists in the harness | `test_agent_cannot_call_tool_outside_its_allowlist` |
| Tool allowlist + pinning | Tools register only if name, version and input-schema SHA-256 match `tool_allowlist.yaml` (11 new 3.0 pins) | `test_untrusted_tool_cannot_register` |
| Input validation | Pydantic models with patterns/bounds on every 3.0 tool and endpoint | API 422 tests |
| Output validation | Evidence validation (required results present) and Evidence Challenger on model text | `test_unauthorized_tool_blocked_and_never_executed` |
| Prompt-injection defense | Injection/override attempts are refused before any 3.0 rule; retrieved text can never trigger actions | `test_injection_still_refused_before_3_0_rules` |
| Execution budgets | Atomic tool-call budget and wall-clock budget per plan | `test_budget_exhaustion_halts_safely` |
| Human approval | Writes require approval by a different authorized human; 3.0 adds no write paths | `test_approvals_still_cannot_be_bypassed_by_3_0_flows` |
| New action `analyze_media` | Visual-lab analysis allowed for engineering/planning/security roles; not guests, auditors or executives | `test_guest_cannot_analyze_media` |
| `simulate` action | Supply/resilience simulation: not guests or auditors | `test_guest_cannot_run_simulations` |
| Audit | Hash-chained events for workflows, exports, reports, memory deletion, visual analyses | `test_audit_chain_verifies_and_detects_tampering` |
| Sensitive data handling | Uploaded footage analysed in memory; only SHA-256 + result summary stored; memory deletable by its owner only | `test_upload_analysis_stores_hash_not_pixels`, restart/delete test |
| Offline guarantee | Process egress guard; loopback-only model endpoints (POL-008); map has no tile service | `make offline`, e2e external-request interception |
| Kill switch | Global stop for agent tool calls (2.0) | `tests/test_policy.py` |

## Visual-lab boundaries (by design, not configuration)

No tracking across frames, no trajectory or route estimation, no intent assessment, no targeting, interception, pursuit or engagement
logic. The module analyses prerecorded, authorized footage for civilian safety research and always states which method ran
(`vision_model` or `classical_baseline`, the latter labelled "not AI").

## Map boundaries

No real-time military asset locations, no sensitive defense facilities, no operational vulnerabilities. Locations are fictional
organisations in civilian cities; disruption notices are synthetic and labelled.

## Known limitations (unchanged from 2.0 unless noted)

Demo identity (no IdP/MFA); process-level egress guard (needs network controls in production); tamper-evident, not tamper-proof,
audit; SQLite single-writer; the Kubernetes manifests are a reference that has not been applied to a live cluster; no certification
(ITAR/EAR, NIST 800-171, CMMC, DO-178C) is claimed — the change-impact module is evidence for engineers, not a certification argument.
