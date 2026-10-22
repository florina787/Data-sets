import type ReactECharts from "echarts-for-react";
import { Download, Info, MessageSquareText, Table2 } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { useApp } from "@/lib/app";
import type { Lineage } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Badge, Button, Card, ErrorState, Spinner } from "./ui";
import { EChart } from "./EChart";

type Row = Record<string, string | number | null | undefined>;

export function toCSV(rows: Row[]) {
  if (!rows.length) return "";
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return ["# SYNTHETIC DATA - FLO", cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

function save(href: string, name: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  a.click();
}

export function ChartCard({ id, title, subtitle, lineage, option, rows, height, onClick, loading, error, children, actions, askContext }: {
  id: string; title: string; subtitle?: string; lineage?: Lineage; option?: any; rows?: Row[]; height?: number;
  onClick?: (p: any) => void; loading?: boolean; error?: unknown; children?: ReactNode; actions?: ReactNode; askContext?: Record<string, string>;
}) {
  const { ask, lang } = useApp();
  const ref = useRef<ReactECharts>(null);
  const [view, setView] = useState<"chart" | "table" | "lineage">("chart");
  const exportPng = () => {
    const inst = ref.current?.getEchartsInstance();
    if (inst) save(inst.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#162338" }), `flo-${id}.png`);
  };
  const exportCsv = () => rows && save(URL.createObjectURL(new Blob([toCSV(rows)], { type: "text/csv" })), `flo-${id}.csv`);
  return (
    <Card className="flex flex-col p-4" data-chart={id}>
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {actions}
          {rows && <Button size="icon" variant="ghost" aria-label="Table view" title="Table view" aria-pressed={view === "table"}
            onClick={() => setView(view === "table" ? "chart" : "table")}><Table2 className="h-4 w-4" /></Button>}
          {lineage && <Button size="icon" variant="ghost" aria-label="Source lineage and methodology" title="Lineage & methodology"
            aria-pressed={view === "lineage"} onClick={() => setView(view === "lineage" ? "chart" : "lineage")}><Info className="h-4 w-4" /></Button>}
          {(option || rows) && (
            <Button size="icon" variant="ghost" aria-label="Export" title="Export PNG (chart) / CSV (data)"
              onClick={() => (view === "table" || !option ? exportCsv() : (exportPng(), rows && exportCsv()))}><Download className="h-4 w-4" /></Button>
          )}
          <Button size="sm" variant="ghost" className="text-gold" onClick={() => ask({ chart_id: id, title, ...askContext })} aria-label={`${t("explain", lang)}: ${title}`}>
            <MessageSquareText className="h-3.5 w-3.5" />{t("explain", lang)}
          </Button>
        </div>
      </div>
      {loading ? <Spinner /> : error ? <ErrorState error={error} /> : view === "lineage" && lineage ? <LineagePanel l={lineage} /> :
        view === "table" && rows ? <DataGrid rows={rows} /> : (children ?? (option && <EChart ref={ref} option={option} height={height} onClick={onClick} ariaLabel={title} />))}
      {lineage && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
          <span>As of {lineage.as_of}</span><span>·</span><span>refreshed {new Date(lineage.refreshed_at).toLocaleTimeString()}</span>
          <span>·</span><span>{lineage.sources.map((s) => s.category).join(", ")}</span>
          {lineage.synthetic && <Badge tone="gold">synthetic</Badge>}
        </div>
      )}
    </Card>
  );
}

export function LineagePanel({ l }: { l: Lineage }) {
  return (
    <div className="space-y-3 text-xs" aria-label="Lineage">
      <div><span className="font-semibold">Methodology: </span>{l.methodology}</div>
      <div>
        <div className="font-semibold mb-1">Metrics (semantic layer v{l.semantic_layer_version})</div>
        {l.metrics.map((m) => (
          <div key={m.id} className="mb-1"><span className="text-gold">{m.id}</span> — {m.definition} <code className="text-muted">{m.formula}</code> · owner {m.owner}</div>
        ))}
      </div>
      <div>
        <div className="font-semibold mb-1">Sources</div>
        {l.sources.map((s) => (
          <div key={s.system}>{s.system} · {s.mode} · production: {String(s.connected_to_production)} · freshness {s.freshness}</div>
        ))}
      </div>
      <div className="text-muted">Dataset version {l.dataset_version}</div>
    </div>
  );
}

export function DataGrid({ rows, max = 200 }: { rows: Row[]; max?: number }) {
  if (!rows.length) return <div className="p-3 text-sm text-muted">No rows.</div>;
  const cols = Object.keys(rows[0]);
  return (
    <div className="max-h-80 overflow-auto scroll-thin">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-card"><tr>{cols.map((c) => <th key={c} className="px-2 py-1 text-left font-medium text-muted">{c}</th>)}</tr></thead>
        <tbody>{rows.slice(0, max).map((r, i) => <tr key={i} className="border-t border-line/60">{cols.map((c) => <td key={c} className="px-2 py-1 tabular-nums">{fmt(r[c])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

const fmt = (v: unknown) => (typeof v === "number" ? (Math.abs(v) >= 1000 ? v.toLocaleString("en-CA", { maximumFractionDigits: 0 }) : v.toLocaleString("en-CA", { maximumFractionDigits: 4 })) : String(v ?? "—"));
