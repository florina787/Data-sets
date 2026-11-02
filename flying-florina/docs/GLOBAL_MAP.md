# Global Aerospace Intelligence map

Code: `frontend/src/features/global/` (page, MapLibre/SVG map), `backend/app/api/routes_global.py` (`/api/global/map`,
`/api/global/timeline`, `/api/global/search`, `/api/global/report`).

## Rendering — no paid or online map service

* **Globe** (default on desktop): MapLibre GL JS v6 with `projection: globe` (upgraded from v5 during this release to clear a critical npm advisory; its worker is bundled by Vite).
* **2D**: the same MapLibre map with Mercator projection.
* **Lite**: an SVG equirectangular map with identical encoding and click targets, used automatically when WebGL is unavailable and by
  default on phones (< 640 px) to save battery and CPU.

Country outlines are Natural Earth 1:110m (public domain) bundled via the `world-atlas` npm package, so there is no tile server, no
API key and no network request; the e2e suite aborts any non-loopback request and the map still renders. deck.gl was not needed for
~40 points and ~70 links.

## Layers

| # | Layer | Colour | Size |
|---|---|---|---|
| 1 | Facility overview | facility type (MRO, repair, warehouse, manufacturing) + suppliers | removal demand |
| 2 | Component health | mean projected health of tracked units (emerald → amber → red) | units reaching end of life within the horizon |
| 3 | Supply chain | supplier late-delivery probability; links coloured the same, width = supply share | open orders |
| 4 | Inventory forecast | highest stockout probability at the site | number of short categories |
| 5 | Operational disruptions | synthetic notices by severity | severity |
| 6 | Recovery intelligence | remaining disruption (green = restored); sites by capacity cut | capacity cut |

## Predictive timeline

TODAY · +7 · +14 · +30 · +60 · +90 days. `/api/global/timeline` returns all six horizons at once (about 240 KB), so moving the slider
re-encodes locally and point sizes tween for 450 ms; there is no request per step. Every value per horizon comes from the forecasting
engine or the reorder simulation (see [FORECASTING_ENGINE.md](FORECASTING_ENGINE.md)); assumptions and data freshness are shown under
the map and returned in the API.

## Interactions

Zoom/rotate (navigation control), search (city, facility, supplier → fly-to), category filter (re-queries forecasts for one category),
six layers, region comparison (two regions side by side), facility drill-down (demand interval, health, units due, workload, cost,
shortages, history + forecast chart), links to the digital twin and forecasting views, supplier drill-down linking to the delay
simulator, disruption drill-down linking to the resilience simulator, and a Markdown report export (policy-checked, audited).

## Safety and labelling

All locations are fictional organisations in civilian cities. There are no military sites, no defense assets, no real-time positions
and no drone routes. Disruption notices are labelled "synthetic scenario notice". A "SYNTHETIC DEMONSTRATION DATA" badge is always
visible.
