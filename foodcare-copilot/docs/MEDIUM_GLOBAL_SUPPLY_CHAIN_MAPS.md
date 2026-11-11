# I Built a Cinematic 3D Supply-Chain Globe for a Food Copilot, and Made It Refuse to Lie

*How an AI copilot for food manufacturing got a 161-country supply-chain globe, why the very first deliverable was an audit instead of code, and the engineering choices that keep a beautiful map honest.*

> **How to publish:** paste this into Medium's editor (or import it with Medium's "Import a story"). The images and videos below link to the public GitHub repository. Medium shows GIFs inline; for the MP4s, upload them as video or link to them.

![A 3D globe of a synthetic food supply network: glowing coastlines, curved supply routes and red quality-incident markers, flying from the whole world to Peru and into a single site](https://github.com/florina787/Data-sets/blob/claude/new-session-pahp8j/foodcare-copilot/docs/media/globe.gif?raw=true)

---

## The request

The brief arrived as a wish list most dashboard builders would love:

> *A cinematic interactive 3D globe. Animated, curved supply-chain connections between farms, suppliers, warehouses, factories, distribution centres and markets. Red pulsing risk indicators for quality incidents. Regional revenue, financial exposure, supplier performance and operational risk. Zoom from the global network to a country, a facility, a supplier, a batch and an individual incident. 30-, 90- and 180-day risk simulations with uncertainty. An illustrative multinational food enterprise serving 161 countries with billion-dollar revenue.*

The same brief also contained the sentence that shaped everything else:

> *Never fabricate country-specific revenue, supplier locations, shipping routes or financial outcomes… The 161-country footprint and billion-dollar revenue scenario must be configurable. Do not hard-code fictional metrics as factual enterprise results.*

Those two halves pull against each other. Globes are persuasive. A glowing arc from a farm in Peru to a factory in Portugal *looks* like knowledge. If the arc is invented and nothing says so, the most beautiful screen in the product becomes its most dangerous one.

This article explains how both halves were met. It covers the audit, the data model, the 3D and 2D rendering, the risk simulation, the "OriginTrace" investigation flow, the testing, and the reasons behind each choice.

---

## Step 0: audit before you build

The brief said: *"First deliver an audit identifying existing map functionality and missing capabilities. Implement only verified gaps after approval."* That is good engineering hygiene, and here it found something important.

The project, **Flo & Jerry — Food Copilot 2.0**, is a FastAPI + React prototype. It answers questions about sales, stock, compliance and potato quality, with a citation on every number. Searching the repository turned up:

| Looked for | Found |
|---|---|
| Map libraries (MapLibre, deck.gl, Three.js, Leaflet, d3-geo) | **None** |
| Latitude / longitude anywhere | **None** |
| Countries | **One:** Canada, 6 provinces with demand weights |
| Facilities | 3 distribution centres, **no coordinates** |
| Routes / shipments | 3 purchase orders, **no origin, carrier or tracking** |
| Suppliers | A free-text field on potato inspections |
| "Supply Chain", "Financial Impact", "Forecast & Risk", "OriginTrace" pages | Inventory existed; **the other three did not** |
| Multi-tenancy | **None** (single tenant, roles only) |

So the "verified farms, suppliers, factories" the brief mentioned **did not exist**. Neither did the 161 countries or any tracking events. Every one of those would have to be invented, and invented things must carry a label.

The audit ended with six decisions only the product owner could make. The answers were:

1. **The network:** a *synthetic global network* (rather than only the few real demo entities).
2. **The scenario:** a *per-country synthetic revenue split*, labelled synthetic.
3. **New pages:** none. *Financial Impact* and *Forecast & Risk* became **tabs on existing pages**, and *OriginTrace* was built on the existing copilot.
4. **Multi-tenancy:** a **later phase**.

The audit is committed in the repository as `docs/audits/GLOBAL_SUPPLY_CHAIN_MAPS_AUDIT.md`. Writing it took less time than building the wrong thing would have.

---

## Step 1: four kinds of truth

The core design decision is a vocabulary. Every country, site, route, incident and simulation result carries one of four **provenance** labels:

| Label | Meaning | Count in the default scenario |
|---|---|---|
| **Verified** | Confirmed enterprise data | **0** |
| **Operational record** | Something that really happened in this app (your own inspection) | 0 until you inspect a batch |
| **Modelled** | A computed scenario about the future, with uncertainty | Every risk band |
| **Synthetic** | Generated for the demonstration from a fixed recipe | 462 items |

The legend under the map shows all four labels **with their counts, including the zero**. A visible "Verified: 0" is the most honest number on the screen. A gold banner above the map carries the scenario's own disclaimer: *"Demonstration scenario… They are not verified business facts."*

A backend test makes this rule enforceable, not just a convention:

```python
def test_every_item_carries_provenance_and_nothing_claims_to_be_verified(platform):
    net = geo.network()
    for item in (*net["nodes"], *net["edges"], *net["incidents"], *net["countries"]):
        assert item["provenance"] in geo.PROVENANCE
    assert net["provenance"]["verified"]["count"] == 0
    assert all(n["name"].startswith("Synthetic ") for n in net["nodes"])
    assert net["tracking"]["events"] == 0 and "SIMULATED" in net["tracking"]["note"]
```

Even the site names begin with "Synthetic", as in *Synthetic factory Portugal 03*. If one of them leaks into a screenshot in a slide deck, it still announces itself.

---

## Step 2: a configurable, reproducible synthetic world

The scenario lives in one small JSON file, `fixtures/geo/scenario.json`:

```json
{
  "name": "Illustrative multinational food enterprise",
  "countries": 161,
  "annual_revenue": 2400000000,
  "currency": "USD",
  "seed": 2026,
  "home_country": "124",
  "home_revenue_share": 0.12,
  "network": {"farm": 22, "supplier": 14, "factory": 9, "distribution_centre": 12, "market": 30},
  "incidents_per_site_year": 1.6,
  "history_days": 365,
  "disruption_days_median": 3.0
}
```

Change any value, or point the `FOODCARE_GEO_SCENARIO` environment variable at another file, and the whole world regenerates. The fixed **seed** makes it reproducible: the same file gives the same globe on every laptop, in CI and in screenshots.

`backend/app/geo.py` turns the file into a network in six steps.

**1. The footprint.**
- The country list comes from Natural Earth's public-domain 1:110m map, through the `world-atlas` package. A small Node script precomputes each country's centroid with `d3-geo`.
- Three disputed or non-sovereign territories are excluded.
- The home country is always included, and a seeded shuffle picks the rest, making 161 in total.

**2. The revenue split.**
- The home country gets a fixed 12%.
- The others share the rest in proportions drawn from a **log-normal** distribution. Real revenue looks like that: a few large markets and a long tail of small ones.
- Rounding to whole dollars loses a few units, and naive code would silently drift. The remainder goes to the largest country, so the total equals the configured USD 2,400,000,000 **to the dollar**. A test asserts it.

**3. Sites.**
- Markets go into the 30 highest-revenue countries; the other tiers are spread more widely.
- Every site sits **near its country's centroid, with a small random offset**. That is a deliberate design choice: no coordinate could ever be mistaken for a real address. Tooltips say "approximate location".

**4. Links.**
- Every farm supplies its nearest supplier, and every supplier its nearest factory.
- Each factory feeds its two nearest distribution centres, and each centre its two nearest markets. Distance is the great-circle *haversine* formula.
- A second pass connects any downstream site that ended up without a supplier.
- Distance sets the mode (road under 900 km, sea over 3,500 km, rail in between) and a lead time.

**5. Revenue that depends on each site.**
- A market carries its country's revenue.
- Walking upstream tier by tier, each site carries the revenue of everything it feeds, split evenly across that site's suppliers.
- The UI prints the formula, and it also prints the gap: only USD 1.50B of the USD 2.40B is traced to sites, because only 30 countries have a market site. Hiding that gap would have made the financial panel look more complete than it is.

**6. A year of incidents.**
- Each non-market site gets a Poisson-distributed number of incidents over the last 365 days, at a site-specific rate around the configured 1.6 a year.
- Each incident gets a date, a type (bruising above spec, greening, soft rot, foreign material, temperature excursion, late delivery, undersize lot), a severity and a lot number like `SYN-LOT-22389`.

The default scenario produces **87 sites, 106 routes and 108 historical incidents**. Building it takes milliseconds and is cached per configuration.

---

## Step 3: the globe

![Six moments of the globe recording: idle, Peru, a single market, simulated movement, the 2D map, a quality incident](https://github.com/florina787/Data-sets/blob/claude/new-session-pahp8j/foodcare-copilot/docs/media/map2d.gif?raw=true)

### Choosing a library

| Option | Verdict |
|---|---|
| **Three.js** (MIT) | ✅ Chosen. Full control of glow, atmosphere and arcs, and no map tiles needed |
| deck.gl `GlobeView` (MIT) | Strong data layers, but GlobeView is still experimental and pulls in a large renderer |
| MapLibre GL JS globe (BSD-3) | Beautiful, but needs vector **tiles**. Hosted tiles usually need an account or a paid plan, and the brief said "do not activate paid services" |
| d3-geo (ISC) | ✅ Chosen for the **2D fallback** |

No tile server, no API key and no billing. The globe's only geography is a 38 kB (gzipped) TopoJSON file that ships with the app.

### Building the scene

The globe component (`Globe3D.tsx`, about 280 lines) builds:

- **The planet:** a 96×96-segment sphere with a dark navy Phong material and a faint royal-blue specular highlight, matching the app's navy design system.
- **The atmosphere:** a slightly larger sphere drawn from the inside (`BackSide`) with additive blending. A tiny fresnel shader makes the glow strongest at the rim:

  ```glsl
  varying vec3 vN;
  void main(){
    float i = pow(0.72 - dot(vN, vec3(0.0,0.0,1.0)), 3.0);
    gl_FragColor = vec4(0.22,0.74,0.97,1.0) * i;
  }
  ```

- **Glowing coastlines:** the TopoJSON border mesh is projected onto the sphere twice. One copy is a crisp cyan line. The other, scaled up by 0.3% with additive blending and low opacity, makes the soft halo. Two cheap line sets look like bloom without a post-processing pass.
- **Curved arcs:** each route is a quadratic Bézier curve. Its control point is the normalised midpoint pushed outward in proportion to the distance, so long routes arc higher, as flight paths do.
- **Sites:** small spheres coloured by tier. Farms are lime, suppliers cyan, factories gold, distribution centres pale periwinkle and markets light gold. Red is reserved **only** for quality risk.
- **Incidents:** red markers. High-severity ones get a ring that expands and fades, a *status* signal rather than fake activity.

### Motion with restraint

The brief asked for "animated data flows" and also said to *"avoid decorative animations that imply nonexistent real-time activity."* The audit had found **zero tracking events**, so the resolution is:

- **Arcs are static by default.** They glow, but nothing moves along them.
- A **Simulated movement** checkbox (off by default) sends small gold dots along the routes at speeds based on lead time. While it is on, a high-contrast badge reads **SIMULATED MOVEMENT · 0 tracking events exist**.
- The idle rotation is slow (OrbitControls `autoRotateSpeed = 0.35`) and **stops the moment you touch the globe**.

### Camera transitions

Selecting a country, site or incident flies the camera there. The flight interpolates the camera's *direction* (normalised vectors, so it travels around the planet rather than through it) and its distance separately, with a cubic ease-in-out over 1.4 s. A country stops at 2.3 globe radii, a site or incident at 1.75.

### Picking and tooltips

A `Raycaster` tests pointer events against visible incident markers first, then sites. To keep rotation smooth, a click is only treated as a click if the pointer moved less than 4 px between down and up. Otherwise it was a drag. Tooltips are plain HTML over the canvas, so they stay sharp and readable, and they always end with the provenance ("SYNTHETIC site (approximate location)" or "OPERATIONAL RECORD (your inspection)").

### Performance

- **Code-splitting:** the globe is `React.lazy`-loaded. Pages without a map never download Three.js (128 kB gzipped), and the world borders (38 kB) load on demand too.
- **Off-screen pause:** an `IntersectionObserver` and `document.hidden` pause the render loop when the globe is scrolled away or the tab is in the background.
- **Pixel ratio:** capped at 2.
- **A measured budget:** the component writes its first-render time into a `data-render-ms` attribute, and the browser test asserts a budget. In headless Chromium with **software** WebGL (SwiftShader), the first render measured **about 440–510 ms**. A real GPU is faster.
- **Failure handling:** if WebGL is missing or throws, an error boundary swaps in the 2D map.

---

## Step 4: the 2D map is not an afterthought

The 2D map (`Map2D.tsx`, built on `d3-geo` and SVG) is what you get with **reduced motion**, on screens **under 768 px**, or **without WebGL**. It is also a one-click alternative for everyone.

- **Projection:** Natural Earth, fitted to the sphere.
- **Choropleth:** countries are shaded by the selected overlay (regional revenue, financial exposure, supplier quality pass rate, or incidents in the last 365 days). The colour follows the square root of the value, so a single dominant country does not wash the rest out.
- **Routes:** drawn as **great-circle** `LineString`s, so they curve naturally on the projection.
- **Zoom transitions:** the zoom fits the selected country's bounds, or the bounding box of the selected site's whole chain. It animates with a 700 ms cubic ease and is instant under reduced motion. Strokes use `vector-effect: non-scaling-stroke`, so lines stay hairline-thin at 14× zoom.
- **Pulses:** high-severity incidents pulse with a CSS ring. The app's global `prefers-reduced-motion` rule switches every pulse off.

For keyboard and screen-reader users there is a **Table view** under the map. It lists every country and site with a *Select* button that does exactly what a click on the map does. The SVG carries a descriptive `aria-label`, and every chart has a text alternative.

---

## Step 5: one component, many pages, one selection

The brief warned against building a separate map for every page. There is one `SupplyMap` component. Each page passes a title, a default tab and a default overlay:

| Page | Opens on | Overlay |
|---|---|---|
| Executive Command | Financial impact | Regional revenue |
| Inventory (the supply-chain page) | Forecast & risk | Financial exposure |
| Quality Intelligence | Quality incidents | Operational risk |

### The shared geographic selection

The selection, `{ country?, node?, incident? }`, lives in the app's React context, *inside* the router, and is **mirrored to the URL**:

```
/inventory?geo=c:604|n:GEO-MAR-04|i:GEO-INC-0041
```

That one decision gives four behaviours for free:

1. **Navigation keeps context.** Navigation links drop the query string, but an effect writes `?geo=` back on every route change.
2. **Reloads keep context.** The state is initialised from the URL.
3. **Links are shareable.** Paste the link to a colleague and they land on the same site.
4. **The context is visible.** A gold chip in the header (`◎ Peru › GEO-MAR-04 ✕`) shows the selection on every page, and ✕ clears it everywhere.

The parser only accepts `[\w-]{1,24}` values, so nothing odd ever travels from the URL into the UI.

### The tabs under the map

- **Financial impact:** the top countries by revenue, and the revenue that depends on each tier in scope. The formula and the attribution gap are printed underneath.
- **Forecast & risk:** the 30/90/180-day bands (next section).
- **Quality incidents:** the list (click one to fly to it), plus a recurrence chart of incidents per month.
- **OriginTrace:** every upstream path from the selected site back to a farm.

---

## Step 6: risk simulation with honest uncertainty

"Risk forecasting" is where dashboards most often overstate what they know. This one is a **stated model**, and the method text is displayed next to the result:

1. **Uncertain rates.** A site with 3 incidents last year doesn't have a known rate of exactly 3 a year. Each simulated run draws a rate from a **Gamma posterior**: shape = incidents + 0.5, rate = years of history + 0.5. Sites with little history get wider spreads, as they should.
2. **Counts.** Each run draws a **Poisson** incident count for the horizon (30, 90 or 180 days).
3. **Severity.** Each incident draws a disruption length from a **log-normal** distribution (median 3 days). Exposure = disrupted days × the revenue dependent on the site ÷ 365.
4. **Repetition.** 400 runs, sorted, reported as the 10th, 50th and 90th percentiles.

For the whole default network:

| Horizon | Incidents, median (P10–P90) | Revenue exposed, median (P10–P90) |
|---|---|---|
| 30 days | 7 (4–11) | USD 7.6M (2.6M–14.8M) |
| 90 days | 22 (16–29) | USD 23.5M (13.9M–37.9M) |
| 180 days | 44 (35–54) | USD 46.9M (34.1M–65.6M) |

The UI draws each horizon as a shaded band with a gold median line, and spells it out: *"Wider bands at longer horizons mean less certainty, not more risk."* Two tests keep it honest: the simulation is **deterministic** for a given scenario, and the bands are **ordered** (P10 ≤ P50 ≤ P90) and **widen** with the horizon.

Everything here is labelled **Modelled**, with "Inputs are synthetic" in the method. Nobody should read "USD 7.6M" as a prediction about a real company.

---

## Step 7: OriginTrace, built on the copilot

There was no "OriginTrace AI" in the repository. Rather than build a second agent with its own prompts, tools and failure modes, OriginTrace became a **new intent in the existing copilot**. The copilot already routes questions deterministically, cites every source, and records every run in the agent trace.

- **Routing.** The router gained an `origin_trace` intent, with keywords such as *trace*, *origin*, *upstream*, *supply chain*, *exposure*, *country* and *factory*. It also recognises site and incident IDs (`GEO-SUP-04`, `GEO-INC-0041`) and country names.
- **The answer.** The handler composes:
  - the upstream paths and the downstream reach;
  - the revenue that depends on the site;
  - the incident recurrence;
  - the modelled 30/90/180-day risk with ranges;
  - a closing reminder that everything comes from a synthetic scenario with no verified sites or tracking events.
- **Citations.** Each claim is cited `[S1]`, `[S2]` to the scenario file (with its seed) and to the simulation.

From any map selection, **Investigate with OriginTrace** opens the copilot drawer with a ready-made question. The run then appears on the **Agent Intelligence** page, next to every other agent run, with its tool calls and timings. A regression test confirms that the new intent didn't steal existing questions: *"How did our sales do in the last 4 weeks?"* still routes to `sales`.

---

## Step 8: putting real records on a synthetic map

The audit found one real, location-adjacent record: potato inspection batches have a free-text **supplier** field. That became the bridge:

- On the inspection form, the Supplier box now suggests the network's supplier names (an HTML `datalist`).
- If a batch names a network supplier, and **20% or more** of its potatoes are graded *Not Good* by the classical image pipeline, the batch appears on the map at that supplier as a red **Operational record**.
- **Only the user who created it** sees it. Another user, or a signed-out visitor, gets the synthetic network with no trace of it.

A backend test runs the real pipeline on a synthetic test image (12 potatoes, 4 Not Good, 33%). It then checks that the batch appears for its owner, through the API with a real session token, and for nobody else. It is the first honest step toward the multi-tenant isolation the brief asked for. Full tenancy needs a `tenant_id` on every table, so it is scheduled as its own phase.

---

## Step 9: testing what matters

**Backend (`test_geo.py`, 7 tests):**
- The scenario is configurable: a 40-country, EUR 5M scenario regenerates correctly, an impossible country count is refused, and revenue sums to the dollar.
- Every item carries provenance, and the verified count is 0.
- The country filter keeps only that country and its direct links; an invalid tier returns HTTP 400.
- Every trace path ends at a farm, every farm feeds something, and unknown sites return 404.
- The risk simulation is deterministic, ordered and widening.
- Real inspections are isolated per user.
- OriginTrace answers with citations, and existing intents are unchanged.

**Browser (`e2e/geo.spec.ts`, Playwright, 2 tests):**
- The disclaimer and "Verified: 0" are visible, and the render budget is met.
- The 2D drill-down works through the accessible table: country, then site, then the forecast and trace tabs.
- The URL contains the selection.
- The selection survives navigating to Inventory and a full reload.
- OriginTrace works from the map.
- Quality Intelligence opens on incidents.
- Clearing the selection removes it from the URL.
- With `reducedMotion: "reduce"` at 390 × 844, the map starts in 2D and the page **never scrolls sideways**.

The whole project's suites pass: backend, the browser tests, linting and strict TypeScript.

---

## Step 10: recording the media for real

Every GIF and video in the README comes from the running app. A Playwright script drives the browser and screenshots each frame:

- it lets the globe idle;
- it selects Peru;
- it drills into a market;
- it switches on simulated movement, so the SIMULATED badge appears in the frame;
- it switches to the 2D map;
- it cycles the overlays;
- it opens a quality incident.

Headless Chromium has no GPU, so it runs with `--use-angle=swiftshader` to get a software WebGL device.

Pillow assembles the frames into GIFs with a single shared palette, which stops flicker and keeps the files small. Identical frames are merged into longer durations. `ffmpeg` encodes the MP4s, pads them to 1280×800 in the app's navy, and concatenates the scenes into a 31-second **executive presentation** video. Re-running two commands regenerates all of it after any UI change.

---

## What I would tell another team

1. **Audit first.** It took less time than building the wrong thing, and it turned "verified farms" into the honest question "which farms?"
2. **Make provenance a data type, not a footnote.** When every item carries a label and a test enforces it, the UI cannot forget it.
3. **Show your zeros.** "Verified: 0" and "0 tracking events exist" build more trust than any amount of polish.
4. **Motion should mean something.** Static arcs by default; movement only when something really moved, or when it is clearly labelled as simulated.
5. **Uncertainty is a feature.** A band that widens with the horizon tells the truth that a single number hides.
6. **One component, one selection, one URL.** Cross-dashboard context is a state-management problem. Solve it once, in the URL.
7. **Ship the 2D map with the same care as the 3D globe.** It is what your reduced-motion, phone and low-power users actually see.

---

*Everything in this project — the company, its countries, revenue, sites, routes and incidents — is fictional and labelled as such. The code, the tests, the audit and the recordings are in the public repository: github.com/florina787/Data-sets (folder `foodcare-copilot`).*

*Tags: Data Visualization · Supply Chain · Three.js · React · Responsible AI*
