# Metrics and business case

The app computes the metrics below from its own persisted records (`GET /api/metrics/process`, shown on the Change
Workspace). In this repository they describe **synthetic demo runs only** and must not be read as operational
evidence.

| Metric | Numerator | Denominator | Window | Exclusions | Source |
|---|---|---|---|---|---|
| Time from requirement to review | change creation → first `REVIEW_REQUIRED` transition | per change | all time | changes never reaching review | audit_events |
| Clarification cycles | sum of answer cycles | answered clarifications | all time | unanswered | clarifications |
| Evaluation time | job duration (ms) | per succeeded run | all time | failed/cancelled | evaluation_runs |
| Regressions caught before release | runs failing `G-NO-REGRESSION` | count | all time | none | evaluation_runs |
| Rejected or inconclusive releases | FAIL/INCONCLUSIVE evaluations + rejected release approvals | count | all time | none | evaluation_runs, approvals |
| Approval turnaround | `REVIEW_REQUIRED` → release approval | per approval | all time | rejected | audit_events |
| Rollback time | rollback approval → simulated completion | per executed rollback | all time | failed | rollback_records |
| Cost per change | recorded LLM cost (dated price config) | changes | all time | infrastructure cost not tracked | agent_invocations |

## Separating synthetic from real evidence

* Durations here measure software running against fixtures. They say nothing about engineering effort.
* “Regressions caught” counts a regression that was seeded on purpose.
* Cost is $0 in deterministic mode. In live mode it is computed from recorded tokens and
  `config/llm-prices-2026-10-06.json`; check those prices before relying on them.

## Building a value estimate (only after validation)

1. Validate eligible change volume per year (changes to models or configs that need governed release).
2. Measure the actual effort per change today (reviewer and engineer hours) and with the pilot workflow.
3. Measure avoided rework and avoided incidents: regressions caught pre-release, weighted by observed historical
   impact.
4. Subtract operating costs: hosting, LLM usage if enabled, maintenance, reviewer time added by the controls.

Do not claim conversion uplift, fewer returns or bias reduction without an appropriately designed study (for example a
controlled experiment with pre-registered outcomes).
