import { Filter, LayoutDashboard, Wand2 } from "lucide-react";
import { useApp } from "@/app/AppState";
import { ChartCard } from "@/components/charts/ChartCard";
import { Badge } from "@/components/common/ui";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChatResponse } from "@/types/api";

/** A dashboard generated for this one question: layout chosen from the analysis type, every chart copied from a verified result. */
export function DashboardView({ r }: { r: ChatResponse }) {
  const { ask, busy } = useApp();
  const d = r.dashboard;
  if (!d) return null;
  const byId = Object.fromEntries(r.charts.map((c) => [c.chart_id, c]));
  return (
    <div className="space-y-4" data-testid="dashboard-view">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-gradient-to-r from-indigo/[0.08] to-transparent px-4 py-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold text-ink"><LayoutDashboard className="h-4 w-4 text-indigo" />{d.title}</p>
          <p className="mt-0.5 text-[11px] text-faint">Built for: “{d.generated_from}” · operations: {d.operations.join(", ") || "retrieval only"}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Active filters">
          <Filter className="h-3.5 w-3.5 text-faint" aria-hidden />
          {d.filters.map((f) => <Badge key={f.field} tone="indigo">{humanize(f.field)}: {f.value}</Badge>)}
        </div>
      </div>
      {d.kpi_chart_ids.map((id) => byId[id] && <ChartCard key={id} spec={byId[id]} />)}
      {d.sections.map((s) => (
        <section key={s.title} aria-label={s.title}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{s.title}</h3>
          <div className="grid gap-4 xl:grid-cols-2">
            {s.items.map((it, i) => byId[it.chart_id] && (
              <div key={it.chart_id} className={cn("space-y-1.5", (it.width === "full" || (s.items.length % 2 === 1 && i === s.items.length - 1)) && "xl:col-span-2")}>
                <ChartCard spec={byId[it.chart_id]} delay={0.04 * i} />
                <p className="px-1 text-[11px] text-faint"><span className="text-muted">Why this chart:</span> {it.why}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
      {d.refinements.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" aria-label="Refine this dashboard">
          <span className="flex items-center gap-1 text-[11px] text-faint"><Wand2 className="h-3.5 w-3.5" />Refine — re-runs the analysis:</span>
          {d.refinements.map((x) => (
            <button key={x.label} disabled={busy} onClick={() => ask(x.question)} title={x.question}
              className="focus-ring rounded-full border border-indigo/25 bg-indigo/[0.07] px-3 py-1 text-xs text-ink transition hover:border-indigo/50 disabled:opacity-40">{x.label}</button>
          ))}
        </div>
      )}
      <p className="text-[11px] text-faint">{d.layout_rule}</p>
    </div>
  );
}
