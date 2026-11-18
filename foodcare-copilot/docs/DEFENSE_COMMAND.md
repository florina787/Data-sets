# Enterprise Defense Command

**Technology → Defense Command** (`/defense`) and Jerry questions such as "Are we under attack?",
"Which business applications are affected?", "Can we isolate the affected endpoint?",
"Which licenses are unused?". Code: `backend/app/defense.py`, `backend/app/copilot/command_ops.py`,
`apps/control-room/src/screens/Defense.tsx`.

> **All security, licence and billing data here is simulated** for the fictional company. No SIEM,
> EDR, scanner, identity, billing or SaaS-admin system is connected; the Connect page says so.
> The storefront health check and its incidents are the only real operational records.

## Threat intelligence (read-only)

* 7 synthetic detections (SIEM/EDR/identity/network style) with classification and de-duplication;
  5 synthetic vulnerabilities (`SYN-VULN-*`) mapped to assets.
* Visuals: posture radar, exposure flow ("shows exposure, not a confirmed attack path"),
  vulnerability heatmap (CVSS, exploit known, internet-facing, active detection).
* Jerry never states the organisation is compromised. It separates **facts** (recorded
  detections), **hypotheses** and **recommendations**.

## Downtime correlation

Downtime windows are shown on a timeline next to detections. Overlaps are labelled
"Timing alone does not show that one caused the other." No root cause is invented.

## Alerts and escalation

Alerts are grouped and de-duplicated; acknowledging or resolving needs `alert.manage`
(engineer, release approver). Notification channels are `planned`: alerts are in-app only.

## Emergency Containment — guarded, never universal

There is no kill switch. Every containment follows the same flow:

1. **Preview (dry run)** — explicit action + explicit asset from an allowlist. Shows impacted
   services, impact level, safety checks, rollback and escalation. Changes nothing.
2. **Propose** — permission `containment.propose` (engineer).
3. **Approve** — permission `containment.approve`; step-up password check; the proposer cannot
   approve; high-impact actions need **two distinct approvers**.
4. **Execute** — within **15 minutes** of approval, idempotent, and in this build always a
   **dry run** (`CONTAINMENT_LIVE = False`). No write connector exists.

Refused outright: protected operational technology — `OT-REFRIG-03` (cold-store refrigeration),
`OT-LINE2-PLC` (fry line PLC) — and pausing customer-critical workloads. Conversation can only
*preview*: "Isolate the endpoint" returns the plan and who must approve; it never executes.

Every step is written to `defense_chain`, a hash-chained, tamper-evident log; the UI shows
whether the chain verifies.

Actions: isolate endpoint · revoke credential · disable service account · block network indicator ·
pause noncritical workload · trigger incident-response workflow.

## License Savings Intelligence

Deterministic arithmetic over paid, assigned and 30-day-active seats, billing terms, minimum
commitments and notice deadlines. Synthetic totals: 849 unused seats; **estimated avoided
expenditure** of CAD 426,972/yr from unused seats, CAD 225,120/yr from renewal reductions,
CAD 64,800/yr from downgrades, of which CAD 2,280 is realisable this quarter (only monthly-billed
seats can be removed now). Unit prices are confidential: without a procurement grant, totals are
rounded to the nearest CAD 1,000. **Savings are never presented as revenue.**

## Tests

`backend/tests/test_defense.py` (29 tests: no over-claiming, correlation ≠ causation, alert
permissions, containment end-to-end, protected OT refused, expired approval, conversation never
executes, licence arithmetic and contract constraints, briefings) and `e2e/command.spec.ts`.
