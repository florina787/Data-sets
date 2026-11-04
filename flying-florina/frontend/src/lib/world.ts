import { feature } from "topojson-client";
import type { FeatureCollection, Geometry } from "geojson";
import world from "world-atlas/countries-110m.json";
import type { Topology } from "topojson-specification";

/** Country outlines bundled from Natural Earth (public domain) via world-atlas: no tile server, no network. */
export const COUNTRIES = feature(world as unknown as Topology, (world as unknown as Topology).objects.countries) as unknown as FeatureCollection<Geometry>;

/** Equirectangular SVG path for every country, for a given drawing size (cropped latitudes look nicer on a banner). */
export function worldPath(W: number, H: number, latTop = 80, latBottom = -58): string {
  const x = (lon: number) => ((lon + 180) / 360) * W;
  const y = (lat: number) => ((latTop - lat) / (latTop - latBottom)) * H;
  return COUNTRIES.features.map((f) => {
    const g = f.geometry as { type: string; coordinates: number[][][] | number[][][][] };
    const polys = g.type === "Polygon" ? [g.coordinates as number[][][]] : (g.coordinates as number[][][][]);
    return polys.map((poly) => poly.map((ring) => ring.map(([lo, la], i) => `${i ? "L" : "M"}${x(lo).toFixed(1)},${y(la).toFixed(1)}`).join("") + "Z").join("")).join("");
  }).join("");
}
