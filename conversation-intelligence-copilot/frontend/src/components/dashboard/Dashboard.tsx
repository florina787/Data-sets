import { CalendarDays, MessageSquarePlus } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { ChartCard } from "@/components/charts/ChartCard";
import { Button, ErrorState, Skeleton } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { api } from "@/services/api";
import type { AnalysisResult, ChartSpec, GraphSpec, Scope } from "@/types/api";

export interface DashboardData { name: string; scope: Scope; results: Record<string, AnalysisResult>; charts: ChartSpec[]; graphs: GraphSpec[] }

export function WindowSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const tax = useAsync(() => api.get<{ months: string[] }>("/api/analytics/taxonomy"), []);
  return (
    <label className="flex items-center gap-2 rounded-xl border border-line bg-surface/70 px-3 py-1.5 text-xs text-muted">
      <CalendarDays className="h-3.5 w-3.5" aria-hidden />
      <span className="sr-only">Date window</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="focus-ring bg-transparent text-ink outline-none">
        <option value="last_month" className="bg-surface">Latest month in data</option>
        <option value="all" className="bg-surface">All dates</option>
        {tax.data?.months.map((m) => <option key={m} value={m} className="bg-surface">{m}</option>)}
      </select>
    </label>
  );
}

export function windowSpec(v: string) {
  return v === "last_month" ? { type: "last_month" } : v === "all" ? { type: "all" } : { type: "month", month: v };
}

export function useDashboard(name: string, win: string) {
  const { datasetMode } = useApp();
  return useAsync(() => api.post<DashboardData>(`/api/dashboards/${name}`, { window: windowSpec(win), dataset_mode: datasetMode }), [name, win, datasetMode]);
}

export function chartById(d: DashboardData | null, id: string): ChartSpec | undefined {
  return d?.charts.find((c) => c.chart_id === id || c.chart_id.endsWith(id));
}

export function DashboardShell({ header, loading, error, reload, children }: { header: ReactNode; loading: boolean; error: Error | null; reload: () => void; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-[1400px]">
      {header}
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-6">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>
          <div className="grid gap-4 xl:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72" />)}</div>
        </div>
      ) : children}
    </div>
  );
}

export function Chart({ d, id, className, height }: { d: DashboardData | null; id: string; className?: string; height?: number }) {
  const spec = chartById(d, id);
  return spec ? <ChartCard spec={spec} className={className} height={height} /> : null;
}

export function AskButton({ question }: { question: string }) {
  const { ask } = useApp();
  const nav = useNavigate();
  return (
    <Button size="sm" variant="outline" onClick={() => { nav("/"); ask(question); }}>
      <MessageSquarePlus className="h-3.5 w-3.5" />Ask the copilot
    </Button>
  );
}
