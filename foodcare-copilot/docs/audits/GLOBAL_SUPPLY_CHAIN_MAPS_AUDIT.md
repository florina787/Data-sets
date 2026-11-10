# Audit: geography, maps and supply-chain visualisation (before "Global Supply Chain Intelligence Maps")

Date: 2026-11-10 · Scope: `foodcare-copilot/` (backend, control-room UI, fixtures, docs) · Status: **audit only, nothing implemented**

## 1. What exists today

| Area | What is there | Evidence |
|---|---|---|
| Map / geospatial libraries | **None.** No MapLibre, deck.gl, Three.js, Leaflet, d3-geo or TopoJSON in any `package.json` or `node_modules`. | `apps/*/package.json` |
| Coordinates | **None.** Nothing in the code or fixtures has a latitude or longitude. | grep for `lat`, `lon`, `geojson` and `projection` finds nothing |
| Countries | **One:** Canada (currency CAD). | `fixtures/enterprise/company.json` |
| Regions | 6 Canadian provinces (ON, QC, BC, AB, MB, NS). Each has a synthetic demand weight, not a location. | `company.json → regions` |
| Facilities | 3 distribution centres (DC-TOR, DC-MTL, DC-VAN), each with the provinces it serves, a lead time and safety days. **No coordinates, factories, farms or markets.** | `company.json → warehouses` |
| Logistics | 3 inbound purchase orders (PO, DC, SKU, units, ETA). **No origin, route, carrier or tracking events.** | `company.json → inbound` |
| Suppliers | Free-text `supplier` and `lot_code` on potato inspection batches, typed by the user. **They are not verified and have no location.** | `memory/schema.py` (migration 3) |
| Quality incidents | Potato inspection batches and items, plus delivery and storefront incidents. **None is linked to a place.** | `inspection_*` tables, `services/incidents.py` |
| Geographic charts | "Revenue by region" horizontal bars on Executive Command, and per-DC stock on Inventory (cards and stock shelf). | `Executive.tsx:58`, `Inventory.tsx`, `StockShelf.tsx` |
| Geographic filtering | A Region dropdown on Sales & Promotions, **kept in the page's own state** so it is lost when you navigate away. A supplier filter on Quality Intelligence. | `Sales.tsx:13`, `QualityIntelligence.tsx:114` |
| Shared selection state | **None.** `AppContext` holds only the user and the guided-demo run. | `context.tsx` |
| Provenance labels | **They exist and can be reused.** Every answer source has a `kind` (`live`, `record`, synthetic, …). The data-sources panel separates "with data", "synthetic" and "not connected". | `enterprise/queries.py:15`, `datasources.py` |
| Forecasting | **None.** Stock risk is a deterministic days-of-cover projection for one campaign. There is no 30/90/180-day model and no uncertainty estimate. | `enterprise/queries.py` |
| Recurrence and history | Quality Intelligence trends inspection grades over time, by supplier. | `quality.py` |
| Agent observability | The Agent Intelligence page (knowledge, context and procedural graphs, activity) and System Observability (metrics, token usage). | `AgentIntelligence.tsx`, `Observability.tsx` |
| Tenancy | **Single tenant.** Demo accounts have roles, but there is no tenant or organisation column anywhere. | `auth.py`, schema |
| Recording | Playwright and Pillow GIF pipeline exist (`e2e/record-media.mjs`, `scripts/make_gifs.py`). `ffmpeg` is available for MP4. | — |

## 2. Pages named in the request, against what exists

| Requested integration | Exists? | Note |
|---|---|---|
| Executive Command | ✅ | Add the globe or map here (do not build a second executive page) |
| Quality Intelligence | ✅ | Add a location column and a "show on map" link |
| Supply Chain | ⚠️ partly | Inventory (stock, DCs, inbound POs) is the closest page. Recommend extending it, **not** creating a new page |
| Financial Impact | ❌ | No page exists. Revenue lives on Executive Command and Sales; there is no exposure or loss model |
| Forecast & Risk | ❌ | No page and no forecasting engine |
| Agent Observability | ✅ | Agent Intelligence + System Observability |
| OriginTrace AI | ❌ | No such component, investigation workflow or name anywhere in the repo |

## 3. Gaps, and what could honestly fill them

| # | Requirement | Gap | Honest way to fill it |
|---|---|---|---|
| 1 | 3D globe | No library | See section 4: Three.js plus offline Natural Earth borders, loaded only on pages that show the map |
| 2 | Arcs between **verified** farms, suppliers, factories, DCs and markets | **There are no verified locations at all.** Any farm, factory or route we draw would be invented | Option A: a clearly labelled **synthetic network** (a fixture marked `synthetic`). Option B: show only the 3 DCs and the regions they serve, positioned at **public city centroids** (Toronto, Montréal, Vancouver), labelled "approximate". The connection is real (`serves`); the coordinates are public geography |
| 3 | Red pulsing quality incidents | Incidents have no location | Pulse only incidents whose batch has a location. Add an optional `site_id` on inspection batches. Unlocated incidents go in a side list and are **not** placed on the map |
| 4 | Regional revenue, exposure, supplier performance, risk | Revenue exists per province (synthetic). There is no exposure or supplier-performance model | Use the existing province revenue (labelled synthetic). Exposure = stock-at-risk × price, from existing data, with the formula shown. Supplier performance = existing inspection grade rates |
| 5 | Animated shipments | **No tracking events exist** | With no events, draw static arcs only. An optional "simulated movement" toggle can be added, off by default, with a permanent "SIMULATED" badge. Nothing should imply live tracking |
| 6 | Zoom: global → country → facility → supplier → batch → incident | Hierarchy data missing | Achievable for country → DC → inbound PO / supplier → batch → potato, once sites exist |
| 7 | OriginTrace AI investigations | Component does not exist | Needs your definition. Proposal: reuse Ask Copilot with a "trace this" prompt plus the context graph, rather than building a new agent |
| 8 | 30/90/180-day risk simulations with uncertainty | No forecasting engine | A transparent **scenario model**: days-of-cover projection plus a Monte Carlo spread on demand, using the history's own variance. Label it "modelled scenario", never "forecast accuracy" |
| 9 | Shared geographic selection | None | `GeoSelection` in `AppContext`, mirrored to the URL (`?geo=CA/ON/DC-TOR`) so it survives navigation and reloads |
| 10 | Camera transitions, glow, tooltips | — | Part of the globe component. Honour `prefers-reduced-motion`: no rotation, instant transitions |
| — | 161 countries, billion-dollar revenue | Today's data is 1 country, CAD, about $0.1M a week | A **configurable scenario** (`fixtures/enterprise/scenario.json`: countries, annual revenue, currency) shown under a "Demonstration scenario, not enterprise results" banner. **Per-country figures cannot be derived without fabricating them.** Recommend showing the scenario only as headline assumptions, with countries shaded as "in scenario footprint", not with invented revenue per country |
| — | Tenant isolation tests | No tenants exist | Requires multi-tenancy: a `tenant_id` column on every table, plus query scoping. **This is a substantial cross-cutting change; recommend a separate phase** |
| — | MP4 recordings | Only GIFs today | Reuse `record-media.mjs` and encode MP4 with `ffmpeg` (already installed) |

## 4. Library evaluation

| Option | Licence | Fit | Concerns |
|---|---|---|---|
| **Three.js** (+ custom globe, or `three-globe`) | MIT | Full control of glow, atmosphere and arcs; no map tiles needed | Adds about 150 kB gzip. Load it **only on map pages** |
| deck.gl `GlobeView` | MIT | Strong data layers (ArcLayer, ScatterplotLayer) | GlobeView is still experimental. Heavier; pulls in luma.gl |
| MapLibre GL JS (globe projection) | BSD-3 | Real map with zoom to street level | Needs **vector tiles**. Hosted tiles usually need an account or paid plan, which conflicts with "no paid services"; self-hosting tiles is heavy |
| **d3-geo + world-atlas** (2D fallback) | ISC | Light SVG world and Canada map, works without WebGL and is accessible | Not 3D |
| Borders data: Natural Earth 1:110m via `world-atlas` | Public domain / ISC | Offline, about 100 kB | Coarse at city zoom (fine for this scale) |

**Recommendation:** use one reusable `<SupplyMap>` component. It renders a Three.js globe when WebGL is available and motion is allowed, and a d3-geo SVG map otherwise (also the default on small screens). Both read the same `GeoSelection` state and the same provenance-tagged layer data from one backend endpoint (`/api/geo/network`). No tile servers and no API keys.

## 5. Decisions I need from you before implementing

1. **The network.** Should it be Option A, a labelled synthetic multinational network (farms, factories and markets in many countries, all marked SYNTHETIC)? Or Option B, only the real demo entities (3 DCs and 6 provinces) at approximate public city coordinates?
2. **The 161-country / billion-dollar scenario.** May it appear as headline assumptions only (recommended), or should it also be split per country (necessarily synthetic, labelled)?
3. **OriginTrace AI.** Should it be built on Ask Copilot and the context graph (recommended), or as a separate agent? Please confirm the name and scope.
4. **New pages.** Financial Impact and Forecast & Risk do not exist. Should they be new pages, or new tabs on Executive Command and Inventory (recommended: no duplicate dashboards)?
5. **Multi-tenancy.** Is it in scope now (large change), or a later phase?
6. **Simulated movement toggle.** Do you want it (off by default, permanently labelled), or should it be omitted entirely?

## 6. Proposed phases after approval

1. A geo data model plus `/api/geo/network` with provenance on every node and edge, a shared `GeoSelection` mirrored to the URL, and the 2D map, wired into Executive Command, Inventory and Quality Intelligence.
2. The Three.js globe (lazy-loaded), with arcs, pulses for located incidents, camera transitions and reduced motion.
3. Scenario risk simulation at 30, 90 and 180 days with uncertainty bands, plus financial-exposure overlays.
4. Tests: geographic filter round-trips, provenance labels on every layer, accessibility (keyboard, table view), responsive layout, and a render-time budget. Tenant isolation follows the tenancy decision.
5. GIF and MP4 recordings, plus a README section.
