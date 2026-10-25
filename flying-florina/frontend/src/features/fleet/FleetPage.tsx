import { Plane } from "lucide-react";
import { useMemo, useState } from "react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Card, ErrorBox, Kpi, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";

type Fleet = {
  total_aircraft: number; by_status: Record<string, number>; by_type: Record<string, number>; by_base: Record<string, number>; available_pct: number; aog_count: number;
  open_work_orders: number; anomaly_aircraft: string[]; mean_health_score: number; as_of: string; demo_threshold: { vibration_index: number; label: string };
  aircraft: { id: string; type: string; fleet: string; base: string; status: string; health_score: number; vibration_7d: number; open_work_orders: number; above_threshold: boolean }[];
};
type Trends = { maintenance_by_month: { month: string; events: number; unscheduled: number }[]; vibration_band: { day: string; mean: number; mx: number }[]; incidents: Record<string, unknown>[] };
type Aircraft = { id: string; type: string; base: string; status: string; health: { health_score: number; vibration_7d: number }; telemetry: { day: string; vibration_index: number | null; egt_delta_c: number | null }[]; open_work_orders: Record<string, unknown>[]; recent_events: Record<string, unknown>[] };

export function FleetPage() {
  const fleet = useApi<Fleet>(["fleet"], "/api/fleet/overview");
  const trends = useApi<Trends>(["trends"], "/api/fleet/trends");
  const [sel, setSel] = useState("AC-204");
  const [filter, setFilter] = useState("");
  const ac = useApi<Aircraft>(["aircraft", sel], `/api/aircraft/${sel}?days=120`);
  const rows = useMemo(() => (fleet.data?.aircraft ?? []).filter((a) => !filter || JSON.stringify(a).toLowerCase().includes(filter.toLowerCase())), [fleet.data, filter]);
  if (fleet.isLoading) return <Loading />;
  if (fleet.error) return <ErrorBox error={fleet.error} onRetry={() => fleet.refetch()} />;
  const f = fleet.data!;
  return (
    <div className="space-y-4">
      <PageHeader title="Fleet & Asset Health" subtitle={`Synthetic fleet as of ${f.as_of}. Health scores are demo heuristics, not airworthiness determinations.`} icon={<Plane className="h-5 w-5" />} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-6" data-testid="fleet-kpis">
        <Kpi label="Aircraft" value={f.total_aircraft} />
        <Kpi label="In service" value={`${f.available_pct}%`} tone="teal" />
        <Kpi label="AOG" value={f.aog_count} tone="red" />
        <Kpi label="Open work orders" value={f.open_work_orders} />
        <Kpi label="Mean health" value={f.mean_health_score} />
        <Kpi label="Above demo threshold" value={f.anomaly_aircraft.length} tone="amber" hint={f.anomaly_aircraft.join(", ")} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Fleet by status"><Chart title="Fleet by status" spec={{ kind: "pie", x: Object.keys(f.by_status), series: [{ name: "Aircraft", data: Object.values(f.by_status) }] }} height={240} /></Card>
        <Card title="Fleet by type"><Chart title="Fleet by type" spec={{ kind: "bar", x: Object.keys(f.by_type), series: [{ name: "Aircraft", data: Object.values(f.by_type) }] }} height={240} /></Card>
        <Card title="Maintenance events per month" subtitle="Source: maintenance_events (synthetic)">
          {trends.data && <Chart title="Maintenance frequency" spec={{ kind: "bar", x: trends.data.maintenance_by_month.map((m) => m.month), series: [{ name: "Events", data: trends.data.maintenance_by_month.map((m) => m.events) }, { name: "Unscheduled", data: trends.data.maintenance_by_month.map((m) => m.unscheduled) }] }} height={240} />}
        </Card>
      </div>
      <Card title={`Aircraft drilldown: ${sel}`} subtitle={f.demo_threshold.label} actions={
        <select className="input !py-1 text-xs" value={sel} onChange={(e) => setSel(e.target.value)} aria-label="Select aircraft">
          {f.aircraft.map((a) => <option key={a.id}>{a.id}</option>)}
        </select>}>
        {ac.isLoading && <Loading />}
        {ac.error ? <ErrorBox error={ac.error} /> : null}
        {ac.data && (
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <Chart title={`${sel} telemetry`} spec={{ kind: "line", x: ac.data.telemetry.map((t) => t.day), series: [{ name: "Vibration index", data: ac.data.telemetry.map((t) => t.vibration_index) }], markLine: { y: f.demo_threshold.vibration_index, label: "Demo threshold" } }} />
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <Kpi label="Health" value={ac.data.health?.health_score ?? "-"} />
                <Kpi label="Vibration 7d" value={ac.data.health?.vibration_7d ?? "-"} />
              </div>
              <div><b>Type</b> {ac.data.type} · <b>Base</b> {ac.data.base} · <b>Status</b> {ac.data.status}</div>
              <DataTable columns={[{ key: "id", label: "Open WO" }, { key: "status", label: "Status" }, { key: "description", label: "Description" }]} rows={ac.data.open_work_orders} maxHeight={180} />
            </div>
          </div>
        )}
      </Card>
      <Card title="All aircraft" actions={<input className="input !py-1 text-xs" placeholder="Filter..." value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter aircraft" />}>
        <DataTable label="Aircraft" columns={[
          { key: "id", label: "Aircraft", render: (r) => <button className="font-semibold text-purple underline dark:text-lavender" onClick={() => setSel(String(r.id))}>{String(r.id)}</button> },
          { key: "type", label: "Type" }, { key: "fleet", label: "Fleet" }, { key: "base", label: "Base" }, { key: "status", label: "Status" },
          { key: "health_score", label: "Health" }, { key: "vibration_7d", label: "Vibration 7d" }, { key: "open_work_orders", label: "Open WOs" }]} rows={rows} />
      </Card>
    </div>
  );
}
