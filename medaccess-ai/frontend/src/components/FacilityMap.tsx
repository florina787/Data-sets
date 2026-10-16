// Schematic, dependency-free GTA map. No third-party tile server is contacted, so no location data
// leaves the browser. Positions are an equirectangular projection; the shoreline is approximate.
import { useMemo, useState } from "react";

import type { FacilityCard } from "../services/api";
import { AvailabilityBadge } from "./ui";

const BOUNDS = { minLon: -80.05, maxLon: -78.75, minLat: 43.2, maxLat: 44.15 };
const W = 640;
const KM_PER_DEG_LAT = 111.0;
const COS = Math.cos((43.7 * Math.PI) / 180);
const H = Math.round(W * ((BOUNDS.maxLat - BOUNDS.minLat) / ((BOUNDS.maxLon - BOUNDS.minLon) * COS)));

const project = (lat: number, lon: number) => ({
  x: ((lon - BOUNDS.minLon) / (BOUNDS.maxLon - BOUNDS.minLon)) * W,
  y: ((BOUNDS.maxLat - lat) / (BOUNDS.maxLat - BOUNDS.minLat)) * H,
});
const PX_PER_KM = W / ((BOUNDS.maxLon - BOUNDS.minLon) * KM_PER_DEG_LAT * COS);

const SHORE: [number, number][] = [
  [43.2, -79.95], [43.27, -79.85], [43.32, -79.78], [43.4, -79.7], [43.47, -79.63], [43.54, -79.56], [43.59, -79.5],
  [43.62, -79.43], [43.63, -79.37], [43.66, -79.3], [43.69, -79.22], [43.74, -79.15], [43.79, -79.08], [43.82, -79.0],
  [43.85, -78.9], [43.86, -78.75],
];
const PLACES: [string, number, number][] = [
  ["Toronto", 43.6532, -79.3832], ["North York", 43.7615, -79.4111], ["Scarborough", 43.7731, -79.2578],
  ["Etobicoke", 43.6205, -79.5132], ["Mississauga", 43.589, -79.6441], ["Brampton", 43.7315, -79.7624],
  ["Markham", 43.8561, -79.337], ["Vaughan", 43.8372, -79.5083], ["Oakville", 43.4675, -79.6877],
  ["Pickering", 43.8384, -79.0868], ["Newmarket", 44.0592, -79.4613], ["Hamilton", 43.2557, -79.8711],
];
const COLOR: Record<string, string> = {
  VERIFIED_AVAILABLE: "#2E7D32", ADVERTISED_UNVERIFIED: "#ED6C02", CONTACT_REQUIRED: "#ED6C02",
  UNAVAILABLE: "#90A4AE", UNKNOWN: "#D32F2F",
};

interface Props {
  cards: FacilityCard[];
  center?: { lat: number; lon: number } | null;
  radiusKm?: number | null;
  highlightId?: string | null;
  onSelect?: (id: string) => void;
}

export function FacilityMap({ cards, center, radiusKm, highlightId, onSelect }: Props) {
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const c = center ? project(center.lat, center.lon) : { x: W / 2, y: H / 2 };
  const vw = W / zoom;
  const vh = H / zoom;
  const vx = Math.min(Math.max(0, c.x - vw / 2), W - vw);
  const vy = Math.min(Math.max(0, c.y - vh / 2), H - vh);
  const shore = useMemo(() => {
    const pts = SHORE.map(([la, lo]) => project(la, lo));
    return `M${pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" L")} L${W},${H} L0,${H} Z`;
  }, []);
  const sel = cards.find((x) => x.facility.id === (selected ?? highlightId));
  const r = 6 / Math.sqrt(zoom);
  return (
    <div className="relative">
      <svg viewBox={`${vx} ${vy} ${vw} ${vh}`} className="h-auto w-full rounded-xl border border-slate-200 bg-[#F4F8F2]" role="group" aria-label="Map of facilities in the Greater Toronto Area">
        <path d={shore} fill="#CFE5F5" />
        {PLACES.map(([n, la, lo]) => {
          const p = project(la, lo);
          return <text key={n} x={p.x} y={p.y} fontSize={11 / Math.sqrt(zoom)} fill="#6B7C8F" textAnchor="middle" aria-hidden="true">{n}</text>;
        })}
        {center && radiusKm && (
          <circle cx={c.x} cy={c.y} r={radiusKm * PX_PER_KM} fill="#1565C0" fillOpacity=".06" stroke="#1565C0" strokeDasharray="6 4" strokeWidth={1.2 / zoom} />
        )}
        {center && <circle cx={c.x} cy={c.y} r={r * 0.9} fill="#1565C0" stroke="#fff" strokeWidth={2 / zoom}><title>Search centre</title></circle>}
        {cards.map((card) => {
          const p = project(card.facility.latitude, card.facility.longitude);
          const active = card.facility.id === (selected ?? highlightId);
          return (
            <g key={card.facility.id} role="button" tabIndex={0} aria-label={`${card.facility.name}, ${card.availability_state.replace(/_/g, " ").toLowerCase()}`}
              onClick={() => { setSelected(card.facility.id); onSelect?.(card.facility.id); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(card.facility.id); onSelect?.(card.facility.id); } }}
              style={{ cursor: "pointer" }}>
              <circle cx={p.x} cy={p.y} r={active ? r * 1.6 : r} fill={COLOR[card.availability_state] ?? "#90A4AE"} stroke="#fff" strokeWidth={2 / zoom} />
              <title>{card.facility.name}</title>
            </g>
          );
        })}
      </svg>
      <div className="absolute right-2 top-2 flex flex-col gap-1">
        <button className="btn-ghost h-8 w-8 p-0" aria-label="Zoom in" onClick={() => setZoom((z) => Math.min(8, z * 1.6))}>+</button>
        <button className="btn-ghost h-8 w-8 p-0" aria-label="Zoom out" onClick={() => setZoom((z) => Math.max(1, z / 1.6))}>−</button>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
        {[["Verified", "#2E7D32"], ["Unverified / contact", "#ED6C02"], ["Unavailable", "#90A4AE"], ["Source down / unknown", "#D32F2F"]].map(([l, col]) => (
          <span key={l} className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: col }} />{l}</span>
        ))}
        <span className="ml-auto">Schematic map · straight-line distances · fictional demo facilities</span>
      </div>
      {sel && (
        <div className="mt-2 rounded-xl border border-slate-200 bg-white p-3 text-sm" aria-live="polite">
          <div className="font-semibold">{sel.facility.name}</div>
          <div className="text-slate-600">{sel.facility.neighbourhood}, {sel.facility.city} · {sel.geo.straight_km.toFixed(1)} km · {sel.facility.phone}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2"><AvailabilityBadge status={sel.availability_state} simulated={sel.facility.is_synthetic} />
            {sel.days_until != null && <span className="text-xs">next opening in {sel.days_until} days</span>}
            {sel.source_status !== "OK" && <span className="text-xs text-danger">Availability source unreachable — contact the provider</span>}
          </div>
        </div>
      )}
    </div>
  );
}
