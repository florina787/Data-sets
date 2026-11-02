import { useEffect, useMemo, useRef, useState } from "react";
import { Map as MLMapCtor, NavigationControl, Popup, setWorkerUrl, type GeoJSONSource, type Map as MLMap } from "maplibre-gl";
// MapLibre 6 loads its worker as a separate ES module; let Vite bundle it and hand MapLibre the URL (works in dev and build).
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import { feature } from "topojson-client";
import type { FeatureCollection, Geometry } from "geojson";
import world from "world-atlas/countries-110m.json";
import type { Topology } from "topojson-specification";
import type { Disruption, Facility, LayerId, MapState, Supplier } from "./types";

/** Country outlines bundled from Natural Earth (public domain) via world-atlas: the map needs no tile server and no network. */
setWorkerUrl(maplibreWorkerUrl);

const COUNTRIES = feature(world as unknown as Topology, (world as unknown as Topology).objects.countries) as unknown as FeatureCollection<Geometry>;

export type MapMode = "globe" | "flat" | "lite";
export type Selection = { kind: "facility" | "supplier" | "disruption"; id: string } | null;

const KIND_COLOR: Record<string, string> = { mro: "#22D3EE", repair_center: "#14B8A6", warehouse: "#38BDF8", manufacturing: "#FBBF24" };
const GOOD = [16, 185, 129], MID = [245, 158, 11], BAD = [239, 68, 68];

/** 0 = good (emerald) .. 0.5 = warning (amber) .. 1 = critical (red). */
export function scale(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  const [a, b, u] = t < 0.5 ? [GOOD, MID, t / 0.5] : [MID, BAD, (t - 0.5) / 0.5];
  return `rgb(${a.map((x, i) => Math.round(x + (b[i] - x) * u)).join(",")})`;
}

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

type Styled = { id: string; kind: string; lon: number; lat: number; color: string; radius: number; label: string; ring?: string };

/** Per-layer encoding: colour and size come from computed metrics only. */
export function encode(state: MapState, layer: LayerId) {
  const fac: Styled[] = state.facilities.map((f: Facility) => {
    let color = KIND_COLOR[f.kind] ?? "#94A3B8", radius = 7;
    if (layer === "health") {
      color = f.health_mean == null ? "#334155" : scale((0.85 - f.health_mean) / 0.5);
      radius = f.units_due != null ? 6 + Math.min(14, f.units_due) : 5;
    } else if (layer === "inventory") {
      color = f.max_stockout_prob == null ? "#334155" : scale(f.max_stockout_prob);
      radius = f.shortage_count != null ? 6 + Math.min(14, f.shortage_count) : 5;
    } else if (layer === "facilities") {
      radius = f.demand_p50 != null ? 6 + Math.min(12, Math.sqrt(f.demand_p50)) : 6;
    } else if (layer === "recovery") {
      color = f.capacity_cut ? scale(f.capacity_cut * 1.6) : "#10B981";
      radius = f.capacity_cut ? 9 + f.capacity_cut * 14 : 5;
    } else if (layer === "supply" || layer === "disruptions") {
      radius = 5;
      color = "#64748B";
    }
    return { id: f.id, kind: "facility", lon: f.lon, lat: f.lat, color, radius, label: `${f.name} · ${f.city}` };
  });
  const sup: Styled[] = layer === "supply" || layer === "facilities"
    ? state.suppliers.map((s: Supplier) => ({ id: s.id, kind: "supplier", lon: s.lon, lat: s.lat, color: layer === "supply" ? scale(s.late_probability) : "#A3E635",
      radius: layer === "supply" ? 7 + s.open_orders * 0.6 : 5, label: `${s.name} (supplier) · ${s.city}`, ring: "#E2E8F0" }))
    : [];
  const dis: Styled[] = layer === "disruptions" || layer === "recovery"
    ? state.disruptions.map((d: Disruption) => ({ id: d.id, kind: "disruption", lon: d.lon + 0.6, lat: d.lat + 0.6,
      color: layer === "recovery" ? scale(1 - d.recovery_progress) : d.severity === "high" ? "#EF4444" : d.severity === "medium" ? "#F59E0B" : "#FBBF24",
      radius: d.phase === "recovered" ? 6 : d.severity === "high" ? 16 : d.severity === "medium" ? 12 : 9, label: `${d.title} (${d.phase})`, ring: "#FEE2E2" }))
    : [];
  const lateBy = Object.fromEntries(state.suppliers.map((s) => [s.id, s.late_probability]));
  const links = layer === "supply" ? state.links : [];
  return { points: [...fac, ...sup, ...dis], links: links.map((l) => ({ ...l, color: scale(lateBy[l.supplier_id] ?? 0) })) };
}

function pointsGeo(points: Styled[]) {
  return { type: "FeatureCollection" as const, features: points.map((p) => ({ type: "Feature" as const, id: undefined,
    properties: { id: p.id, kind: p.kind, color: p.color, radius: p.radius, label: p.label, ring: p.ring ?? "rgba(255,255,255,0.65)" },
    geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] } })) };
}

function arc(from: [number, number], to: [number, number], n = 24): [number, number][] {
  // simple curved polyline (bezier through a raised midpoint) so links read as flows
  const mid: [number, number] = [(from[0] + to[0]) / 2, (from[1] + to[1]) / 2 + Math.min(18, Math.abs(from[0] - to[0]) / 6)];
  return Array.from({ length: n + 1 }, (_, i) => {
    const t = i / n;
    return [(1 - t) ** 2 * from[0] + 2 * (1 - t) * t * mid[0] + t * t * to[0], (1 - t) ** 2 * from[1] + 2 * (1 - t) * t * mid[1] + t * t * to[1]];
  });
}

function linksGeo(links: { from: [number, number]; to: [number, number]; color: string; share: number; supplier_id: string; facility_id: string }[]) {
  return { type: "FeatureCollection" as const, features: links.map((l) => ({ type: "Feature" as const,
    properties: { color: l.color, width: 0.6 + l.share * 2.2 }, geometry: { type: "LineString" as const, coordinates: arc(l.from, l.to) } })) };
}

/** Interpolate radii between two encodings so the map transitions smoothly when the forecast horizon changes. */
function tween(prev: Styled[], next: Styled[], t: number): Styled[] {
  const p = new Map(prev.map((x) => [x.kind + x.id, x]));
  return next.map((n) => {
    const o = p.get(n.kind + n.id);
    return o ? { ...n, radius: o.radius + (n.radius - o.radius) * t } : { ...n, radius: n.radius * t };
  });
}

export function GlobeMap({ state, layer, mode, selection, onSelect, focus }: {
  state: MapState; layer: LayerId; mode: MapMode; selection: Selection; onSelect: (s: Selection) => void; focus?: { lon: number; lat: number; ts: number } | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const enc = useMemo(() => encode(state, layer), [state, layer]);
  const last = useRef<Styled[]>([]);

  useEffect(() => {
    if (mode === "lite" || !box.current) return;
    const m = new MLMapCtor({
      container: box.current, attributionControl: false, center: [20, 25], zoom: mode === "globe" ? 1.25 : 1.1, minZoom: 0.6, maxZoom: 7,
      style: {
        version: 8, projection: { type: mode === "globe" ? "globe" : "mercator" },
        sources: { countries: { type: "geojson", data: COUNTRIES } },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#050B18" } },
          { id: "land", type: "fill", source: "countries", paint: { "fill-color": "#0D1D33", "fill-opacity": 0.95 } },
          { id: "borders", type: "line", source: "countries", paint: { "line-color": "rgba(34,211,238,0.22)", "line-width": 0.6 } },
        ],
      },
    });
    m.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
    m.on("load", () => {
      m.addSource("links", { type: "geojson", data: linksGeo([]) });
      m.addSource("points", { type: "geojson", data: pointsGeo([]) });
      m.addLayer({ id: "links", type: "line", source: "links", paint: { "line-color": ["get", "color"], "line-width": ["get", "width"], "line-opacity": 0.55 } });
      m.addLayer({ id: "halo", type: "circle", source: "points", paint: { "circle-radius": ["*", ["get", "radius"], 1.9], "circle-color": ["get", "color"], "circle-opacity": 0.14, "circle-blur": 0.6 } });
      m.addLayer({ id: "points", type: "circle", source: "points", paint: { "circle-radius": ["get", "radius"], "circle-color": ["get", "color"], "circle-opacity": 0.92,
        "circle-stroke-color": ["get", "ring"], "circle-stroke-width": 1 } });
      m.addLayer({ id: "selected", type: "circle", source: "points", filter: ["==", ["get", "id"], ""], paint: { "circle-radius": ["+", ["get", "radius"], 5], "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#22D3EE", "circle-stroke-width": 2.5 } });
      const pop = new Popup({ closeButton: false, closeOnClick: false, offset: 10 });
      m.on("mousemove", "points", (e) => {
        m.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (f) pop.setLngLat(e.lngLat).setText(String(f.properties.label)).addTo(m);
      });
      m.on("mouseleave", "points", () => { m.getCanvas().style.cursor = ""; pop.remove(); });
      m.on("click", "points", (e) => {
        const f = e.features?.[0];
        if (f) onSelect({ kind: f.properties.kind, id: String(f.properties.id) });
      });
      setReady(true);
    });
    map.current = m;
    return () => { setReady(false); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    (m.getSource("links") as GeoJSONSource).setData(linksGeo(enc.links));
    const from = last.current, to = enc.points;
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 450);
      (m.getSource("points") as GeoJSONSource).setData(pointsGeo(tween(from, to, t)));
      if (t < 1) raf = requestAnimationFrame(step);
      else last.current = to;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [enc, ready]);

  useEffect(() => {
    if (ready && map.current) map.current.setFilter("selected", ["==", ["get", "id"], selection?.id ?? ""]);
  }, [selection, ready]);

  useEffect(() => {
    if (ready && map.current && focus) map.current.flyTo({ center: [focus.lon, focus.lat], zoom: 3.2, duration: 1200 });
  }, [focus, ready]);

  if (mode === "lite") return <LiteMap points={enc.points} links={enc.links} selection={selection} onSelect={onSelect} />;
  return <div ref={box} className="h-full w-full" data-testid="maplibre-map" role="application" aria-label="Interactive global map" />;
}

/** No-WebGL fallback: equirectangular SVG with the same encoding and click targets. */
function LiteMap({ points, links, selection, onSelect }: { points: Styled[]; links: { from: [number, number]; to: [number, number]; color: string; share: number }[];
  selection: Selection; onSelect: (s: Selection) => void }) {
  const W = 1000, H = 500;
  const x = (lon: number) => ((lon + 180) / 360) * W, y = (lat: number) => ((90 - lat) / 180) * H;
  const paths = useMemo(() => COUNTRIES.features.map((f) => {
    const g = f.geometry as { type: string; coordinates: number[][][] | number[][][][] };
    const polys = g.type === "Polygon" ? [g.coordinates as number[][][]] : (g.coordinates as number[][][][]);
    return polys.map((poly) => poly.map((ring) => ring.map(([lo, la], i) => `${i ? "L" : "M"}${x(lo).toFixed(1)},${y(la).toFixed(1)}`).join("") + "Z").join("")).join("");
  }), []);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full bg-[#050B18]" data-testid="lite-map" role="img" aria-label="Global map (lite, no WebGL)">
      {paths.map((d, i) => <path key={i} d={d} fill="#0D1D33" stroke="rgba(34,211,238,0.22)" strokeWidth={0.5} />)}
      {links.map((l, i) => <polyline key={i} points={arc(l.from, l.to).map(([lo, la]) => `${x(lo)},${y(la)}`).join(" ")} fill="none" stroke={l.color} strokeOpacity={0.55} strokeWidth={0.6 + l.share * 2} />)}
      {points.map((p) => (
        <g key={p.kind + p.id} onClick={() => onSelect({ kind: p.kind as "facility", id: p.id })} className="cursor-pointer">
          <title>{p.label}</title>
          <circle cx={x(p.lon)} cy={y(p.lat)} r={p.radius * 1.8} fill={p.color} opacity={0.14} />
          <circle cx={x(p.lon)} cy={y(p.lat)} r={p.radius} fill={p.color} stroke={selection?.id === p.id ? "#22D3EE" : "rgba(255,255,255,0.6)"} strokeWidth={selection?.id === p.id ? 3 : 1} />
        </g>
      ))}
    </svg>
  );
}
