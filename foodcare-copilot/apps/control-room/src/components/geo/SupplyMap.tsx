import { Component, lazy, ReactNode, Suspense, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { GeoSel, useApp } from "../../context";
import { openCopilot } from "../../screens/Copilot";
import { HBars } from "../charts";
import Map2D from "./Map2D";
import {
  GeoNode, money, Network, prefersReducedMotion, Provenance, PROVENANCE_STYLE, RISK_RED, scopeOf, TIER_COLOR, TIER_LABEL,
  TIERS, useNetwork, useRisk, webglAvailable,
} from "./geoData";

const Globe3D = lazy(() => import("./Globe3D"));

type Overlay = "revenue" | "exposure" | "performance" | "risk";
type Tab = "financial" | "forecast" | "quality" | "trace";
const OVERLAYS: Record<Overlay, string> = {
  revenue: "Regional revenue", exposure: "Financial exposure (revenue dependent on sites)",
  performance: "Supplier quality pass rate", risk: "Operational risk (incidents, 365 days)",
};
const TABS: Record<Tab, string> = { financial: "Financial impact", forecast: "Forecast & risk", quality: "Quality incidents", trace: "OriginTrace" };

class GlobeBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

export function ProvenanceBadge({ kind, label }: { kind: Provenance; label?: string }) {
  const text = { verified: "Verified", operational_record: "Operational record", modeled: "Modelled", synthetic: "Synthetic" }[kind];
  return <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${PROVENANCE_STYLE[kind]}`} title={label}>{text}</span>;
}

/** Reusable Global Supply Chain Intelligence map: one implementation shared by every page. */
export default function SupplyMap({ title = "Global supply chain intelligence", defaultTab = "financial", defaultOverlay = "revenue" }:
  { title?: string; defaultTab?: Tab; defaultOverlay?: Overlay }) {
  const { data: net, error } = useNetwork();
  const { geo, setGeo } = useApp();
  const reduced = prefersReducedMotion();
  const [mode, setMode] = useState<"3d" | "2d">(() => (!reduced && webglAvailable() && window.innerWidth >= 768 ? "3d" : "2d"));
  const [overlay, setOverlay] = useState<Overlay>(defaultOverlay);
  const [tab, setTab] = useState<Tab>(defaultTab);
  const [simulated, setSimulated] = useState(false);
  const [renderMs, setRenderMs] = useState<number | null>(null);

  if (error) return <section className="card"><p className="text-sm text-brick-700">Could not load the supply network: {error}</p></section>;
  if (!net) return <section className="card" aria-busy="true"><p className="text-sm text-navy-600">Loading the global supply network…</p></section>;
  return <Loaded {...{ net, geo, setGeo, reduced, mode, setMode, overlay, setOverlay, tab, setTab, simulated, setSimulated, renderMs, setRenderMs, title }} />;
}

function Loaded({ net, geo, setGeo, reduced, mode, setMode, overlay, setOverlay, tab, setTab, simulated, setSimulated, renderMs, setRenderMs, title }: any) {
  const n: Network = net;
  const cur = n.scenario.currency;
  const fmt = (v: number) => money(v, cur);
  const scope = useMemo(() => scopeOf(n, geo), [n, geo.country, geo.node, geo.incident]);
  const countryValue = useMemo(() => {
    const m = new Map<string, number>();
    if (overlay === "revenue") n.countries.forEach((c) => m.set(c.id, c.revenue));
    if (overlay === "risk") n.countries.forEach((c) => m.set(c.id, c.incidents_365d));
    if (overlay === "exposure" || overlay === "performance") {
      const acc = new Map<string, number[]>();
      for (const s of n.nodes) if (s.tier !== "market") acc.set(s.country, [...(acc.get(s.country) ?? []), overlay === "exposure" ? s.revenue_dependent : s.performance.quality_pass_pct]);
      acc.forEach((v, k) => m.set(k, overlay === "exposure" ? v.reduce((a, b) => a + b, 0) : v.reduce((a, b) => a + b, 0) / v.length));
    }
    return m;
  }, [n, overlay]);
  const fmtOverlay = (v: number) => overlay === "performance" ? `${v.toFixed(1)}%` : overlay === "risk" ? `${v} incidents` : fmt(v);
  const select = (g: GeoSel) => setGeo(g);
  const mapProps = { net: n, scope, sel: geo, onSelect: select, countryValue, overlayLabel: OVERLAYS[overlay as Overlay], formatValue: overlay === "revenue" || overlay === "exposure" ? fmt : fmtOverlay,
    simulated, reducedMotion: reduced, onRendered: setRenderMs };
  const flat = <Map2D {...mapProps} formatValue={fmtOverlay} />;
  const scopeRevenue = scope.node ? scope.node.revenue_dependent : scope.country ? scope.country.revenue : n.scenario.annual_revenue;

  return (
    <section className="card relative overflow-hidden" aria-labelledby="geo-title" data-testid="supply-map" data-render-ms={renderMs ?? ""} data-mode={mode}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="geo-title" className="text-lg font-semibold">{title}</h2>
          <p className="text-xs text-navy-600">{n.scenario.name}: {n.scenario.countries} countries, {fmt(n.scenario.annual_revenue)} annual revenue · configurable in <code>fixtures/geo/{n.scenario.path}</code></p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div role="group" aria-label="Map view" className="inline-flex overflow-hidden rounded-lg border border-surface-line">
            {(["3d", "2d"] as const).map((m) => (
              <button key={m} className={`px-2.5 py-1 ${mode === m ? "bg-royal-600 text-white" : "text-navy-700 hover:bg-surface-raised"}`} aria-pressed={mode === m}
                onClick={() => setMode(m)} disabled={m === "3d" && !webglAvailable()}>{m === "3d" ? "3D globe" : "2D map"}</button>
            ))}
          </div>
          <label className="flex items-center gap-1 text-navy-700">Overlay
            <select className="rounded-lg border border-surface-line bg-surface-raised px-1.5 py-1" value={overlay} onChange={(e) => setOverlay(e.target.value as Overlay)}>
              {Object.entries(OVERLAYS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-navy-700" title={n.tracking.note}>
            <input type="checkbox" checked={simulated} onChange={(e) => setSimulated(e.target.checked)} /> Simulated movement
          </label>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-gold-500/40 bg-[#1a2433] px-3 py-1.5 text-[11px] text-gold-300" role="note">
        <ProvenanceBadge kind="synthetic" /> {n.scenario.disclaimer}
        {simulated && <span className="rounded bg-gold-500 px-1.5 py-0.5 font-bold text-[#091a30]">SIMULATED MOVEMENT · {n.tracking.events} tracking events exist</span>}
      </div>

      <div className="mt-3 grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0 rounded-xl border border-surface-line bg-[#050e1c]">
          {mode === "3d" ? (
            <GlobeBoundary fallback={flat}><Suspense fallback={<p className="p-6 text-sm text-navy-600">Loading the 3D globe…</p>}><Globe3D {...mapProps} /></Suspense></GlobeBoundary>
          ) : flat}
          <Legend net={n} />
        </div>
        <SidePanel net={n} scope={scope} geo={geo} setGeo={setGeo} fmt={fmt} scopeRevenue={scopeRevenue} />
      </div>

      <div className="mt-4">
        <div role="tablist" aria-label="Geographic analysis" className="flex flex-wrap gap-1 border-b border-surface-line">
          {(Object.keys(TABS) as Tab[]).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
              className={`-mb-px rounded-t-lg border-b-2 px-3 py-1.5 text-sm ${tab === t ? "border-ice-400 font-medium text-navy-900" : "border-transparent text-navy-600 hover:text-navy-900"}`}>{TABS[t]}</button>
          ))}
        </div>
        <div role="tabpanel" className="pt-3">
          {tab === "financial" && <Financial net={n} scope={scope} fmt={fmt} />}
          {tab === "forecast" && <Forecast scope={scope} fmt={fmt} />}
          {tab === "quality" && <Quality scope={scope} setGeo={setGeo} />}
          {tab === "trace" && <Trace net={n} scope={scope} />}
        </div>
      </div>
      <TableView net={n} scope={scope} setGeo={setGeo} fmt={fmt} />
    </section>
  );
}

function Legend({ net }: { net: Network }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-surface-line px-3 py-2 text-[11px] text-navy-700">
      {TIERS.map((t) => <span key={t} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: TIER_COLOR[t] }} />{TIER_LABEL[t]}</span>)}
      <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: RISK_RED }} />Quality incident</span>
      <span className="ml-auto inline-flex flex-wrap gap-1.5">
        {(Object.entries(net.provenance) as [Provenance, { label: string; count: number }][]).map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1" data-testid={`prov-${k}`}><ProvenanceBadge kind={k} label={v.label} />{v.count}</span>
        ))}
      </span>
    </div>
  );
}

function SidePanel({ net, scope, geo, setGeo, fmt, scopeRevenue }: any) {
  const crumbs: { label: string; sel: GeoSel }[] = [{ label: "Global network", sel: {} }];
  if (scope.country) crumbs.push({ label: scope.country.name, sel: { country: scope.country.id } });
  if (scope.node) crumbs.push({ label: `${TIER_LABEL[scope.node.tier as keyof typeof TIER_LABEL]} ${scope.node.id}`, sel: { country: scope.node.country, node: scope.node.id } });
  if (scope.incident) crumbs.push({ label: scope.incident.id, sel: geo });
  const high = scope.incidents.filter((i: any) => i.severity === "high").length;
  return (
    <aside className="space-y-3" aria-label="Selection">
      <nav aria-label="Geographic selection" className="flex flex-wrap items-center gap-1 text-xs">
        {crumbs.map((c, i) => (
          <span key={c.label} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-navy-600">›</span>}
            <button className={`rounded px-1.5 py-0.5 ${i === crumbs.length - 1 ? "bg-royal-600/20 font-semibold text-navy-900" : "text-ice-300 hover:underline"}`} onClick={() => setGeo(c.sel)}>{c.label}</button>
          </span>
        ))}
      </nav>
      {scope.node && <p className="text-sm font-semibold text-navy-900">{scope.node.name}</p>}
      {scope.incident && <p className="rounded-lg border border-[#f43f5e]/50 bg-[#3d2230] px-2 py-1.5 text-xs text-[#fda4af]"><b>{scope.incident.kind}</b> · {scope.incident.date} · {scope.incident.severity} · lot {scope.incident.batch} <ProvenanceBadge kind={scope.incident.provenance} /></p>}
      <div className="grid grid-cols-2 gap-2">
        <Kpi label={scope.node ? "Revenue dependent" : "Revenue in scope"} value={fmt(scopeRevenue)} />
        <Kpi label="Sites in scope" value={String(scope.node ? scope.nodeIds.size : scope.country ? scope.country.sites : net.nodes.length)} />
        <Kpi label="Incidents (365 d)" value={String(scope.incidents.length)} sub={`${high} high severity`} tone={high ? "risk" : undefined} />
        <Kpi label="Routes in scope" value={String(scope.edges.length)} sub="no tracking events" />
      </div>
      <p className="text-[11px] text-navy-600">Click a country, site or red incident on the map, or use the table view below. The selection follows you to Inventory, Quality Intelligence and Ask Copilot, and is kept in the page address.</p>
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary text-xs" onClick={() => openCopilot(originQuestion(scope))}><span aria-hidden>✦</span> Investigate with OriginTrace</button>
        {!scope.all && <button className="btn-ghost text-xs" onClick={() => setGeo({})}>Clear selection</button>}
      </div>
    </aside>
  );
}

export function originQuestion(scope: ReturnType<typeof scopeOf>): string {
  if (scope.incident) return `OriginTrace: trace ${scope.incident.id} back to the farm`;
  if (scope.node) return `OriginTrace: trace ${scope.node.id} back to the farm`;
  if (scope.country) return `OriginTrace: what is the supply chain exposure in ${scope.country.name}?`;
  return "OriginTrace: summarise global supply chain risk and exposure";
}

function Kpi({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "risk" }) {
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${tone === "risk" ? "border-[#f43f5e]/50" : "border-surface-line"} bg-surface-raised/50`}>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-navy-600">{label}</div>
      <div className={`font-mono text-base ${tone === "risk" ? "text-[#fda4af]" : "text-navy-900"}`}>{value}</div>
      {sub && <div className="text-[10px] text-navy-600">{sub}</div>}
    </div>
  );
}

function Financial({ net, scope, fmt }: any) {
  const countries = scope.country ? [scope.country] : net.countries.slice(0, 10);
  const byTier = TIERS.filter((t) => t !== "market").map((t) => ({
    label: TIER_LABEL[t], value: (net.nodes as GeoNode[]).filter((x) => x.tier === t && scope.nodeIds.has(x.id)).reduce((a, b) => a + b.revenue_dependent, 0),
  }));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div>
        <div className="label mb-2">{scope.country ? "Country revenue" : "Top 10 countries by revenue"} <ProvenanceBadge kind="synthetic" /></div>
        <HBars ariaLabel="Revenue by country" format={fmt} items={countries.map((c: any) => ({ label: c.name, value: c.revenue, note: `${c.revenue_share_pct}% of total` }))} />
      </div>
      <div>
        <div className="label mb-2">Revenue that depends on each tier in scope <ProvenanceBadge kind="synthetic" /></div>
        <HBars ariaLabel="Revenue dependent by tier" format={fmt} items={byTier} />
        <p className="mt-2 text-[11px] text-navy-600">Formula: each market carries its country's revenue; every upstream site carries the revenue of what it feeds, split evenly across that site's suppliers. Overlapping chains mean tiers are not additive. {fmt(net.attribution.attributed_to_market_sites)} of {fmt(net.attribution.total)} is traced to sites: {net.attribution.note}</p>
      </div>
    </div>
  );
}

function Forecast({ scope, fmt }: any) {
  const risk = useRisk(scope.node ? undefined : scope.country?.id, scope.node?.id ?? scope.incident?.node_id);
  if (!risk) return <p className="text-sm text-navy-600">Running the simulation…</p>;
  const maxE = Math.max(...risk.horizons.map((h) => h.exposure.p90), 1);
  return (
    <div className="space-y-3" data-testid="risk-bands">
      <p className="text-xs text-navy-600"><ProvenanceBadge kind="modeled" /> {risk.method} {risk.draws} draws · {risk.scope.sites} site(s) in scope.</p>
      {risk.horizons.map((h) => (
        <div key={h.days} className="grid grid-cols-[64px_1fr_190px] items-center gap-3 text-xs" aria-label={`${h.days} days: exposure median ${fmt(h.exposure.p50)}, 80% band ${fmt(h.exposure.p10)} to ${fmt(h.exposure.p90)}`}>
          <span className="font-semibold text-navy-900">{h.days} days</span>
          <div className="relative h-5 rounded bg-surface-raised/60">
            <div className="absolute inset-y-1 rounded bg-ice-400/30 ring-1 ring-ice-400/60" style={{ left: `${(h.exposure.p10 / maxE) * 100}%`, width: `${Math.max(0.6, ((h.exposure.p90 - h.exposure.p10) / maxE) * 100)}%` }} />
            <div className="absolute inset-y-0 w-0.5 bg-gold-400" style={{ left: `${(h.exposure.p50 / maxE) * 100}%` }} />
          </div>
          <span className="font-mono text-navy-700">{fmt(h.exposure.p50)} <span className="text-navy-600">({fmt(h.exposure.p10)}–{fmt(h.exposure.p90)})</span><br />{h.incidents.p50} incidents ({h.incidents.p10}–{h.incidents.p90})</span>
        </div>
      ))}
      <p className="text-[11px] text-navy-600">Shaded band = 10th to 90th percentile (uncertainty); gold line = median. Wider bands at longer horizons mean less certainty, not more risk.</p>
    </div>
  );
}

function Quality({ scope, setGeo }: any) {
  const months = new Map<string, number>();
  for (const i of scope.incidents) months.set(i.date.slice(0, 7), (months.get(i.date.slice(0, 7)) ?? 0) + 1);
  const series = [...months.entries()].sort().slice(-12);
  const max = Math.max(1, ...series.map(([, v]) => v));
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <ul className="max-h-64 space-y-1 overflow-y-auto pr-1 text-xs" aria-label="Quality incidents in scope">
        {scope.incidents.slice(0, 60).map((i: any) => (
          <li key={i.id}>
            <button className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-surface-raised ${scope.incident?.id === i.id ? "bg-surface-raised" : ""}`}
              onClick={() => setGeo({ country: i.country, node: i.node_id, incident: i.id })}>
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: RISK_RED, opacity: i.severity === "low" ? 0.5 : 1 }} />
              <span className="font-mono text-navy-600">{i.date}</span><span className="flex-1 truncate text-navy-900">{i.kind}</span>
              <span className="text-navy-600">{i.severity}</span><ProvenanceBadge kind={i.provenance} />
            </button>
          </li>
        ))}
        {scope.incidents.length === 0 && <li className="text-navy-600">No incidents in this scope.</li>}
      </ul>
      <div>
        <div className="label mb-2">Historical recurrence (incidents per month)</div>
        <div className="flex h-24 items-end gap-1" role="img" aria-label={`Incidents per month: ${series.map(([m, v]) => `${m} ${v}`).join(", ")}`}>
          {series.map(([m, v]) => <div key={m} className="flex-1 rounded-t bg-[#f43f5e]/70" style={{ height: `${(v / max) * 100}%` }} title={`${m}: ${v}`} />)}
        </div>
        <Link className="mt-2 inline-block text-xs text-ice-300 hover:underline" to="/quality-intel">Open Quality Intelligence (selection kept) →</Link>
      </div>
    </div>
  );
}

function Trace({ net, scope }: any) {
  const nodeId = scope.node?.id;
  const [detail, setDetail] = useState<any>(null);
  useEffect(() => {
    setDetail(null);
    if (nodeId) api(`/api/geo/node/${nodeId}`).then(setDetail).catch(() => setDetail(null));
  }, [nodeId]);
  if (!nodeId) return <p className="text-sm text-navy-600">Select a site or an incident to trace it back to the farm. For a country or the whole network, use "Investigate with OriginTrace".</p>;
  if (!detail) return <p className="text-sm text-navy-600">Tracing…</p>;
  return (
    <div className="space-y-2 text-xs">
      <p className="text-navy-700">{detail.upstream_paths.length} upstream path(s) · feeds {detail.downstream.length} downstream site(s) · {net.scenario.currency} {detail.financial.revenue_dependent.toLocaleString()} revenue dependent <ProvenanceBadge kind="synthetic" /></p>
      <ol className="space-y-1.5" aria-label="Upstream paths">
        {detail.upstream_paths.slice(0, 6).map((p: any[], i: number) => (
          <li key={i} className="flex flex-wrap items-center gap-1">
            {p.map((x, j) => (
              <span key={x.id} className="inline-flex items-center gap-1">
                {j > 0 && <span className="text-navy-600">←</span>}
                <span className="rounded border border-surface-line px-1.5 py-0.5" style={{ borderColor: TIER_COLOR[x.tier as keyof typeof TIER_COLOR] }}>{TIER_LABEL[x.tier as keyof typeof TIER_LABEL]} · {x.country_name}</span>
              </span>
            ))}
          </li>
        ))}
      </ol>
      <button className="btn-primary text-xs" onClick={() => openCopilot(originQuestion(scope))}><span aria-hidden>✦</span> Ask OriginTrace to explain this chain</button>
    </div>
  );
}

function TableView({ net, scope, setGeo, fmt }: any) {
  const sites = (net.nodes as GeoNode[]).filter((x) => scope.nodeIds.has(x.id)).slice(0, 40);
  return (
    <details className="mt-3 text-xs">
      <summary className="cursor-pointer text-navy-700">Table view (keyboard and screen-reader access to every country and site)</summary>
      <div className="mt-2 grid gap-4 lg:grid-cols-2">
        <table className="table">
          <thead><tr><th>Country</th><th>Revenue</th><th>Sites</th><th>Incidents</th><th /></tr></thead>
          <tbody>{(scope.country ? [scope.country] : net.countries.slice(0, 25)).map((c: any) => (
            <tr key={c.id}><td>{c.name}</td><td className="font-mono">{fmt(c.revenue)}</td><td>{c.sites}</td><td>{c.incidents_365d}</td>
              <td><button className="text-ice-300 hover:underline" onClick={() => setGeo({ country: c.id })} aria-label={`Select ${c.name}`}>Select</button></td></tr>
          ))}</tbody>
        </table>
        <table className="table">
          <thead><tr><th>Site</th><th>Tier</th><th>Country</th><th /></tr></thead>
          <tbody>{sites.map((s) => (
            <tr key={s.id}><td className="font-mono">{s.id}</td><td>{TIER_LABEL[s.tier]}</td><td>{s.country_name}</td>
              <td><button className="text-ice-300 hover:underline" onClick={() => setGeo({ country: s.country, node: s.id })} aria-label={`Select ${s.name}`}>Select</button></td></tr>
          ))}</tbody>
        </table>
      </div>
    </details>
  );
}
