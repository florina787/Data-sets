// Builds fixtures/geo/countries.json from Natural Earth 1:110m (public domain, via world-atlas, ISC):
// ISO 3166 numeric id, name, and the geographic centroid (lon, lat) of each country.
//   node scripts/build_geo_countries.mjs
import fs from "fs";
import { createRequire } from "module";
import { geoCentroid } from "d3-geo";
import { feature } from "topojson-client";
const require = createRequire(new URL("../apps/control-room/package.json", import.meta.url));
const topo = require("world-atlas/countries-110m.json");
const fc = feature(topo, topo.objects.countries);
const out = fc.features
  .filter((f) => f.id && f.properties?.name && f.properties.name !== "Antarctica")
  .map((f) => { const [lon, lat] = geoCentroid(f); return { id: String(f.id), name: f.properties.name, lon: +lon.toFixed(2), lat: +lat.toFixed(2) }; })
  .sort((a, b) => a.id.localeCompare(b.id));
fs.writeFileSync(new URL("../fixtures/geo/countries.json", import.meta.url), JSON.stringify({
  source: "Natural Earth 1:110m admin-0 countries (public domain) via world-atlas 2.0.2 (ISC); centroids computed with d3-geo",
  countries: out }, null, 1) + "\n");
console.log(out.length, "countries");
