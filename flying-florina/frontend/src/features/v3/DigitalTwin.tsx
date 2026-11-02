import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Cpu } from "lucide-react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, PageHeader, Skeleton } from "@/components/ui";
import { get } from "@/lib/api";
import { scale } from "@/features/global/GlobeMap";
import { Banner, Gauge, Metric, num, pct } from "./common";

type Unit = { id: string; serial: string; facility: string; facility_id: string; category: string; category_id: string; status: string; age_weeks: number; last_health: number | null;
  health_slope_8w: number | null; rul_p10?: number; rul_p50?: number; rul_p90?: number; rul_combined?: number; rul_trend?: number | null; risk_30d?: number; anomaly_now?: boolean;
  engineering_revision: string; install_week: number; family?: string; unit_cost_usd?: number };
type Twin = { unit: Unit; telemetry: { week: number; health: number | null; vibration: number; temperature: number; pressure: number; operating_hours: number; anomaly: number }[];
  events: { id: string; week: number; date: string; kind: string; description: string; work_order: string; doc_ref: string | null }[];
  position_history: { id: string; install_week: number; removal_week: number | null; life_weeks: number; status: string }[]; flag_reasons: string[];
  data_quality: { weeks: number; missing_health_readings: number }; survival_model: { k: number; eta_weeks: number; failures: number; category: string };
  rul_uncertainty: { weeks_ahead: number; p10: number; p50: number; p90: number }[]; predicted_demand_90d: number[]; documents_to_review: string[]; assumptions: string[] };

export function DigitalTwin() {
  const [params] = useSearchParams();
  const [facility, setFacility] = useState(params.get("facility") ?? "");
  const [sel, setSel] = useState<string | null>(params.get("unit"));
  const units = useQuery({ queryKey: ["twin-units", facility], queryFn: () => get<Unit[]>(`/api/twin/units${facility ? `?facility=${facility}` : ""}`) });
  const list = units.data?.data ?? [];
  const id = sel ?? list[0]?.id;
  const twin = useQuery({ queryKey: ["twin", id], queryFn: () => get<Twin>(`/api/twin/${id}`), enabled: !!id });
  const t = twin.data?.data;
  if (units.error) return <ErrorBox error={units.error} />;
  const tel = (t?.telemetry ?? []).slice(-52);
  return (
    <div className="space-y-4">
      <PageHeader title="Aerospace Digital Twin" icon={<Cpu className="h-5 w-5" />}
        subtitle="Component-level maintenance twin: installation and maintenance history, operating history, degradation, work orders, revisions, replacements and predicted demand." />
      <Banner tone="amber">Advisory only. Synthetic units and telemetry. Nothing here authorizes release to service or overrides certified maintenance procedures.</Banner>
      <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card title="Tracked units" subtitle="Installed units, highest 30-day risk first" actions={
          <select className="input !py-1 text-xs" value={facility} onChange={(e) => { setFacility(e.target.value); setSel(null); }} aria-label="Facility">
            <option value="">All MRO hubs</option>
            {["F01", "F04", "F07", "F10", "F11", "F12"].map((f) => <option key={f} value={f}>{f}</option>)}
          </select>}>
          {units.isLoading ? <Skeleton className="h-96" /> : (
            <div className="max-h-[70vh] space-y-1 overflow-y-auto pr-1" data-testid="twin-list">
              {list.slice(0, 80).map((u) => (
                <button key={u.id} onClick={() => setSel(u.id)} className={`w-full rounded-lg border px-2.5 py-1.5 text-left text-xs transition ${u.id === id ? "border-cyan/50 bg-cyan/10" : "border-token hover:bg-white/[0.03]"}`}>
                  <div className="flex items-center justify-between"><span className="font-medium">{u.category}</span><span className="num" style={{ color: scale(u.risk_30d ?? 0) }}>{pct(u.risk_30d)}</span></div>
                  <div className="text-faint">{u.id} · {u.facility} · health {num(u.last_health)}</div>
                </button>
              ))}
            </div>
          )}
        </Card>
        {!t ? <Skeleton className="h-[70vh]" /> : (
          <div className="space-y-4" data-testid="twin-detail">
            <Card title={`${t.unit.category} · ${t.unit.id}`} subtitle={`${t.unit.facility} · serial ${t.unit.serial} · revision ${t.unit.engineering_revision} · installed week ${t.unit.install_week}`}>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Gauge value={t.unit.last_health} label="Health index" sub="removal at 0.20" />
                <Gauge value={t.unit.risk_30d ?? null} label="30-day removal risk" bad sub="RandomForest" />
                <Gauge value={t.unit.rul_combined ?? null} max={52} label="RUL (weeks)" bad={false} sub={`P10–P90 ${num(t.unit.rul_p10, 0)}–${num(t.unit.rul_p90, 0)}`} />
                <div className="grid gap-2">
                  <Metric k="Age" v={`${t.unit.age_weeks} wk`} /><Metric k="Slope (8 wk)" v={num(t.unit.health_slope_8w, 4)} />
                  <Metric k="Anomaly now" v={t.unit.anomaly_now ? <Badge tone="red">flagged</Badge> : "no"} />
                </div>
              </div>
            </Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Why was this component flagged?">
                {t.flag_reasons.length ? <ul className="list-disc space-y-1 pl-4 text-sm">{t.flag_reasons.map((r) => <li key={r}>{r}</li>)}</ul> : <p className="text-sm muted">No flag rule fired for this unit.</p>}
                <p className="mt-2 text-xs muted">Data quality: {t.data_quality.missing_health_readings} of {t.data_quality.weeks} weekly health readings missing.</p>
              </Card>
              <Card title="How uncertainty changes over time" subtitle={`Weibull survival for ${t.survival_model.category}: k=${t.survival_model.k}, η=${t.survival_model.eta_weeks} weeks (${t.survival_model.failures} failures)`}>
                {t.rul_uncertainty.length ? <Chart title="rul uncertainty" height={220} spec={{ kind: "line", x: t.rul_uncertainty.map((u) => `+${u.weeks_ahead}w`), series: [
                  { name: "RUL P10", data: t.rul_uncertainty.map((u) => u.p10) }, { name: "RUL P50", data: t.rul_uncertainty.map((u) => u.p50) }, { name: "RUL P90", data: t.rul_uncertainty.map((u) => u.p90) }] }} /> : <p className="text-sm muted">Removed unit.</p>}
              </Card>
            </div>
            <Card title="Degradation and operating history (last 52 weeks)">
              <Chart title="telemetry" height={300} spec={{ kind: "line", x: tel.map((w) => String(w.week)), series: [
                { name: "health index", data: tel.map((w) => w.health) as number[] }, { name: "vibration", data: tel.map((w) => w.vibration) },
                { name: "temperature", data: tel.map((w) => w.temperature) }, { name: "pressure", data: tel.map((w) => w.pressure) }], markLine: { y: 0.2, label: "removal threshold" } }} />
            </Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="Maintenance records and work orders">
                <DataTable rows={t.events as unknown as Record<string, unknown>[]} columns={[{ key: "date", label: "Date" }, { key: "kind", label: "Kind" }, { key: "description", label: "Description" },
                  { key: "work_order", label: "Work order" }, { key: "doc_ref", label: "Document" }]} />
              </Card>
              <Card title="Replacement history at this position">
                <DataTable rows={t.position_history as unknown as Record<string, unknown>[]} columns={[{ key: "id", label: "Unit" }, { key: "install_week", label: "Installed (wk)" },
                  { key: "removal_week", label: "Removed (wk)" }, { key: "life_weeks", label: "Life (wk)" }, { key: "status", label: "Status" }]} />
                <p className="mt-2 text-xs muted">Predicted removals of this category at this hub, next 90 days: P10 {t.predicted_demand_90d[0]} · P50 {t.predicted_demand_90d[1]} · P90 {t.predicted_demand_90d[2]}</p>
              </Card>
            </div>
            <Card title="What an engineer should review">
              <div className="flex flex-wrap gap-2">{t.documents_to_review.map((d) => <Badge key={d} tone="teal">{d}</Badge>)}</div>
              <ul className="mt-3 list-disc space-y-1 pl-4 text-xs muted">{t.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
