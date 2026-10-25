# Flying_Florina — one-page pilot brief

**From legacy systems to trusted industrial intelligence.** *Independent concept demo — not affiliated with or endorsed by IFS. Synthetic data.*

**Problem.** Sustainment decisions depend on evidence spread across an ERP, an MRO application, a 20-year-old database,
nightly CSV files and a document library that disagree (in the demo: ERP shows 2 isolator kits on site, the physical count shows 0).
Assembling evidence is slow, and AI assistants that can act are a governance risk.

**Approach.**
1. **Wrap, don't rewrite**: read-only typed adapters and narrow MCP tools over approved views and documented APIs.
2. **Agents assemble, humans decide**: parallel agents gather telemetry, evidence, parts and technician availability, then draft a plan; approvals enforce separation of duties.
3. **Executable trust**: deny-by-default policy evaluated before every tool call, prompt-injection containment, kill switch, hash-chained audit.

**90-day pilot.** Days 0–30: answer unknowns, read-only DB role, firewall `/admin/sql`, classify documents.
Days 31–60: MCP tool over the adapter, validated batch bridge, pilot the investigation workflow with approval gates.
Days 61–90: facade + anti-corruption layer for the Java ERP service; decide on CDC and vendor ERP projections from measured results.

**Value model (assumptions, editable).** Benefits from reduced manual reconciliation, small unscheduled-downtime
reductions and avoided rework, against pilot engineering and run costs. $0 incremental software licenses.
Shown as a range in the Executive Value Studio; validate with pilot measurements.

**Proof in the demo.** 102 backend tests, 13 browser tests, 14 generated-adapter tests, 12/12 security scenarios,
offline check with 0 egress attempts. Exfiltration request → DENY (POL-004), 0 tool executions.

**Not claimed.** Live IFS connectivity, certifications or accreditation, airworthiness decisions, predictive accuracy, guaranteed savings.
