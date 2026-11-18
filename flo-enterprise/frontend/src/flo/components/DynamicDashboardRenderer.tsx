import type { ChartSpec, KPI, MessageContext } from "../types";
import { FinancialChartRenderer } from "./FinancialChartRenderer";
import { FinancialKPICard } from "./FinancialKPICard";

const WIDE = new Set(["treemap", "geo", "agent_graph", "matrix", "combo", "stacked_area", "waterfall"]);

/** Lays out exactly the KPIs and charts the backend composed for this question - nothing pre-baked. */
export function DynamicDashboardRenderer({ kpis, charts, onFollowup }: { kpis: KPI[]; charts: ChartSpec[]; onFollowup: (q: string, c?: MessageContext) => void }) {
  return (
    <div className="space-y-4">
      {kpis.length > 0 && (
        <div role="group" className="grid grid-cols-2 gap-3 md:grid-cols-3 2xl:grid-cols-4" aria-label="Key metrics">
          {kpis.map((k, i) => <FinancialKPICard key={k.id} k={k} index={i} />)}
        </div>
      )}
      {charts.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-2">
          {charts.map((c, i) => (
            <div key={c.chart_id} className={WIDE.has(c.chart_type) || (charts.length % 2 === 1 && i === 0) ? "xl:col-span-2" : ""}>
              <FinancialChartRenderer spec={c} index={i} onFollowup={onFollowup} height={WIDE.has(c.chart_type) ? 320 : 270} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
