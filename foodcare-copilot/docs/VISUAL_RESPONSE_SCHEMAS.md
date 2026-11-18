# Visual Response Engine — schema 1.0

Jerry never sends HTML, SVG or code to the browser. It sends **typed visual objects** that the
server validates (`backend/app/visuals.py`, pydantic discriminated union on `kind`) and the
browser renders with fixed components (`apps/control-room/src/components/visuals/VisualRenderer.tsx`).

* Each visual is validated on its own; an invalid one is dropped and logged, the rest still render.
* All string fields have length limits; lists have size limits.
* Every visual carries `provenance`: `verified`, `operational_record`, `modeled` or `synthetic`,
  shown as a chip on the card.
* Every visual has a **Show data** toggle that renders the same values as a table (text alternative).
* Missing data is shown as missing (`Waterfall.missing`), never as zero.

## Kinds

| kind | Key fields | Used for |
|---|---|---|
| `kpis` | `items[≤8]{label,value,delta,status}` | Pulse, briefings, savings totals |
| `bar` | `unit`, `items[≤30]{label,value,note}`, `highlight` | Sales, waste, budget used |
| `line` | `unit`, `points[≤60]` | Trends |
| `waterfall` | `unit`, `steps[≤12]`, `missing` | Losses, licence savings |
| `forecast_band` | `bands[≤6]`, `method`; provenance always `modeled` | Scenarios |
| `table` | `columns[≤8]`, `rows[≤50]` | Detail lists |
| `flow` | `nodes[≤40]{id,label,group,state,detail}`, `edges[≤80]` | Architecture, dependencies, attack exposure |
| `motion_story` | `story` ∈ architecture / supplier_disruption / farm_to_market, `steps[≤12]`, `disclaimer` | Motion Stories |
| `timeline` | `events[≤30]{date,label,provenance}` | Incidents, downtime |
| `plan` | `steps[≤10]{step,owner,approval,evidence}`, `assumptions` | Recommendations |
| `radar` | `axes[3..10]{label,value 0–100}` | Security posture |
| `heatmap` | `rows`, `columns`, `values` 0–4 (none … critical) | Vulnerability exposure, risk |
| `gantt` | `today`, `rows{label,group,status,start,end,milestones}` | Delivery portfolio |

## Actions

`UiAction.type` is one of `download`, `open_globe`, `open_xray`, `open_page`, `open_motion`,
`open_containment`. URLs must match `URL_PATTERN` (same-origin `/api/...` or app routes);
anything else is rejected by validation.

## Rendering rules

* Design tokens: Midnight Navy `#091321`, Elevated `#17283C`, Champagne `#D7B77A`, Teal `#45C5B8`,
  Ivory `#F3F0E9`; risk colours only for risk.
* Graph layout: one column per group when there are at most six groups; otherwise columns by
  dependency depth (split every ten nodes) so labels never pile up.
* Motion Stories respect `prefers-reduced-motion` (all steps shown statically, no autoplay).

Tests: `test_command.py` (schema validation, invalid visuals dropped, URL allowlist),
`e2e/command.spec.ts` (radar, heatmap, waterfall, Gantt render in the browser).
