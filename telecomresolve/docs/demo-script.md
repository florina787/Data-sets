# Five-minute demonstration script

Setup: `make reset` (or `POST /api/demo/reset` as the supervisor), then open the UI.

| Time | Step | What to show / say |
|---|---|---|
| 0:00 | Disclose | Point at the banner: independent prototype, synthetic data. Header shows **Generation: DEMO (deterministic rules)** and **Connectors: SIMULATED**. Nothing is a live model or a live system. |
| 0:30 | Open the case | Persona **Ava (Specialist)** → *Copilot Workspace* → **C-1003**. Read the complaint. Right panel: two earlier calls, both with modem restarts, one remote line check reporting marginal SNR. |
| 1:00 | Investigate | *Run investigation*. Node chips (triage → evidence → diagnosis → planning) tick as persisted audit events arrive over SSE. |
| 1:45 | Evidence | Evidence panel: measured observations vs reported statements. Click **[DIAG-SNR]** — the dialog shows the 23 cited samples and "Verified against source". Note `INC-7001` is *not* listed as a cause: it is on another access node (proximity only). |
| 2:30 | Recommendation | *Create technician dispatch (simulated)*: purpose, prerequisites, uncertainty ("exact fault location not established; appointment availability unknown"), risk high, supervisor approval required. *Earlier interventions*: modem restart recorded as already tried — **not repeated**. |
| 3:00 | Approve | Ava sees she cannot approve (proposer, wrong role). Switch to **Emma (Supervisor)** → *Approve*. Approval is bound to the payload hash and expires. |
| 3:30 | Execute & verify | Switch to **Dev (Field coordinator)** → *Execute (simulated)*. Status becomes *Recovery not yet verified* — an API success is not recovery. *Verify recovery*: 6 healthy post-action samples (simulated, fast-forwarded) → **Resolved**. |
| 4:00 | Audit | *Audit* tab: hash chain intact, replayed status matches, reconstructed recommendation with its evidence excerpts. |
| 4:20 | Abstention | Open **C-1004** → *Run investigation*: diagnostics are 5 days old, the line test is unavailable → **Insufficient evidence** with specific questions. No diagnosis is invented. |
| 4:45 | Close | *Evaluation* tab: release gates, 13 labelled synthetic cases, and the caveat that labels and rules share an author. What would need validating before a real pilot: the discovery worksheet. |

## Additional demonstrations

- **Active outage (C-1001):** mapped access node + overlapping incident window → *Associate case with incident*;
  dispatch shown as *Not permitted* (active incident on mapped path). After execution, verification stays in
  **Monitoring** while the incident is active.
- **Contradictory evidence (C-1005):** customer reports evening drops; 23 healthy samples; a nearby incident on a
  different access node is flagged *proximity only* → **Escalated** for analyst review.
- **Prompt injection (C-1008):** a chat note instructs the AI to apply a $500 credit and dispatch without approval.
  The note is quarantined (red chip), the recommendation is power/ventilation troubleshooting, and the refusal
  section explains the ignored instructions.
- **Guaranteed restoration (C-1007):** the customer demands a 5pm guarantee and a credit. Both are refused with
  citations (no published estimate on INC-7001; credits disabled). Ask the chat "When will it be restored?" for a
  policy answer.
- **Denied approval (C-1009):** as Emma, reject with a reason → **Rejected**; execution is refused.
- **Duplicate execution (C-1011):** execute twice — the second call with the same key replays; a new key is refused.
- **Cross-tenant (C-1012):** as Ava, open `#/workspace/C-1012` → "Case not found in your scope"; as the supervisor,
  the *Audit* tab shows the `ACCESS_DENIED` event.
