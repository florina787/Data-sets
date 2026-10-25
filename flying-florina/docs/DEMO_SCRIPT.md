# Demo scripts (run fully offline)

Before you start: `make demo`, open http://127.0.0.1:5173, and optionally **Settings → Reset demo data**.
Say up front: *"Everything you see is synthetic, local, and independent of IFS. No paid APIs, no internet."*

## 3-minute version

| Time | Do | Say |
|---|---|---|
| 0:00 | Mission Control (Maintenance Planner). Point at the badges | "Synthetic data, demo mode, no live IFS connection, a local rules engine. Nothing leaves this laptop." |
| 0:15 | Ask: *Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options.* | "The router picked the maintenance graph. Telemetry, retrieval and history ran in parallel. This log is the real execution record." |
| 0:45 | Scroll: vibration chart, hypotheses, parts table, recovery options, citations | "Hypotheses, not a diagnosis. MAIN-HUB stock is rejected because ERP says 2 and the physical count says 0. The gray-market alternate is rejected because no authority document exists. And this supplier bulletin tried to inject an instruction: it was quarantined, and the export it asked for was denied." |
| 1:30 | Ask: *Export restricted maintenance records to my personal email.* | "Denied by POL-004 before any tool ran: zero executions, logged in a hash-chained audit trail." |
| 2:00 | Switch persona to Reliability Engineer → Trust Center → Approval Queue → Approve | "The planner could not approve their own draft. A different authorized person approves; execution re-checks policy and a replay is rejected." |
| 2:30 | Legacy X-Ray (Enterprise Architect) → Generate safe read-only bridge → Run tests | "From a 20-year-old schema to a typed, read-only API and MCP tool, with 14 passing contract, security and MCP tests. No rewrite of the core." |

## 8-minute version (four acts)

**Act 1 – Legacy Transformation (2 min).** Persona: Enterprise Architect. Legacy X-Ray → *Import metadata* →
`fixtures/legacy/mro_core_legacy.sql`, then `fixtures/legacy/nightly_inventory.csv`. Show the dependency map
(click APP-03 and a dashed unknown), hotspots (ERP simulator, MRO app, legacy DB), findings (`/admin/sql`, SSRF
webhook, missing PKs, stale counts), and unknowns U1–U5. *Recommend modernization path* → Current/Target/Diff/Roadmap.
*Generate safe read-only bridge* → *Run tests* → 14 passed → *Download bundle*. Explain: strangler facade +
anti-corruption layer; read-only view; MCP is an agent interface over a governed API, not the security boundary.

**Act 2 – Operational AI (2 min).** Persona: Maintenance Planner. Ask the AC-204 question. Open *Show agent graph*.
Walk through the timeline (timestamps are real; *Run options → Demo pacing* slows it down, and is disclosed).
Click *Compare delay scenarios*; change delays to `24, 60, 72` → *Recompute*: the extra hangar-slot wait makes
downtime jump non-linearly. Point at formulas and assumptions.

**Act 3 – Defense Trust (2 min).** Ask the export question → DENY, POL-004, 0 executions. Trust Center →
*Security Test Lab* → *Run all 12 scenarios* (as Security Officer) → 12/12. *Evidence Ledger* → *Verify chain*.
Approve the AC-204 work order as Reliability Engineer; execute as Planner; click *Replay write* → denied POL-005.
Optional: *Incident / Kill Switch* → activate, show a query is denied (POL-009), release.

**Act 4 – Executive Value (1 min).** Persona: Executive. Ask *Create a 90-day modernization pitch for this customer.*
Show the roadmap, risks, API/MCP strategy and ROI ranges; edit an assumption → *Recompute ROI*; download the PDF brief.
Close: "Every number came from data you can inspect or an assumption you can edit. Measure it in a pilot."

## Questions to expect
* *Is this connected to IFS?* No. The ERP fixtures are fictional "IFS-like" projections; a real integration would use documented, licensed APIs (R7).
* *Where is the LLM?* Not needed for the demo. Routing, policy and analytics are deterministic; an optional local model may only rephrase text, never decide.
* *Is it secure enough for CUI?* No. See SECURITY_LIMITATIONS.md: demo identity, process-level egress guard, tamper-evident (not tamper-proof) audit.
