import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LifeBuoy, Play, Save } from "lucide-react";
import { Chart } from "@/components/Chart";
import { Card, ErrorBox, Kpi, PageHeader, Skeleton } from "@/components/ui";
import { get, post } from "@/lib/api";
import { Banner, pct, usd } from "./common";

type Scenario = { id: string; label: string; defaults: Record<string, string | number> };
type Res = { backlog_p50: number[]; backlog_p10: number[]; backlog_p90: number[]; peak_backlog_hours: number; inventory_availability: Record<string, number>; cost_p50_usd: number;
  cost_p90_usd: number; recovery_weeks_after_disruption?: number | null; recovered_within_horizon?: boolean };
type Sim = { label: string; params: Record<string, unknown>; weeks: number[]; results: { baseline: Res; disruption: Res; recovery: Res }; assumptions: string[] };

export function Resilience() {
  const qc = useQueryClient();
  const sc = useQuery({ queryKey: ["res-sc"], queryFn: () => get<{ scenarios: Scenario[]; saved: { id: string; kind: string; name: string; ts: string }[] }>("/api/resilience/scenarios") });
  const [scenario, setScenario] = useState("facility_outage");
  const [params, setParams] = useState<Record<string, string | number>>({});
  const [mit, setMit] = useState({ overtime_capacity: 0.15, delay_reduction: 0.5, demand_deferral: 0.1 });
  const [name, setName] = useState("");
  const def = sc.data?.data.scenarios.find((s) => s.id === scenario);
  useEffect(() => { if (def) setParams(def.defaults); }, [def]);
  const run = useMutation({ mutationFn: (save?: string) => post<Sim>("/api/resilience/simulate", { scenario, params, mitigation: mit, save_as: save || undefined }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["res-sc"] }) });
  useEffect(() => { if (def && !run.data) run.mutate(undefined); }, [def]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = run.data?.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Operational Resilience Simulator" icon={<LifeBuoy className="h-5 w-5" />}
        subtitle="Baseline vs disruption vs recovery: backlog, inventory availability, recovery time, cost and uncertainty from deterministic capacity logic and 200 seeded Monte Carlo paths." />
      <Banner>Synthetic scenarios by default. Results depend on the stated assumptions below; they are planning aids, not predictions of real events.</Banner>
      {sc.error ? <ErrorBox error={sc.error} /> : null}
      <Card title="Scenario">
        {!sc.data ? <Skeleton className="h-24" /> : (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Scenarios">
              {sc.data.data.scenarios.map((s) => (
                <button key={s.id} role="tab" aria-selected={scenario === s.id} onClick={() => setScenario(s.id)}
                  className={`rounded-full border px-3 py-1 text-xs ${scenario === s.id ? "border-cyan/60 bg-cyan/10 text-cyan" : "border-token muted"}`}>{s.label}</button>
              ))}
            </div>
            <div className="flex flex-wrap items-end gap-3">
              {Object.entries(params).map(([k, v]) => (
                <label key={k} className="flex flex-col gap-1 text-xs"><span className="label">{k.replace(/_/g, " ")}</span>
                  <input className="input !py-1 w-36 text-sm" value={v} aria-label={k} onChange={(e) => setParams({ ...params, [k]: typeof v === "number" ? Number(e.target.value) : e.target.value })} /></label>
              ))}
              {(Object.keys(mit) as (keyof typeof mit)[]).map((k) => (
                <label key={k} className="flex flex-col gap-1 text-xs"><span className="label">{k.replace(/_/g, " ")}: {pct(mit[k])}</span>
                  <input type="range" min={0} max={0.8} step={0.05} value={mit[k]} className="timeline w-32" aria-label={k} onChange={(e) => setMit({ ...mit, [k]: Number(e.target.value) })} /></label>
              ))}
              <button className="btn btn-primary" onClick={() => run.mutate(undefined)} disabled={run.isPending}><Play className="h-4 w-4" />{run.isPending ? "Running…" : "Run"}</button>
              <input className="input !py-1 w-40 text-sm" placeholder="Save as…" value={name} onChange={(e) => setName(e.target.value)} aria-label="Scenario name" />
              <button className="btn btn-ghost" disabled={!name || run.isPending} onClick={() => { run.mutate(name); setName(""); }}><Save className="h-4 w-4" />Save</button>
            </div>
          </div>
        )}
      </Card>
      {run.error ? <ErrorBox error={run.error} /> : null}
      {r && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="res-kpis">
            <Kpi label="Peak backlog (h): base → disrupted → mitigated" value={`${r.results.baseline.peak_backlog_hours} → ${r.results.disruption.peak_backlog_hours} → ${r.results.recovery.peak_backlog_hours}`} />
            <Kpi label="Recovery after disruption ends" value={r.results.disruption.recovery_weeks_after_disruption == null ? "> horizon" : `${r.results.disruption.recovery_weeks_after_disruption} wk → ${r.results.recovery.recovery_weeks_after_disruption ?? "—"} wk`} hint="Unmitigated → mitigated" />
            <Kpi label="Inventory availability at 90 days" value={`${pct(r.results.baseline.inventory_availability["90"])} → ${pct(r.results.disruption.inventory_availability["90"])}`} />
            <Kpi label="Cost P50 (disrupted / mitigated)" value={`${usd(r.results.disruption.cost_p50_usd)} / ${usd(r.results.recovery.cost_p50_usd)}`} hint="Hours above capacity × labour rate" />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Maintenance backlog (hours, P50)" subtitle="BASELINE vs DISRUPTION vs RECOVERY">
              <Chart title="backlog" height={300} spec={{ kind: "line", x: r.weeks.map((w) => `W${w}`), series: (["baseline", "disruption", "recovery"] as const).map((k) => ({ name: k, data: r.results[k].backlog_p50 })) }} />
            </Card>
            <Card title="Forecast uncertainty (disruption run)" subtitle="P10 / P50 / P90 backlog across 200 seeded paths">
              <Chart title="unc" height={300} spec={{ kind: "line", x: r.weeks.map((w) => `W${w}`), series: [{ name: "P10", data: r.results.disruption.backlog_p10 }, { name: "P50", data: r.results.disruption.backlog_p50 }, { name: "P90", data: r.results.disruption.backlog_p90 }] }} />
            </Card>
            <Card title="Inventory availability by horizon" subtitle="Share of hub × category pairs without a stockout">
              <Chart title="avail" height={260} spec={{ kind: "bar", x: Object.keys(r.results.baseline.inventory_availability).map((d) => `+${d}d`), series: (["baseline", "disruption", "recovery"] as const).map((k) => ({ name: k, data: Object.values(r.results[k].inventory_availability) })) }} />
            </Card>
            <Card title="Assumptions">
              <ul className="list-disc space-y-1 pl-4 text-xs muted">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
              <p className="mt-2 text-xs muted">Parameters: {JSON.stringify(r.params)}</p>
            </Card>
          </div>
        </>
      )}
      {!!sc.data?.data.saved.length && (
        <Card title="Saved scenarios (SQLite)">
          <ul className="space-y-1 text-xs">{sc.data.data.saved.map((s) => <li key={s.id} className="flex justify-between border-b border-token py-1"><span>{s.name} · {s.kind}</span><span className="text-faint">{s.ts.slice(0, 16).replace("T", " ")}</span></li>)}</ul>
        </Card>
      )}
    </div>
  );
}
