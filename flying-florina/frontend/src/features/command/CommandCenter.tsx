import { motion } from "framer-motion";
import { LayoutDashboard, MousePointerClick } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";

type Overview = {
  filters: { options: Record<string, string[]> };
  kpis: Record<string, number | null> & { simulated_downtime_exposure_usd: { low: number; high: number; label: string } };
  status: Record<string, number>;
  availability_trend: { month: string; availability_pct: number; events: number; unscheduled: number; downtime_hours: number }[];
  health_distribution: { bucket: string; aircraft: number }[];
  heatmap: { x: string[]; y: string[]; cells: number[][] };
  backlog: { status: string; priority: string; count: number }[];
  parts_shortage: Record<string, unknown>[];
  risk_matrix: { aircraft: string; health_score: number; open_work_orders: number; status: string; base: string; type: string }[];
  agent_activity: { workflow: string; status: string; n: number }[];
  decisions: { pending_approvals: number; denials: number; decisions: number; top_risks: string[] };
  notes: string[];
};

const FILTERS = [["fleet", "Fleet"], ["base", "Base"], ["ac_type", "Aircraft type"], ["severity", "Severity"]] as const;

export function CommandCenter() {
  const navigate = useNavigate();
  const [f, setF] = useState<Record<string, string>>({});
  const qs = useMemo(() => new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString(), [f]);
  const q = useApi<Overview>(["command", qs], `/api/command/overview${qs ? `?${qs}` : ""}`);
  const [drill, setDrill] = useState<string | null>(null);
  const d = q.data;
  const k = d?.kpis;
  const backlogStatuses = useMemo(() => [...new Set((d?.backlog ?? []).map((b) => b.status))], [d]);
  const agentWfs = useMemo(() => [...new Set((d?.agent_activity ?? []).map((a) => a.workflow))], [d]);

  return (
    <div className="space-y-5">
      <PageHeader title="Executive Command Center" icon={<LayoutDashboard className="h-5 w-5" />}
        subtitle="Aerospace & defense leadership view. Every KPI is computed from the synthetic fleet database; simulations are labelled."
        actions={<div className="flex flex-wrap gap-2" data-testid="command-filters">
          {FILTERS.map(([key, label]) => (
            <select key={key} className="input !py-1 text-xs" aria-label={`Filter by ${label}`} value={f[key] ?? ""} onChange={(e) => setF({ ...f, [key]: e.target.value })}>
              <option value="">{key === "severity" ? "All severities" : `All ${label.toLowerCase()}s`}</option>
              {(d?.filters.options[key] ?? []).map((o) => <option key={o}>{o}</option>)}
            </select>
          ))}
        </div>} />
      {q.isLoading && <Loading label="Computing fleet KPIs" />}
      {q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : null}
      {d && k && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7" data-testid="command-kpis">
            {[
              ["Total aircraft", k.total_aircraft, undefined, "/fleet"],
              ["Fleet readiness", `${k.readiness_pct}%`, "teal", "/fleet"],
              ["Requiring maintenance", k.requiring_maintenance, "amber", "/maintenance"],
              ["AOG cases", k.aog, "red", "/aog"],
              ["Engineering alerts", k.engineering_alerts, "amber", "/predictive"],
              ["Open work orders", k.open_work_orders, undefined, "/maintenance"],
              ["Critical parts at risk", k.critical_parts_at_risk, "amber", "/parts"],
              ["Mean turnaround (days)", k.mean_turnaround_days, undefined, "/maintenance"],
              ["Technician capacity", k.technicians, undefined, "/aog"],
              ["Active agent workflows", k.active_workflows, undefined, "/agents"],
              ["Pending approvals", k.pending_approvals, "amber", "/trust?tab=approvals"],
              ["Policy denials", k.policy_denials, "red", "/trust?tab=trace"],
            ].map(([label, value, tone, to], i) => (
              <motion.button key={label as string} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                onClick={() => navigate(to as string)} className="text-left" title={`Open ${to}`}>
                <Kpi label={label as string} value={value as string} tone={tone as string | undefined} />
              </motion.button>
            ))}
            <div className="col-span-2 md:col-span-2">
              <Kpi label="Simulated downtime exposure (AC-204)" value={`$${k.simulated_downtime_exposure_usd.low.toLocaleString()} – $${k.simulated_downtime_exposure_usd.high.toLocaleString()}`}
                tone="amber" hint={k.simulated_downtime_exposure_usd.label} />
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Fleet availability trend" subtitle="Derived: 1 − downtime / (aircraft × 24 h × days)" className="xl:col-span-2">
              <Chart title="Fleet availability trend" spec={{ kind: "line", x: d.availability_trend.map((t) => t.month), series: [{ name: "Availability %", data: d.availability_trend.map((t) => t.availability_pct) }], yLabel: "%" }} height={260} />
            </Card>
            <Card title="Aircraft health distribution" subtitle="Demo health index buckets (heuristic, not airworthiness)">
              <Chart title="Aircraft health distribution" spec={{ kind: "bar", x: d.health_distribution.map((h) => h.bucket), series: [{ name: "Aircraft", data: d.health_distribution.map((h) => h.aircraft) }] }} height={260} />
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Maintenance event timeline" subtitle="Events and unscheduled events per month">
              <Chart title="Maintenance events" spec={{ kind: "bar", x: d.availability_trend.map((t) => t.month), series: [{ name: "Events", data: d.availability_trend.map((t) => t.events) }, { name: "Unscheduled", data: d.availability_trend.map((t) => t.unscheduled) }] }} height={250} />
            </Card>
            <Card title="Component risk heatmap" subtitle="Open work orders by ATA chapter × base" actions={<MousePointerClick className="h-3.5 w-3.5 text-faint" aria-label="Interactive" />}>
              <Chart title="Component risk heatmap" spec={{ kind: "heatmap", x: d.heatmap.x, y: d.heatmap.y.map((c) => `ATA ${c}`), cells: d.heatmap.cells, series: [] }} height={250}
                onSelect={(p) => setDrill(`ATA chapter cell: ${JSON.stringify(p.data)}`)} />
            </Card>
            <Card title="Fleet by status" subtitle="Click a slice to open Fleet Readiness">
              <Chart title="Fleet by status" spec={{ kind: "pie", x: Object.keys(d.status), series: [{ name: "Aircraft", data: Object.values(d.status) }] }} height={250}
                onSelect={() => navigate("/fleet")} />
            </Card>
          </div>
          {drill && <p className="muted text-xs" role="status">Selected {drill}. Open Maintenance & MRO for the underlying work orders.</p>}

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="Maintenance backlog" subtitle="Open work orders by status and priority">
              <Chart title="Maintenance backlog" spec={{ kind: "bar", x: backlogStatuses, series: ["routine", "urgent"].map((p) => ({ name: p, data: backlogStatuses.map((s) => d.backlog.find((b) => b.status === s && b.priority === p)?.count ?? 0) })) }} height={250} />
            </Card>
            <Card title="Operational risk matrix" subtitle="Health score vs open work orders (lowest-health aircraft)">
              <Chart title="Operational risk matrix" spec={{ kind: "scatter", x: [], xLabel: "Health score", yLabel: "Open WOs", series: [{ name: "Aircraft", data: [], points: d.risk_matrix.map((r) => [r.health_score, r.open_work_orders, r.aircraft]) }] }} height={250}
                onSelect={() => navigate("/fleet")} />
            </Card>
            <Card title="Agent activity" subtitle="Workflow runs by type and outcome">
              <Chart title="Agent activity" spec={{ kind: "bar", x: agentWfs.map((w) => w.replace(/_/g, " ")), series: ["completed", "awaiting_approval", "denied", "failed"].map((s) => ({ name: s, data: agentWfs.map((w) => d.agent_activity.find((a) => a.workflow === w && a.status === s)?.n ?? 0) })) }} height={250} />
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card title="Spare-parts shortage ranking" subtitle="Critical/high parts with ≤ 2 verified units">
              <DataTable label="Parts shortage" maxHeight={260} columns={[{ key: "part_number", label: "Part" }, { key: "name", label: "Name" }, { key: "criticality", label: "Criticality" }, { key: "verified_total", label: "Verified" }, { key: "lead_time_days", label: "Lead d" }]} rows={d.parts_shortage} />
            </Card>
            <Card title="Executive decision summary" subtitle="What needs leadership attention now">
              <div className="space-y-2 text-sm">
                <div className="flex flex-wrap gap-2">
                  <Badge tone="amber">{d.decisions.pending_approvals} pending approval(s)</Badge>
                  <Badge tone="red">{d.decisions.denials} policy denial(s)</Badge>
                  <Badge tone="gray">{d.decisions.decisions} governed decisions</Badge>
                </div>
                <ul className="space-y-1">{d.decisions.top_risks.map((r) => <li key={r} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 rounded-full bg-warn" />{r}</li>)}</ul>
                <ul className="mt-2 space-y-1 text-[11px] text-faint">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
