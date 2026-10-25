# Threat model (demo deployment)

## Assets
Synthetic restricted maintenance records and documents; policy definitions and tool pins; approval records and idempotency keys; audit chain; session-signing secret; generated adapter code; host machine.

## Actors
Legitimate personas (incl. guest and external supplier); a malicious insider using a valid persona; a compromised or prompt-injected document; an untrusted/rogue MCP tool; a malicious upload; a local attacker with file-system access.

## Trust boundaries
See [ARCHITECTURE.md](ARCHITECTURE.md#trust-boundaries).

## Attack trees and mitigations

| Goal | Path | Mitigation (implemented) | Residual risk |
|---|---|---|---|
| Exfiltrate restricted records | Ask the assistant to e-mail them | Exfil intent routed to governance graph; POL-004 denies before tool runs; 0 executions asserted in tests | Copy/paste from the UI by an authorized user is not preventable by software |
| | Hide instruction in a document | Injection quarantine + POL-011 denies actions sourced from retrieved content | Novel phrasing may evade the pattern list; POL-011 still blocks actions |
| | Register a shadow export tool | Allowlist + schema-hash pinning (POL-006) | A privileged user editing the allowlist file |
| Read data above clearance | Query or search | Label/role filter in SQL before ranking; per-endpoint POL-003; agents limited to the human's rights | Aggregation/inference from public data |
| Unauthorized write | Call execute without approval | POL-005: approved, unexpired, matching idempotency key, not replayed; SoD (POL-013) | Two colluding approvers |
| Privilege escalation | Agent or user changes roles/policies | POL-007; policies are code reviewed in VCS | Host admin |
| Forge identity | Craft/alter token | HMAC signature, audience, expiry checks | Secret theft from data dir |
| Code execution via upload | Upload script/SQL/ZIP | Parse only; ZIP traversal/symlink/bomb checks; XML DTD rejection; size/extension/binary checks | Parser bugs (regex DoS bounded by size limit) |
| Code execution via generated adapter | Malicious template output | Templates are static; static checks; tests only on explicit permitted request, subprocess, minimal env, timeout | Subprocess is not an OS-level sandbox |
| SSRF | Supply callback URL | No user-supplied URLs fetched; egress guard blocks non-loopback; LLM URL must be loopback | — |
| Tamper with evidence | Edit audit rows | Hash chain detects edits/deletions; export carries verification | Full-chain rewrite by host admin |
| DoS | Flood workflows | Concurrency semaphore, rate limit per actor, step timeouts, circuit breakers | No reverse proxy/rate limiting at the HTTP edge |
| XSS | Inject HTML in answers/docs | React escaping; custom markdown escapes HTML first (tested); CSP in production build | Dev server runs without CSP |
