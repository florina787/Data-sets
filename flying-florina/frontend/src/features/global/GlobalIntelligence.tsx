import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Download, Globe2, Map as MapIcon, Search, Square } from "lucide-react";
import { Badge, Card, ErrorBox, Kpi, PageHeader, Skeleton } from "@/components/ui";
import { Chart } from "@/components/Chart";
import { download, get } from "@/lib/api";
import { GlobeMap, scale, webglAvailable, type MapMode, type Selection } from "./GlobeMap";
import { HORIZONS, LAYERS, type LayerId, type MapState } from "./types";

const usd = (v?: number) => (v == null ? "—" : `$${(v / 1e6).toFixed(2)}M`);
const pct = (v?: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export function HorizonSlider({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  const i = HORIZONS.indexOf(value as (typeof HORIZONS)[number]);
  return (
    <div className="glass px-4 py-3" data-testid="timeline">
      <div className="flex items-center justify-between">
        <p className="label">Predictive timeline</p>
        <p className="text-xs text-cyan num">{value === 0 ? "TODAY" : `+${value} DAYS`}</p>
      </div>
      <input type="range" min={0} max={HORIZONS.length - 1} step={1} value={i < 0 ? 0 : i} aria-label="Forecast horizon"
        onChange={(e) => onChange(HORIZONS[Number(e.target.value)])} className="timeline mt-2 w-full" />
      <div className="mt-1 flex justify-between text-[10px] tracking-wider text-faint">
        {HORIZONS.map((h) => (
          <button key={h} onClick={() => onChange(h)} className={h === value ? "font-semibold text-cyan" : "hover:text-[var(--text)]"}>{h === 0 ? "TODAY" : `+${h}D`}</button>
        ))}
      </div>
    </div>
  );
}

export function GlobalIntelligence() {
  const [params] = useSearchParams();
  const [horizon, setHorizon] = useState<number>(Number(params.get("horizon") ?? 30));
  const [layer, setLayer] = useState<LayerId>((params.get("layer") as LayerId) ?? "inventory");
  const [category, setCategory] = useState<string>(params.get("category") ?? "");
  const [mode, setMode] = useState<MapMode>(() => (webglAvailable() && window.innerWidth >= 640 ? "globe" : "lite"));
  const [sel, setSel] = useState<Selection>(null);
  const [q, setQ] = useState("");
  const [focus, setFocus] = useState<{ lon: number; lat: number; ts: number } | null>(null);
  const [cmp, setCmp] = useState<[string, string]>(["Europe", "Asia-Pacific"]);
  const tl = useQuery({ queryKey: ["global-timeline", category], queryFn: () => get<Record<string, MapState>>(`/api/global/timeline${category ? `?category=${category}` : ""}`), staleTime: 300_000 });
  const search = useQuery({ queryKey: ["global-search", q], queryFn: () => get<{ kind: string; id: string; name: string; city: string; lat: number; lon: number }[]>(`/api/global/search?q=${encodeURIComponent(q)}`), enabled: q.length >= 2 });
  const state = tl.data?.data[String(horizon)];
  const facility = sel?.kind === "facility" ? state?.facilities.find((f) => f.id === sel.id) : undefined;
  const supplier = sel?.kind === "supplier" ? state?.suppliers.find((s) => s.id === sel.id) : undefined;
  const disruption = sel?.kind === "disruption" ? state?.disruptions.find((d) => d.id === sel.id) : undefined;
  const topCat = category || facility?.shortages?.[0]?.category_id || "hydraulic_pump";
  const hist = useQuery({ queryKey: ["series", topCat, facility?.id], enabled: !!facility && facility.kind === "mro",
    queryFn: () => get<{ category: string; history: { week_start: string; removals: number }[]; forecast: { horizon_days: number; p10: number; p50: number; p90: number }[] }>(`/api/forecast/series?category=${topCat}&facility=${facility?.id}`) });
  const catName = useMemo(() => Object.fromEntries((state?.categories ?? []).map((c) => [c.id, c.name])), [state]);
  if (tl.error) return <ErrorBox error={tl.error} onRetry={() => tl.refetch()} />;
  const totals = state ? {
    demand: state.facilities.reduce((a, f) => a + (f.demand_p50 ?? 0), 0), shortages: state.facilities.reduce((a, f) => a + (f.shortage_count ?? 0), 0),
    active: state.disruptions.filter((d) => d.phase === "active").length, late: state.suppliers.reduce((a, s) => a + s.late_probability, 0) / Math.max(1, state.suppliers.length),
  } : null;
  const regionData = state?.regions.filter((r) => cmp.includes(r.region)) ?? [];
  return (
    <div className="space-y-4">
      <PageHeader title="Global Aerospace Intelligence" icon={<Globe2 className="h-5 w-5" />}
        subtitle="Facilities, suppliers, component forecasts, inventory, disruptions and recovery on one map. Forecasts are computed by models, never by the language model."
        actions={<button className="btn btn-ghost" onClick={() => download(`/api/global/report?horizon=${horizon}`, `global_intelligence_${horizon}d.md`)}><Download className="h-4 w-4" />Export report</button>} />
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="gold">SYNTHETIC DEMONSTRATION DATA</Badge>
        {state && <span className="text-xs muted">Data as of {state.freshness.data_as_of} · models built {state.freshness.models_built_at.slice(0, 16).replace("T", " ")} · {state.freshness.model_version}</span>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label={`Removal demand P50 (${horizon ? `+${horizon}d` : "today"})`} value={totals ? totals.demand.toFixed(0) : "…"} hint="Sum over MRO hubs, units" />
        <Kpi label="Projected shortages" value={totals?.shortages ?? "…"} tone={totals && totals.shortages > 20 ? "red" : "amber"} hint="Facility × category with ≥20% stockout probability" />
        <Kpi label="Active disruptions" value={totals?.active ?? "…"} hint="Synthetic scenario notices" />
        <Kpi label="Mean supplier late probability" value={totals ? pct(totals.late) : "…"} hint="Lead-time quantile model on open orders" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-faint" />
              <input className="input !pl-8 w-56" placeholder="Search city, facility, supplier" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search locations" />
              {q.length >= 2 && (search.data?.data.length ?? 0) > 0 && (
                <div className="glass absolute z-20 mt-1 w-72 p-1">
                  {search.data?.data.map((h) => (
                    <button key={h.kind + h.id} className="block w-full rounded-lg px-2 py-1.5 text-left text-xs hover:bg-white/5"
                      onClick={() => { setFocus({ lon: h.lon, lat: h.lat, ts: Date.now() }); setSel({ kind: h.kind as "facility", id: h.id }); setQ(""); }}>
                      {h.name} <span className="muted">· {h.city} · {h.kind}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <select className="input" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Component category">
              <option value="">All component categories</option>
              {state?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <div className="ml-auto flex gap-1" role="group" aria-label="Map projection">
              {([["globe", "Globe", Globe2], ["flat", "2D", MapIcon], ["lite", "Lite", Square]] as const).map(([m, label, Icon]) => (
                <button key={m} className={`btn !px-2.5 !py-1 text-xs ${mode === m ? "btn-primary" : "btn-ghost"}`} onClick={() => setMode(m)}
                  disabled={m !== "lite" && !webglAvailable()} title={m === "lite" ? "SVG map, no WebGL" : undefined}><Icon className="h-3.5 w-3.5" />{label}</button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Map layers">
            {LAYERS.map((l, i) => (
              <button key={l.id} role="tab" aria-selected={layer === l.id} onClick={() => setLayer(l.id)}
                className={`rounded-full border px-3 py-1 text-xs transition ${layer === l.id ? "border-cyan/60 bg-cyan/10 text-cyan" : "border-token muted hover:text-[var(--text)]"}`}>
                <span className="mr-1 text-faint">{i + 1}</span>{l.label}
              </button>
            ))}
          </div>
          <div className="panel relative h-[58vh] min-h-[380px] overflow-hidden">
            {state ? <GlobeMap state={state} layer={layer} mode={mode} selection={sel} onSelect={setSel} focus={focus} /> : <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center"><Skeleton className="h-2 w-48" /><p className="text-sm muted">Fitting forecasting models on the synthetic dataset (first start only; results are cached locally)…</p></div>}
            <div className="glass pointer-events-none absolute bottom-3 left-3 max-w-[260px] p-3 text-[11px]">
              <p className="label mb-1">{LAYERS.find((l) => l.id === layer)?.label}</p>
              <Legend layer={layer} />
            </div>
          </div>
          <HorizonSlider value={horizon} onChange={setHorizon} />
        </div>
        <div className="space-y-3">
          <Card title={facility?.name ?? supplier?.name ?? disruption?.title ?? "Select a site"} subtitle={facility ? `${facility.city} · ${facility.region} · ${facility.kind.replace("_", " ")}` : supplier ? `Supplier · ${supplier.city}` : disruption ? `${disruption.kind.replace("_", " ")} · ${disruption.phase}` : "Click a point on the map"}>
            {!sel && <p className="text-sm muted">Facilities, suppliers and disruption notices are clickable. Use the timeline to see the same site at +7…+90 days.</p>}
            {facility && (
              <div className="space-y-3 text-sm" data-testid="facility-panel">
                <div className="grid grid-cols-2 gap-2">
                  <Stat k="Demand P10–P90" v={facility.demand_p50 != null ? `${facility.demand_p10?.toFixed(0)}–${facility.demand_p90?.toFixed(0)}` : "—"} />
                  <Stat k="Mean health" v={facility.health_mean != null ? facility.health_mean.toFixed(2) : "—"} />
                  <Stat k="Units due" v={facility.units_due ?? "—"} />
                  <Stat k="Workload" v={pct(facility.workload_utilisation)} />
                  <Stat k="Cost P50" v={usd(facility.cost_p50_usd)} />
                  <Stat k="High-risk units" v={facility.high_risk_units ?? "—"} />
                </div>
                {!!facility.shortages?.length && (
                  <div>
                    <p className="label mb-1">Projected shortages (+{horizon}d)</p>
                    {facility.shortages.slice(0, 6).map((s) => (
                      <div key={s.category_id} className="flex items-center justify-between border-b border-token py-1 text-xs">
                        <span>{catName[s.category_id] ?? s.category_id}</span>
                        <span className="num" style={{ color: scale(s.stockout_prob) }}>{pct(s.stockout_prob)} stockout · P50 {s.p50.toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {hist.data && (
                  <Chart title={`${hist.data.data.category}: history and forecast`} height={170} spec={{ kind: "line", x: [...hist.data.data.history.slice(-26).map((h) => h.week_start.slice(5)), ...hist.data.data.forecast.map((f) => `+${f.horizon_days}d`)],
                    series: [{ name: "weekly removals", data: [...hist.data.data.history.slice(-26).map((h) => h.removals), ...hist.data.data.forecast.map(() => null)] as number[] },
                      { name: "cumulative forecast P50", data: [...hist.data.data.history.slice(-26).map(() => null), ...hist.data.data.forecast.map((f) => f.p50)] as number[] }] }} />
                )}
                <div className="flex flex-wrap gap-2">
                  <Link className="btn btn-ghost text-xs" to={`/twin?facility=${facility.id}`}>Open digital twins</Link>
                  <Link className="btn btn-ghost text-xs" to={`/forecasting?region=${encodeURIComponent(facility.region)}`}>Forecast details</Link>
                </div>
              </div>
            )}
            {supplier && (
              <div className="space-y-2 text-sm">
                <Stat k="Late-delivery probability (open orders)" v={pct(supplier.late_probability)} />
                <Stat k="Without disruptions" v={pct(supplier.baseline_late_probability)} />
                <Stat k="Disruption days added" v={supplier.disruption_days_added} />
                <p className="text-xs muted">Supplies: {supplier.categories.map((c) => catName[c] ?? c).join(", ")}</p>
                <Link className="btn btn-ghost text-xs" to={`/supply?supplier=${supplier.id}`}>What if this supplier is delayed?</Link>
              </div>
            )}
            {disruption && (
              <div className="space-y-2 text-sm">
                <Badge tone={disruption.severity === "high" ? "red" : "amber"}>{disruption.severity}</Badge> <Badge tone="gray">{disruption.source}</Badge>
                <Stat k="Window" v={`day ${disruption.start_day} → ${disruption.end_day}`} />
                <Stat k="Recovery progress" v={pct(disruption.recovery_progress)} />
                <Stat k="Days to restore" v={disruption.days_to_restore} />
                <Stat k="Capacity cut / lead time added" v={`${pct(disruption.capacity_cut)} / +${disruption.lead_time_add_days}d`} />
                <Link className="btn btn-ghost text-xs" to="/resilience">Simulate this disruption</Link>
              </div>
            )}
          </Card>
          <Card title="Region comparison" subtitle={`+${horizon} days`}>
            <div className="mb-2 flex gap-2">
              {[0, 1].map((i) => (
                <select key={i} className="input flex-1 !py-1 text-xs" value={cmp[i]} aria-label={`Region ${i + 1}`}
                  onChange={(e) => setCmp((c) => (i === 0 ? [e.target.value, c[1]] : [c[0], e.target.value]))}>
                  {state?.regions.map((r) => <option key={r.region}>{r.region}</option>)}
                </select>
              ))}
            </div>
            <table className="ff"><thead><tr><th>Metric</th>{regionData.map((r) => <th key={r.region}>{r.region}</th>)}</tr></thead>
              <tbody>
                <tr><td>Demand P50</td>{regionData.map((r) => <td key={r.region} className="num">{r.demand_p50.toFixed(0)}</td>)}</tr>
                <tr><td>Shortages</td>{regionData.map((r) => <td key={r.region} className="num">{r.shortages}</td>)}</tr>
                <tr><td>Mean health</td>{regionData.map((r) => <td key={r.region} className="num">{r.health_mean?.toFixed(2) ?? "—"}</td>)}</tr>
                <tr><td>Cost P50</td>{regionData.map((r) => <td key={r.region} className="num">{usd(r.cost_p50_usd)}</td>)}</tr>
                <tr><td>Disruptions</td>{regionData.map((r) => <td key={r.region} className="num">{r.disruptions}</td>)}</tr>
              </tbody></table>
          </Card>
        </div>
      </div>
      {state && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Disruption & recovery timeline" subtitle="Synthetic scenario notices (not verified civilian notices)">
            <table className="ff"><thead><tr><th>Notice</th><th>Region</th><th>Phase</th><th>Recovery</th></tr></thead>
              <tbody>{state.disruptions.length ? state.disruptions.map((d) => (
                <tr key={d.id} className="cursor-pointer" onClick={() => { setLayer("disruptions"); setSel({ kind: "disruption", id: d.id }); setFocus({ lon: d.lon, lat: d.lat, ts: Date.now() }); }}>
                  <td>{d.title}</td><td>{d.region}</td><td>{d.phase}</td><td className="num">{pct(d.recovery_progress)}</td></tr>)) : <tr><td colSpan={4} className="muted">No notices active at this horizon.</td></tr>}</tbody></table>
          </Card>
          <Card title="Assumptions and data freshness">
            <ul className="list-disc space-y-1 pl-4 text-xs muted">{state.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          </Card>
        </div>
      )}
    </div>
  );
}

function Stat({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="rounded-lg border border-token bg-white/[0.02] px-2 py-1.5"><p className="text-[10px] uppercase tracking-wider text-faint">{k}</p><p className="num text-sm">{v}</p></div>;
}

function Legend({ layer }: { layer: LayerId }) {
  const bar = <div className="mt-1 h-1.5 rounded-full" style={{ background: "linear-gradient(90deg,#10B981,#F59E0B,#EF4444)" }} />;
  const items: Record<LayerId, React.ReactNode> = {
    facilities: <>Colour = facility type (<span className="text-cyan">MRO</span>, <span className="text-[#14B8A6]">repair</span>, <span className="text-[#38BDF8]">warehouse</span>, <span className="text-[#FBBF24]">manufacturing</span>), green = suppliers. Size = removal demand.</>,
    health: <>Mean projected health of tracked units. Size = units reaching end of life within the horizon.{bar}</>,
    supply: <>Supplier colour and link colour = late-delivery probability; link width = supply share.{bar}</>,
    inventory: <>Highest stockout probability at the site; size = number of short categories.{bar}</>,
    disruptions: <>Synthetic notices by severity (amber/red). Grey = facilities.</>,
    recovery: <>Notice colour = remaining disruption (green = restored). Site size = capacity cut.{bar}</>,
  };
  return <div className="muted leading-relaxed">{items[layer]}</div>;
}
