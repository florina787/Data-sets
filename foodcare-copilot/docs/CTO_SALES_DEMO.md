# CTO sales demo — "Your Enterprise. Under Your Command."

Open **Overview → Guided CTO demo** (`/demo`), sign in as **Eli Novak (Engineer)**, pick a track,
press **Start**, then **Next question**. Every line is sent to the real Jerry in one continuous
conversation, so follow-ups and context work as they would for a customer. Nothing is executed.

Before the demo: `scripts/reset_demo.sh`, then `scripts/start.sh`; open http://127.0.0.1:8700.

## Track 1 — Your Enterprise. Under Your Command. (≈ 6 min)

| # | Say | What the room sees | Talking point |
|---|---|---|---|
| 1 | Jerry, show me my enterprise. | KPI tiles, priorities | One conversation instead of ten dashboards |
| 2 | Which factories need attention? | Bars + table | Cited, read-only data |
| 3 | Where did the information come from? | X-Ray panel | Every answer is inspectable |
| 4 | How do you connect to Databricks? | Architecture flow, real connector states | Honest: "adapter available", not "connected" |
| 5 | How do you interact with Kubernetes? | Same, Kubernetes read-only | get/list only, no kubectl from chat |
| 6 | Hide confidential details. | Policy chips | Enforcement is server-side; there is no reveal button |
| 7 | Animate how these systems work together. | Motion Story + GIF download | Explains the architecture to non-engineers |
| 8 | What do you recommend? | Action plan with owners and approvals | Recommends; never acts |
| 9 | Prepare a board-ready PDF. | Download | Real file, policy-filtered |

## Track 2 — Enterprise Defense Command (≈ 5 min)

Are we under attack? → Which business applications are affected? → Can we isolate the affected
endpoint? → Who must approve containment? → Which licenses are unused? → Which renewals should we
renegotiate? → Prepare a security and savings board report.

Say out loud: *the security data is simulated; Jerry separates facts from hypotheses; containment
is preview-only with step-up and two-person approval; protected refrigeration and production
lines are refused; savings are avoided expenditure, not revenue.*

## Track 3 — Cross-functional Team Intelligence (≈ 4 min)

Summarise every team → What is Marketing building? → Which initiatives are blocked by data
engineering? → Which projects exceed budget? → What decisions need my approval this week? →
Board-ready delivery briefing PDF.

The story: Marketing's loyalty relaunch is blocked by Commercial pricing approval and two
Technology deliveries; the CTO sees it, and the decision, in one place.

## Honesty rules for presenters

* Say "synthetic company" and "simulated security telemetry" at the start.
* Don't claim live Databricks, Kubernetes, SIEM or billing connections; the Connect page shows the truth.
* Don't claim measured user-research results; see `CTO_UX_RESEARCH.md` for what is a hypothesis.

Browser check of the defense track: `e2e/command.spec.ts`. Screenshots: `docs/screenshots/40–43-*.png`.
