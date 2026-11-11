import { geoGraticule10, geoNaturalEarth1, geoPath } from "d3-geo";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { GeoSel } from "../../context";
import { GeoIncident, GeoNode, Network, RISK_RED, scopeOf, TIER_COLOR, TIER_LABEL } from "./geoData";

const W = 960;
const H = 500;
type Scope = ReturnType<typeof scopeOf>;
export type MapProps = {
  net: Network; scope: Scope; sel: GeoSel; onSelect: (g: GeoSel) => void;
  countryValue: Map<string, number>; overlayLabel: string; formatValue: (v: number) => string;
  simulated: boolean; reducedMotion: boolean; onRendered?: (ms: number) => void;
};

let worldPromise: Promise<FeatureCollection<Geometry, { name: string }>> | null = null;
export function loadWorld() {
  worldPromise ??= import("world-atlas/countries-110m.json").then((m: any) => {
    const topo = m.default ?? m;
    return feature(topo, topo.objects.countries) as unknown as FeatureCollection<Geometry, { name: string }>;
  });
  return worldPromise;
}

export default function Map2D({ net, scope, onSelect, countryValue, overlayLabel, formatValue, simulated, reducedMotion, onRendered }: MapProps) {
  const [world, setWorld] = useState<FeatureCollection<Geometry, { name: string }> | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; title: string; lines: string[] } | null>(null);
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  const started = useRef(performance.now());
  const wrap = useRef<HTMLDivElement>(null);
  useEffect(() => { loadWorld().then(setWorld); }, []);
  useEffect(() => { if (world) onRendered?.(Math.round(performance.now() - started.current)); }, [world]);

  const projection = useMemo(() => geoNaturalEarth1().fitExtent([[8, 8], [W - 8, H - 8]], { type: "Sphere" }), []);
  const path = useMemo(() => geoPath(projection), [projection]);
  const byId = useMemo(() => new Map(net.nodes.map((n) => [n.id, n])), [net]);
  const max = Math.max(1, ...countryValue.values());

  // Camera: zoom to the selected country or the selected site's supply chain.
  useEffect(() => {
    let box: [[number, number], [number, number]] | null = null;
    if (scope.node) {
      const pts = [...scope.nodeIds].map((id) => byId.get(id)!).map((n) => projection([n.lon, n.lat])!);
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      box = [[Math.min(...xs) - 30, Math.min(...ys) - 30], [Math.max(...xs) + 30, Math.max(...ys) + 30]];
    } else if (scope.country && world) {
      const f = world.features.find((x) => String(x.id) === scope.country!.id);
      if (f) box = path.bounds(f);
    }
    let target = { k: 1, x: 0, y: 0 };
    if (box) {
      const [[x0, y0], [x1, y1]] = box;
      const k = Math.max(1, Math.min(14, 0.85 / Math.max((x1 - x0) / W, (y1 - y0) / H)));
      target = { k, x: W / 2 - k * (x0 + x1) / 2, y: H / 2 - k * (y0 + y1) / 2 };
    }
    if (reducedMotion) { setView(target); return; }
    const from = view, t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const u = Math.min(1, (t - t0) / 700), e = 1 - Math.pow(1 - u, 3);
      setView({ k: from.k + (target.k - from.k) * e, x: from.x + (target.x - from.x) * e, y: from.y + (target.y - from.y) * e });
      if (u < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [scope.node?.id, scope.country?.id, world, reducedMotion]);

  const tip = (ev: React.MouseEvent, title: string, lines: string[]) => {
    const r = wrap.current!.getBoundingClientRect();
    setHover({ x: ev.clientX - r.left, y: ev.clientY - r.top, title, lines });
  };
  const nodeTip = (n: GeoNode) => [`${TIER_LABEL[n.tier]} · ${n.country_name}`, `Revenue dependent: ${formatValue(n.revenue_dependent)}`,
    `On time ${n.performance.on_time_pct}% · quality pass ${n.performance.quality_pass_pct}%`, "SYNTHETIC site (approximate location)"];
  const incTip = (i: GeoIncident) => [`${i.date} · ${i.severity} severity`, `Lot ${i.batch}`,
    i.provenance === "operational_record" ? "OPERATIONAL RECORD (your inspection)" : "SYNTHETIC historical incident"];
  const k = view.k;
  const inScope = (id: string) => scope.nodeIds.has(id);

  return (
    <div ref={wrap} className="relative" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" data-testid="map-2d"
        aria-label={`2D supply-chain map: ${net.countries.length} countries, ${net.nodes.length} synthetic sites, ${net.incidents.length} incidents. Use the table below for keyboard access.`}>
        <defs>
          <radialGradient id="geo-sea" cx="50%" cy="45%" r="70%"><stop offset="0%" stopColor="#0d2442" /><stop offset="100%" stopColor="#061224" /></radialGradient>
          <filter id="geo-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <g transform={`translate(${view.x},${view.y}) scale(${k})`}>
          <path d={path({ type: "Sphere" }) ?? ""} fill="url(#geo-sea)" stroke="#1e3a5f" strokeWidth={1} vectorEffect="non-scaling-stroke" />
          <path d={path(geoGraticule10()) ?? ""} fill="none" stroke="#12304f" strokeWidth={0.5} vectorEffect="non-scaling-stroke" />
          {world?.features.map((f: Feature<Geometry, { name: string }>) => {
            const id = String(f.id);
            const v = countryValue.get(id);
            const selected = scope.country?.id === id;
            const fill = v === undefined ? "#0f2138" : `rgba(56,189,248,${0.12 + 0.6 * Math.sqrt(v / max)})`;
            return (
              <path key={id} d={path(f) ?? ""} fill={fill} stroke={selected ? "#e9b95b" : "#2b5a86"} strokeWidth={selected ? 1.6 : 0.5}
                vectorEffect="non-scaling-stroke" className={v === undefined ? "" : "cursor-pointer"}
                onClick={() => v !== undefined && onSelect({ country: id })}
                onMouseMove={(ev) => v !== undefined && tip(ev, f.properties.name, [`${overlayLabel}: ${formatValue(v)}`, "SYNTHETIC scenario value"])} />
            );
          })}
          <g fill="none" filter="url(#geo-glow)">
            {net.edges.map((e) => {
              const a = byId.get(e.from)!, b = byId.get(e.to)!;
              const d = path({ type: "LineString", coordinates: [[a.lon, a.lat], [b.lon, b.lat]] }) ?? "";
              const on = inScope(e.from) && inScope(e.to);
              return (
                <g key={e.id}>
                  <path id={`arc-${e.id}`} d={d} stroke={on && !scope.all ? "#e9b95b" : "#38bdf8"} strokeOpacity={on ? (scope.all ? 0.35 : 0.85) : 0.06}
                    strokeWidth={on && !scope.all ? 1.6 : 0.9} vectorEffect="non-scaling-stroke" />
                  {simulated && on && !reducedMotion && (
                    <circle r={2.2 / k} fill="#f3d18a"><animateMotion dur={`${4 + e.lead_time_days / 3}s`} repeatCount="indefinite"><mpath href={`#arc-${e.id}`} /></animateMotion></circle>
                  )}
                </g>
              );
            })}
          </g>
          {net.nodes.map((n) => {
            const [x, y] = projection([n.lon, n.lat])!;
            const on = inScope(n.id), picked = scope.node?.id === n.id;
            return (
              <g key={n.id} transform={`translate(${x},${y})`} opacity={on ? 1 : 0.18} className="cursor-pointer"
                onClick={(ev) => { ev.stopPropagation(); onSelect({ country: n.country, node: n.id }); }}
                onMouseMove={(ev) => tip(ev, n.name, nodeTip(n))}>
                {picked && <circle r={9 / k} fill="none" stroke="#e9b95b" strokeWidth={1.4} vectorEffect="non-scaling-stroke" className="geo-node-pulse" />}
                <circle r={(n.tier === "market" ? 3.6 : 3) / k} fill={TIER_COLOR[n.tier]} stroke="#061224" strokeWidth={0.6} vectorEffect="non-scaling-stroke" />
              </g>
            );
          })}
          {scope.incidents.map((i) => {
            const [x, y] = projection([i.lon, i.lat])!;
            const picked = scope.incident?.id === i.id;
            return (
              <g key={i.id} transform={`translate(${x + 4 / k},${y - 4 / k})`} className="cursor-pointer" data-provenance={i.provenance}
                onClick={(ev) => { ev.stopPropagation(); onSelect({ country: i.country, node: i.node_id, incident: i.id }); }}
                onMouseMove={(ev) => tip(ev, `${i.kind} (${i.id})`, incTip(i))}>
                {(i.severity === "high" || picked) && <circle r={7 / k} fill="none" stroke={RISK_RED} strokeWidth={1.2} vectorEffect="non-scaling-stroke" className="geo-risk-pulse" />}
                <circle r={(picked ? 3.4 : 2.2) / k} fill={RISK_RED} fillOpacity={i.severity === "low" ? 0.55 : 0.95} />
              </g>
            );
          })}
        </g>
      </svg>
      {hover && (
        <div className="pointer-events-none absolute z-10 max-w-[260px] rounded-lg border border-surface-line bg-surface-card/95 px-3 py-2 text-xs shadow-xl backdrop-blur"
          style={{ left: Math.min(hover.x + 14, (wrap.current?.clientWidth ?? 600) - 270), top: hover.y + 14 }} role="tooltip">
          <div className="font-semibold text-navy-900">{hover.title}</div>
          {hover.lines.map((l) => <div key={l} className="text-navy-700">{l}</div>)}
        </div>
      )}
    </div>
  );
}
