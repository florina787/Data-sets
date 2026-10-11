# Business measures

The dashboard (`GET /api/dashboard`) derives every figure from persisted cases, approvals, executions,
recovery observations and audit events. It shows sample sizes and says "no data" rather than inventing values.
**Synthetic, fast-forwarded workflows cannot substantiate real-world savings.**

| Measure | Numerator / value | Denominator | Inclusion & window | Time basis | Implemented |
|---|---|---|---|---|---|
| Investigation time (median, p95) | seconds from `INVESTIGATION_STARTED` to first `RECOMMENDATION_READY` / `NEEDS_INFORMATION` / `ESCALATED` | investigations | all in scope | wall-clock of agent effort | Yes |
| Time to verified resolution | minutes from case creation to the `RESOLVED` recovery check | resolved cases | cases with a RESOLVED observation | **mixed**: includes seed offsets and simulated recovery windows — not real elapsed time | Yes (labelled) |
| Repeat-contact rate | accounts with ≥ 2 contacts (interactions + cases) | accounts with ≥ 1 contact | `REPEAT_CONTACT_WINDOW_DAYS` (30) | calendar | Yes |
| Escalation rate | cases that reached `ESCALATED` | investigated cases | all | — | Yes |
| Approval turnaround | minutes from approval request to decision | decided approvals | all | waiting time (human) | Yes |
| Dispatch appropriateness | dispatches matching labelled allowed actions | dispatches | labelled evaluation cases only | — | In evaluation report |
| Evidence support | citations that resolve and support their claim | citations used | per case | — | Citation validator + evaluation |
| Cost per investigated case | estimated model cost from provider usage × configured price | investigated cases | LIVE/HYBRID only; DEMO shows $0 and says no calls were made | — | Yes (no live data yet) |

Time categories are kept separate: **agent effort** (node latencies in the audit trail), **waiting time**
(approval turnaround), **simulation time** (recovery windows flagged `simulation_time: true`) and **wall-clock**.

## Assisted vs baseline comparison

The evaluation runner compares the assisted workflow with a naive heuristic baseline on the same 11 labelled cases
(action selection only). It shows what the labels reward; it is not a measurement of human specialists. A real
comparison needs the same cases worked by specialists with and without the tool, timed, with missing data reported.

## Business-case formula (for a future pilot, not computed here)

```
annual value = eligible cases × validated minutes saved per case × approved loaded labour cost per minute
             − (operating cost + implementation cost amortised)
```

Rules: "minutes saved" must come from a controlled pilot, not from this prototype; avoid double counting
(e.g. a prevented repeat contact and the handling time of that contact); report realised ROI only from production
outcomes. No ROI is claimed from synthetic outcomes.
