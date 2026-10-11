# Seven-minute demo script

Setup: `docker compose up --build`, open http://localhost:8080. If you have run the demo before, reset it first
(release manager → `POST /api/demo/reset`, or `make reset`).

| Time | Persona | Action | What to say |
|---|---|---|---|
| 0:00 | — | Point at the banner | “Independent prototype, synthetic evaluation data. Three separate modes: language is deterministic, predictions are synthetic fixtures (not CV inference), deployment is simulated. No L’Oréal systems, data or policies.” |
| 0:30 | Product owner | Open **BR-101** → Requirements | Eight ambiguities flagged: correct match, group definitions, lighting protocol, labels, acceptable regression, devices, re-capture, release evidence. Open a related-guidance link to show the exact excerpt. |
| 1:15 | Product owner | **Use all demo clarifications** → **Approve requirement v2** | The answers are configurable demo rules (top-1 primary, top-3 secondary, ≥ 100 per cell, ≤ 2 pp regression, ≥ 5 pp target). Show AC-1…AC-7 mapped to gate IDs. |
| 1:45 | ML engineer | Evidence → **Run evidence and impact agents** | Citations carry ID, version, section and retrieval time, and each opens its excerpt. Superseded protocol v1.0 is flagged OUTDATED. The vendor note's “SYSTEM OVERRIDE…” is shown as ignored. Three claims are UNKNOWN. |
| 2:30 | Product owner | Impact → **Accept** | High risk: DEV-T3 has no evaluation samples. |
| 2:50 | CV engineer → ML engineer | Development → register **rc1** → **Run evaluation** | Background job; the page polls. |
| 3:15 | any | Evaluation tab | Overall **+2.51 pp**, but **TS-3 × cool_fluorescent −4.31 pp** (CI −8.62 to −0.86) → G-NO-REGRESSION FAIL. TS-4 × warm also lost 3.48 pp of coverage. Raw counts, Wilson intervals, pp vs relative change, family confusion. Ask the copilot “Why is release blocked?”. |
| 4:00 | CV engineer, QA, ML engineer | Register **rc2**, QA approves the code review (the author cannot), run evaluation | Development agent flags that the diff changes DEV-T3's lighting map, which has no data. Outcome **PASS**: target +12.17 pp, no cell below 0 pp. |
| 4:45 | Domain reviewer, privacy reviewer, release manager | Approvals → domain ✓, privacy ✓, **Approve release** | Show the binding (digest, revision, dataset, config, policy, target). The approval is single-use and expires in 72 h; the approver differs from the author. |
| 5:15 | Release manager | Release → **Start simulated canary** | The approval is revalidated immediately before deployment. 5% stage. |
| 5:30 | Ops analyst / release manager | Monitoring → advance window → promote to 25% → advance ×2 | DEV-T3 × warm reaches 57 labels at 42.11% vs 72.95% reference → **alert**. Before that, too few labels for any conclusion. |
| 6:15 | Ops analyst | **Investigate** | The monitoring agent finds `lpm-v2` maps DEV-T3 warm → cool_fluorescent (previous map: warm). Caveat: the alert alone doesn't prove the cause; confirm with a device test. **Request rollback**. |
| 6:40 | Release manager | **Approve rollback** | Compatibility checks pass, v2.3.0 is restored (simulated) → ROLLED_BACK. |
| 6:50 | any | Audit tab | Traceability chain from requirement to rollback, hash-chain verification, measured agent telemetry (0 tokens in deterministic mode), report export. |

Fallback if time runs short: skip the evidence excerpt dialog and the copilot question.
