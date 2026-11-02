import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Network, Play } from "lucide-react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { DependencyGraph } from "@/components/DependencyGraph";
import { Badge, Card, ErrorBox, PageHeader, Skeleton } from "@/components/ui";
import { get, post } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { Banner, Metric, num, pct, Select } from "./common";

type Sup = { id: string; name: string; city: string; region: string; deliveries: number; lead_time_quantiles: number[]; on_time_rate: number; delivery_variability_cv: number;
  on_time_first_year: number; on_time_second_year: number; late_probability_open_orders: number; categories: string[] };
type Overview = { suppliers: Sup[]; concentration: { category: string; suppliers: number; hhi: number; single_source: boolean }[];
  repair_turnaround: { center: string; category_id: string; p10: number; p50: number; p90: number }[]; graph: { nodes: { id: string; label: string; kind: string }[]; edges: { source: string; target: string; share: number }[] };
  lead_time_model: { method: string; mae: number; coverage_80: number; baseline_supplier_median: { mae: number } }; late_delivery_eval: { precision: number; recall: number; f1: number; brier: number } };
type Impact = { supplier: { name: string }; delay_days: number; horizon_days: number; affected_categories: { category: string; share: number }[];
  scenarios: { scenario: string; deferred_maintenance_hours: number; cost_usd: number }[]; rows: Record<string, unknown>[]; assumptions: string[] };

export function SupplyChain() {
  const [params] = useSearchParams();
  const ov = useQuery({ queryKey: ["supply-ov"], queryFn: () => get<Overview>("/api/supply/overview") });
  const [supplier, setSupplier] = useState(params.get("supplier") ?? "S1");
  const [delay, setDelay] = useState(14);
  const [horizon, setHorizon] = useState(60);
  const run = useMutation({ mutationFn: () => post<Impact>("/api/supply/delay-impact", { supplier_id: supplier, delay_days: delay, horizon_days: horizon }) });
  if (ov.error) return <ErrorBox error={ov.error} />;
  const o = ov.data?.data;
  const r = run.data?.data;
  const nodes: GraphNode[] = (o?.graph.nodes ?? []).map((n) => ({ id: n.id, label: n.label, type: n.kind === "supplier" ? "system" : "entity" }));
  const edges: GraphEdge[] = (o?.graph.edges ?? []).map((e, i) => ({ id: `e${i}`, source: e.source, target: e.target, label: pct(e.share), kind: "supplies" }));
  return (
    <div className="space-y-4">
      <PageHeader title="Global Supply Chain Intelligence" icon={<Network className="h-5 w-5" />}
        subtitle="Supplier performance, lead-time distributions, concentration, repair capacity, dependencies and business-continuity simulation." />
      <Banner>Fictional suppliers and SYNTHETIC delivery history. Lead-time risk comes from a quantile model scored on held-out orders.</Banner>
      <Card title="What happens to our maintenance schedule if a supplier is late?" subtitle="Simulates inventory depletion and deferred work with a weekly reorder policy; compares planning options">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Supplier" value={supplier} onChange={setSupplier} options={(o?.suppliers ?? []).map((s) => ({ value: s.id, label: `${s.name} (${s.region})` }))} />
          <label className="flex flex-col gap-1 text-xs"><span className="label">Delay (days): {delay}</span>
            <input type="range" min={0} max={60} value={delay} onChange={(e) => setDelay(Number(e.target.value))} aria-label="Delay days" className="timeline w-48" /></label>
          <Select label="Horizon" value={String(horizon)} onChange={(v) => setHorizon(Number(v))} options={[30, 60, 90].map((h) => ({ value: String(h), label: `+${h} days` }))} />
          <button className="btn btn-primary" onClick={() => run.mutate()} disabled={run.isPending} data-testid="run-delay"><Play className="h-4 w-4" />{run.isPending ? "Simulating…" : "Simulate"}</button>
          <Link to="/global?layer=supply" className="btn btn-ghost text-xs">Supply chain map layer</Link>
        </div>
        {run.error ? <ErrorBox error={run.error} /> : null}
        {r && (
          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]" data-testid="delay-result">
            <div>
              <p className="text-sm">A <b>{r.delay_days}-day</b> delay at <b>{r.supplier.name}</b> affects {r.affected_categories.map((c) => `${c.category} (${pct(c.share)} of supply)`).join(", ")}.</p>
              <Chart title="options" height={240} spec={{ kind: "bar", x: r.scenarios.map((s) => s.scenario), series: [{ name: "deferred maintenance hours", data: r.scenarios.map((s) => s.deferred_maintenance_hours) }] }} />
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[11px] muted">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </div>
            <DataTable rows={r.rows.slice(0, 12)} columns={[{ key: "facility", label: "Facility" }, { key: "category", label: "Category" }, { key: "stockout_baseline", label: "Stockout baseline" },
              { key: "stockout_delay", label: "With delay" }, { key: "stockout_alternate", label: "Alternate supplier" }, { key: "stockout_transfer", label: "Stock transfer" }, { key: "deferred_hours_delay", label: "Extra deferred h" }]} />
          </div>
        )}
      </Card>
      {!o ? <Skeleton className="h-96" /> : (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Supplier performance trends" subtitle="On-time rate, first vs second year of history">
              <Chart title="ontime" height={280} spec={{ kind: "bar", x: o.suppliers.map((s) => s.name), series: [{ name: "year 1", data: o.suppliers.map((s) => s.on_time_first_year) },
                { name: "year 2", data: o.suppliers.map((s) => s.on_time_second_year) }] }} />
            </Card>
            <Card title="Lead-time distributions (days)" subtitle="P10 / P25 / P50 / P75 / P90 of recorded deliveries">
              <Chart title="leadtime" height={280} spec={{ kind: "bar", x: o.suppliers.map((s) => s.name), series: ["P10", "P25", "P50", "P75", "P90"].map((q, i) => ({ name: q, data: o.suppliers.map((s) => s.lead_time_quantiles[i]) })) }} />
            </Card>
          </div>
          <Card title="Suppliers">
            <DataTable rows={o.suppliers as unknown as Record<string, unknown>[]} columns={[{ key: "name", label: "Supplier" }, { key: "region", label: "Region" }, { key: "deliveries", label: "Deliveries" },
              { key: "on_time_rate", label: "On-time rate" }, { key: "delivery_variability_cv", label: "Variability (CV)" }, { key: "late_probability_open_orders", label: "Late prob. (open orders)" }]} />
          </Card>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Supplier concentration" subtitle="Herfindahl index of supply shares per category (1 = single source)">
              <DataTable rows={o.concentration.map((c) => ({ ...c, single_source: c.single_source ? "yes" : "no" }))} columns={[{ key: "category", label: "Category" }, { key: "suppliers", label: "Suppliers" },
                { key: "hhi", label: "HHI" }, { key: "single_source", label: "Single source" }]} />
            </Card>
            <Card title="Lead-time model (held-out)" subtitle={o.lead_time_model.method}>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Metric k="MAE (days)" v={num(o.lead_time_model.mae, 1)} /><Metric k="Supplier-median MAE" v={num(o.lead_time_model.baseline_supplier_median.mae, 1)} />
                <Metric k="80% coverage" v={pct(o.lead_time_model.coverage_80)} /><Metric k="Late-delivery F1" v={num(o.late_delivery_eval.f1)} />
                <Metric k="Late-delivery Brier" v={num(o.late_delivery_eval.brier, 3)} />
              </div>
              <p className="mt-3 label">Repair capacity (turnaround days, P50)</p>
              <Chart title="tat" height={200} spec={{ kind: "bar", x: o.repair_turnaround.filter((r) => r.center.startsWith("Atlantic")).map((r) => r.category_id.replace(/_/g, " ")),
                series: [{ name: "Shannon P50", data: o.repair_turnaround.filter((r) => r.center.startsWith("Atlantic")).map((r) => r.p50) },
                  { name: "Seattle P50", data: o.repair_turnaround.filter((r) => r.center.startsWith("Cascade")).map((r) => r.p50) }] }} />
            </Card>
          </div>
          <Card title="Supply-chain dependency graph" subtitle="Supplier → component category, labelled with supply share"><DependencyGraph nodes={nodes} edges={edges} height={460} /></Card>
          <p className="text-xs text-faint"><Badge tone="gold">synthetic</Badge> No real supplier relationships are represented.</p>
        </>
      )}
    </div>
  );
}
