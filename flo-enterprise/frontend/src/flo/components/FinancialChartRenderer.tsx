import type ReactECharts from "echarts-for-react";
import { Download, Info, MessageSquareText, MousePointerClick, Table2 } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { DataGrid, toCSV } from "@/components/ChartCard";
import { EChart } from "@/components/EChart";
import { GeoMap } from "@/components/GeoMap";
import { Badge, Button, Select, cn } from "@/components/ui";
import { useApp } from "@/lib/app";
import { tokens } from "@/lib/chartTheme";
import { buildOption, isRenderable, specRows } from "../chartOptions";
import { formatDelta, formatValue, PROVENANCE_LABEL, prefersReducedMotion } from "../format";
import type { ChartSpec, MessageContext } from "../types";
import { DataFreshnessIndicator } from "./DataFreshnessIndicator";

function save(href: string, name: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  a.click();
}

function Scorecard({ spec }: { spec: ChartSpec }) {
  const tone = { ok: "bg-pos", warn: "bg-warn", crit: "bg-crit", neutral: "bg-line", denied: "bg-crit", skipped: "bg-line" } as const;
  return (
    <ul className="max-h-80 space-y-2 overflow-y-auto scroll-thin pr-1">
      {spec.nodes.map((n) => (
        <li key={n.id} className="text-xs">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-ink/90" title={n.name}>{n.name}</span>
            {n.meta?.status && <span className="text-muted">{String(n.meta.status).replace(/_/g, " ")}</span>}
            {n.value != null && spec.unit === "%" && <span className="tabular-nums text-muted">{Math.round(n.value)}%{n.x != null ? ` / plan ${Math.round(n.x)}%` : ""}</span>}
          </div>
          <div className="relative mt-1 h-1.5 rounded bg-line/60" role="progressbar" aria-valuenow={n.value ?? 0} aria-valuemin={0} aria-valuemax={100} aria-label={n.name}>
            <div className={cn("h-1.5 rounded", tone[n.status ?? "neutral"])} style={{ width: `${Math.min(100, Math.max(n.status === "neutral" ? 4 : 0, n.value ?? 0))}%` }} />
            {n.x != null && <div className="absolute -top-0.5 h-2.5 w-0.5 bg-ink/70" style={{ left: `${Math.min(100, n.x)}%` }} />}
          </div>
          {n.meta?.needs && n.status !== "ok" && <div className="mt-0.5 text-[11px] text-muted">Needs: {String(n.meta.needs)}</div>}
        </li>
      ))}
    </ul>
  );
}

export function FinancialChartRenderer({ spec, onFollowup, index = 0, height = 280, inline = false }: {
  spec: ChartSpec; onFollowup: (q: string, ctx?: MessageContext) => void; index?: number; height?: number; inline?: boolean;
}) {
  const { theme } = useApp();
  const ref = useRef<ReactECharts>(null);
  const [view, setView] = useState<"chart" | "table" | "lineage">("chart");
  const ok = isRenderable(spec);
  const option = useMemo(() => (ok ? buildOption(spec, tokens(), !prefersReducedMotion()) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [spec, theme, ok]);
  const rows = useMemo(() => (ok ? specRows(spec) : []), [spec, ok]);
  // LumaTrade-style headline: latest value of the primary line and its change across the window, from this chart's own data
  const hero = useMemo(() => {
    if (!ok || !["line", "area"].includes(spec.chart_type)) return null;
    const s0 = spec.series.find((x) => x.role !== "baseline");
    const vals = (s0?.values ?? []).filter((v): v is number => v != null);
    if (!s0 || vals.length < 2) return null;
    const first = vals[0], last = vals[vals.length - 1];
    const unit = s0.unit || spec.unit;
    const delta = unit === "%" ? last - first : first !== 0 ? last / first - 1 : null;
    return { name: s0.name, last, unit, delta, deltaText: delta == null ? "" : unit === "%" ? formatDelta(delta, "pp") : formatDelta(delta, "%") };
  }, [spec, ok]);
  if (!ok) {
    return <div className="rounded-xl border border-crit/40 bg-crit/10 p-3 text-sm" role="alert">Chart not shown: unsupported specification.</div>;
  }
  const can = (i: string) => spec.interactions.includes(i as never);
  const drill = (name: string) => spec.drilldown && can("drilldown") && onFollowup(spec.drilldown.prompt_template.replace("{value}", name), { focus: name });
  const exportPng = () => {
    const inst = ref.current?.getEchartsInstance();
    if (inst) save(inst.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: tokens().surface }), `flo-${spec.chart_id}.png`);
  };
  const exportCsv = () => save(URL.createObjectURL(new Blob([toCSV(rows)], { type: "text/csv" })), `flo-${spec.chart_id}.csv`);
  const summary = `${spec.title}. ${spec.subtitle}`.trim();
  return (
    <section className="flo-rise flex min-w-0 flex-col rounded-2xl border border-line/70 bg-gradient-to-b from-card to-card/70 p-4 shadow-[0_12px_32px_-20px_rgb(0_0_0/0.6)]" style={{ animationDelay: `${120 + index * 70}ms` }}
      data-chart={inline ? undefined : spec.chart_id} data-inline-chart={inline ? spec.chart_id : undefined} aria-label={inline ? `${spec.title} (in answer)` : spec.title}>
      <header className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{spec.title}</h3>
          {spec.subtitle && <p className="text-xs text-muted">{spec.subtitle}</p>}
          {hero && !inline && (
            <div role="group" className="mt-2 flex items-baseline gap-2" aria-label={`Latest ${hero.name}: ${formatValue(hero.last, hero.unit)}`}>
              <span className="text-2xl font-semibold tracking-tight tabular-nums">{formatValue(hero.last, hero.unit)}</span>
              {hero.delta != null && (
                <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums", hero.delta >= 0 ? "bg-pos/15 text-pos" : "bg-crit/15 text-crit")}>
                  {hero.deltaText} <span className="font-normal opacity-80">over window</span></span>
              )}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1">
          {spec.available_filters.map((f) => f.id === "months" ? (
            <div key={f.id} role="radiogroup" aria-label={`${f.label} for ${spec.title}`} className="flex rounded-full border border-line bg-bg/50 p-0.5">
              {f.options.map((o) => (
                <button key={String(o)} role="radio" aria-checked={String(f.value) === String(o)}
                  onClick={() => String(f.value) !== String(o) && onFollowup(`Show ${spec.title.toLowerCase()} for the last ${o} months.`, { months: Number(o) })}
                  className={cn("rounded-full px-2.5 py-0.5 text-[11px] tabular-nums transition-colors",
                    String(f.value) === String(o) ? "bg-card text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink")}>{o}m</button>
              ))}
            </div>
          ) : (
            <Select key={f.id} aria-label={`${f.label} for ${spec.title}`} value={String(f.value)} className="h-7 text-xs"
              onChange={(e) => {
                const v = e.target.value;
                onFollowup(f.id === "months" ? `Show ${spec.title.toLowerCase()} for the last ${v} months.` : `Show ${spec.title.toLowerCase()} by ${v.replace(/_/g, " ")}.`,
                  f.id === "months" ? { months: Number(v) } : { group_by: v });
              }}>
              {f.options.map((o) => <option key={String(o)} value={String(o)}>{f.id === "months" ? `${o} months` : String(o).replace(/_/g, " ")}</option>)}
            </Select>
          ))}
          <Button size="icon" variant="ghost" aria-label="Table view" title="Table view" aria-pressed={view === "table"} onClick={() => setView(view === "table" ? "chart" : "table")}>
            <Table2 className="h-4 w-4" /></Button>
          <Button size="icon" variant="ghost" aria-label="Methodology and source lineage" title="Methodology & lineage" aria-pressed={view === "lineage"}
            onClick={() => setView(view === "lineage" ? "chart" : "lineage")}><Info className="h-4 w-4" /></Button>
          <Button size="icon" variant="ghost" aria-label={`Export ${spec.title}`} title="Export PNG (chart) and CSV (data)"
            onClick={() => { if (option && view === "chart") exportPng(); exportCsv(); }}><Download className="h-4 w-4" /></Button>
          {can("explain") && (
            <Button size="sm" variant="ghost" className="text-gold" onClick={() => onFollowup(`Explain the ${spec.title.toLowerCase()} chart.`, { focus: spec.title })}
              aria-label={`Explain with FLO: ${spec.title}`}><MessageSquareText className="h-3.5 w-3.5" />Explain</Button>
          )}
        </div>
      </header>
      {view === "table" ? <DataGrid rows={rows as any} /> : view === "lineage" ? (
        <div role="group" className="space-y-2 text-xs" aria-label="Lineage">
          {spec.lineage.methodology && <p><span className="font-semibold">Methodology: </span>{spec.lineage.methodology}</p>}
          {spec.metrics.map((m) => <p key={m.id}><span className="text-gold">{m.name}</span> — {m.definition} {m.formula && <code className="text-muted">{m.formula}</code>}</p>)}
          <p className="text-muted">Sources: {spec.lineage.sources.join(", ") || "—"} · tools: {spec.lineage.tools.join(", ") || "—"}</p>
          <p className="text-muted">Dataset {spec.lineage.dataset_version ?? "—"} · semantic layer {spec.lineage.semantic_layer_version ?? "—"} · schema {spec.schema_version} · produced by {spec.agent}</p>
        </div>
      ) : spec.chart_type === "scorecard" ? <Scorecard spec={spec} /> : spec.chart_type === "geo" ? (
        <GeoMap height={height} rows={spec.nodes.map((n) => ({ country: n.id, region: n.group ?? "", lat: n.lat!, lon: n.lon!, value: n.value ?? 0, weight: Number(n.meta?.weight ?? 0) }))}
          onSelect={(r) => drill(r.country)} />
      ) : option && (
        <EChart ref={ref} option={option} height={height} ariaLabel={summary}
          onClick={spec.drilldown && can("drilldown") ? (p: any) => drill(String(p.name ?? p.data?.name ?? "")) : undefined} />
      )}
      <footer className="mt-2 flex flex-wrap items-center gap-2">
        <DataFreshnessIndicator asOf={spec.lineage.as_of} refreshedAt={spec.lineage.refreshed_at} synthetic={spec.lineage.synthetic && spec.provenance === "platform_synthetic"}
          sources={spec.lineage.sources} compact />
        {spec.provenance !== "platform_synthetic" && <Badge tone={spec.provenance === "illustrative_assumption" ? "warn" : "blue"}>{PROVENANCE_LABEL[spec.provenance]}</Badge>}
        {spec.drilldown && can("drilldown") && <span className="flex items-center gap-1 text-[11px] text-muted"><MousePointerClick className="h-3 w-3" />click to drill down</span>}
        {spec.note && <span className="w-full text-[11px] text-muted">{spec.note}</span>}
      </footer>
    </section>
  );
}

export const unitText = (spec: ChartSpec, v: number) => formatValue(v, spec.unit);
