# FLO product: business domains, KPIs, experience and decision memory

## B. Business domains and measurable KPIs

FLO does **not** claim productivity improvements. Each KPI below is defined so it can be *measured* after adoption;
the "Measured in FLO today" column shows what this demonstration actually instruments (on synthetic data).

| Domain | Objective | KPI (definition) | Measured in FLO today |
|---|---|---|---|
| Executive & Corporate Intelligence | Decision speed, financial visibility | Time from question to evidence-backed answer (p50/p95 workflow latency); % of executive questions answered with lineage | Workflow latency per trace (AI Ops); lineage on every chart |
| Investment & Portfolio Intelligence | Analytical consistency, research productivity | % of figures sourced from the semantic layer; number of concentration breaches detected vs reviewed | Semantic metric ids on every dataset; breach counts (Risk Intelligence) |
| Wealth Advisor Intelligence | Advisor efficiency, client service quality | Advisor prep time per review (baseline vs pilot, survey + telemetry); follow-ups closed within SLA | Meeting-prep workflow latency; open follow-ups on Advisor Home |
| Client & Distribution Intelligence | Retention, flows | 12-month client retention; organic growth rate; net flows by vehicle | `clients.retention`, `flows.net`, AUM waterfall |
| Enterprise Risk & Compliance | Governance | Exceptions open > SLA; % AI communications approved before send; approval turnaround | Exceptions, approvals report, audit chain verification |
| AI Governance & Operations | AI operating efficiency | Cost per successful workflow; eval pass rate; tool failure rate; policy denials | AI Ops dashboard, evaluation report, release gate |

## U/V. Experience and visual analytics

* Default dark theme with the specified palette (background `#0B1220`, sidebar `#101B2D`, cards `#162338`, accent gold
  `#D4AF37`); light theme toggle. Series colours use an 8-slot categorical palette **validated** (CVD/contrast checks)
  against the card surface; gold is reserved for brand accents and status colours (positive/warning/critical) for state.
* Layout: persistent role-aware sidebar, header with global search, date-range and asset-class filters, notifications
  (pending approvals), data freshness, language selector, Ask Flo side panel, governance status (policy version, PDP,
  telemetry mode), export controls.
* Every chart card (`frontend/src/components/ChartCard.tsx`) provides hover tooltips, drill-down or filtering where it
  applies, **table view** (accessibility), **export** (PNG + CSV), **source lineage & methodology** (semantic metrics,
  adapters, dataset version), **last refresh time** and **Explain with Flo**.
* Chart forms implemented: line, area (stacked), bar, stacked bar, donut, waterfall (AUM attribution, sector
  contribution), heatmap (risk, correlation), treemap (profitability, sectors), scatter/bubble (risk-return, decision
  timeline, service timeline), geographic choropleth (MapLibre, bundled country shapes, no tile server), tornado
  (sensitivity), agent workflow graph. Sankey and risk-matrix variants are covered by the waterfall/heatmap forms; a
  dedicated Sankey is not implemented (see limitations).
* No dual-axis charts: margin and revenue yield are separate charts; revenue/expenses share one CAD axis.
* Keyboard: skip link, focus rings, sortable tables with keyboard row activation, ARIA labels on charts and controls.

## X. Multilingual & extensibility

* Languages: English, French, Hindi, Tamil, Korean, Spanish — UI navigation labels, answer headings, language detection
  (script + stop-words), glossary-based multilingual query expansion, and **approved communication templates in all six
  languages** with translation validation (numbers, dates, currencies, preserved terms such as FLO/ETF/RRSP).
* Free-text narrative translation needs a real translation-capable model; in mock mode Ask Flo answers in English with
  a localized heading and an explicit note, preserving numbers and citations. This is stated in the UI.
* New business domains plug in by registering agents (`harness/registry.py` decorator) and tools (`agents/tools.py`);
  the harness, gateway, policy engine and graph supervisors need no change.

## W. Executive Decision Memory

Records decision, owner, date, rationale, evidence, assumptions, expected impact, target KPI (baseline/target/observed),
deadline, approval, follow-ups and outcome. Answers "which decisions delivered measurable value", "which initiatives are
behind schedule", "what assumptions were used" and "which commitments remain unresolved". Decision D-0001 (fee
repositioning) is **measured from the data** with an uncontrolled comparison group, and every answer carries the caveat
that associations are not causal impact. New decisions and outcomes are recorded through approval-aware, audited APIs.
