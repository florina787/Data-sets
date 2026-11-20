# Visualization system

## Design language

The overall system uses a light lavender canvas with a fine grid, indigo `dome` accents, isometric layered tiles and black pill CTAs. Each area takes a deliberate variation:

| Area | Treatment |
|---|---|
| Copilot layer (Overview) | Dark navy with a glowing horizon arc, showing Florome as a layer over the copilots |
| Governance + system metrics | Dark-to-blue gradient, oversized condensed headline, terminal-style verified-hash lines |
| Sources | Soft lavender glass cards |
| Integrations | Ember-on-black "connect" hero, isometric cube network with Florome lit at the core, bold colour tiles per platform group |
| Actions ledger | Dark fintech-style ledger: big number, Overview/Transactions/Alerts tabs, range chips, area chart |

All visuals are original SVG/CSS; no third-party artwork is embedded. The illustrations are data-driven. For example, a cube or tile is only shown as verified if `/platforms` says so.

## Implemented visualizations

| Spec name | Page | Data | Interactions |
|---|---|---|---|
| Enterprise Digital Nervous System | Nervous System | `/topology` | Zoom/pan, minimap, search, platform filters, impact-only, incident roles from RCA, drill-down panel |
| RCA Causality Constellation | RCA | `evidence_graph` | Supports (solid) vs contradicts (dashed), hide disproven, click → raw evidence + hash check |
| Deployment Time-Travel | RCA | RCA timeline | Lanes per resource, anomalies in red, root-change and detection markers, zoom slider, click → evidence |
| Action Command Center | Actions | plans, executions | Approve/reject, execute/resume, validation checks, ledger |
| AI Money River | FinOps | `/finops/costs` | Sankey, period switch, focus node |
| Governance Trust view (partial) | Governance | policy, audit, metrics | Emergency stop, audit chain, route latency |

**Not built yet:** Risk Weather Map, Architecture Multiverse, AI Duplication Galaxy, DevOps Bottleneck River, Investment Gravity Field, full Trust Orbit graph, Model Drift Seismograph, Decision Evidence DNA.

Accessibility: `prefers-reduced-motion` is respected and charts have ARIA labels. Loading, empty and error states are shared components.
