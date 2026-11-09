# Commercial roadmap (not built)

Everything below is a **plan**, not a capability. Nothing here has been implemented, measured or sold; no market
position, recovered-revenue figure or prediction accuracy is claimed. Each item names the evidence it would need.

| Capability | What it would do | Builds on | Evidence required before claiming it works | Main risk |
|---|---|---|---|---|
| **Customer health graph** | Account ↔ invoices ↔ tickets ↔ CSAT ↔ contacts as a graph; health score per account | account snapshot, CSAT, support_tickets | resolved account identity (200 names / 3,815 ids); a health score validated against later renewals | identity errors propagate through the graph |
| **Predictive churn** | Probability an active account churns in the next N months | accounts table | churn **dates** (the ledger has only a snapshot flag), a time-split back-test with calibration; leakage-safe features | today's data cannot support it — would be overfitting a snapshot |
| **Private deployment** | Single-tenant install (container + local Qwen) inside a customer VPC | local-first design, no API keys, read-only DB | hardened container, SSO, audit export, load test, security review | GPU/CPU sizing for larger models |
| **Connector marketplace** | Supported adapters for Stripe, Chargebee, Zuora, Salesforce, HubSpot, NetSuite | `app/sources` raw contract + mapping YAML | per-connector contract tests against sandbox accounts; incremental sync; rate-limit handling | API drift; per-connector maintenance cost |
| **Human-approved workflows** | Promote a previewed source into the ledger, or push a finding to collections/billing, only after an approver signs off | integration preview, investigation status | approval audit trail, role-based permissions, reversible promotion | write paths break today's read-only guarantee — needs its own threat model |
| **Statistical anomaly detection** (e.g. Isolation Forest) | Rank unusual invoices for review | pricing check, leakage checks | labelled review outcomes to measure precision; explanations per flag | on this synthetic ledger the deterministic check finds 0 pricing errors, so a model would mostly flag big Enterprise deals |
| **LLM → QueryPlan routing** | Qwen maps phrasing to the metric catalog (JSON) instead of free SQL | semantic catalog, eval harness | beat the keyword planner on a held-out phrasing set without losing the six stakeholder answers | latency on CPU |

## Built since this roadmap was written
* **Semantic Spine** (knowledge graph → context graph → procedural graph → trace & learn) — `app/semantic_graph.py`,
  page `#/spine`, tests `tests/test_semantic_spine.py`. The "learn" step only *proposes* (e.g. "add support tickets to the
  metric catalog"); a person decides. Building it surfaced a real gap — "delete all refunds" was not refused — now fixed
  and covered by tests.
