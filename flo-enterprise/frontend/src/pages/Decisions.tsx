import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorState, Input, Label, PageHeader, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { axis, baseOption, tokens } from "@/lib/chartTheme";

const ch = createColumnHelper<any>();
const OUT = ["delivered", "partially_delivered", "not_delivered", "pending"];

export default function Decisions() {
  const { can } = useApp();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["decisions"], queryFn: () => api("/api/decisions") });
  const [form, setForm] = useState({ title: "", rationale: "", target_kpi: "", baseline_value: "", target_value: "", deadline: "", expected_impact: "", assumptions: "" });
  const add = useMutation({ mutationFn: () => api("/api/decisions", { method: "POST", json: { ...form, baseline_value: Number(form.baseline_value), target_value: Number(form.target_value),
    assumptions: form.assumptions ? form.assumptions.split(";").map((s) => s.trim()) : [] } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["decisions"] }) });
  const tk = tokens();
  const opt = useMemo(() => q.data && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => `${p.data[2]}<br/>${p.data[0]} · ${p.seriesName.replace("_", " ")}` },
    xAxis: axis({ type: "time" }), yAxis: axis({ type: "category", data: OUT.map((o) => o.replace("_", " ")) }),
    series: OUT.map((o, i) => ({ name: o, type: "scatter", symbolSize: 10, itemStyle: { color: tk.series[i], borderColor: tk.surface, borderWidth: 2 },
      data: q.data.decisions.filter((d: any) => d.outcome_status === o).map((d: any) => [d.decision_date, o.replace("_", " "), d.title]) })) }), [q.data, tk]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const s = q.data.summary;
  const d1 = q.data.decisions.find((d: any) => d.id === "D-0001");
  const cols = [ch.accessor("id", { header: "ID" }), ch.accessor("title", { header: "Decision" }), ch.accessor("owner", { header: "Owner" }), ch.accessor("decision_date", { header: "Date" }),
    ch.accessor("target_kpi", { header: "Target KPI" }), ch.accessor("baseline_value", { header: "Baseline" }), ch.accessor("target_value", { header: "Target" }),
    ch.accessor("observed_value", { header: "Observed", cell: (c) => c.getValue() ?? "—" }), ch.accessor("deadline", { header: "Deadline" }),
    ch.accessor("outcome_status", { header: "Outcome", cell: (c) => <Badge tone={c.getValue() === "delivered" ? "good" : c.getValue() === "not_delivered" ? "crit" : c.getValue() === "pending" ? "neutral" : "warn"}>{c.getValue().replace("_", " ")}</Badge> }),
    ch.accessor("open_follow_ups", { header: "Open follow-ups", cell: (c) => c.getValue().length })];
  return (
    <div className="space-y-4">
      <PageHeader title="Executive Decision Memory" subtitle={s.caveat} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {OUT.map((o) => <Stat key={o} label={o.replace("_", " ")} value={s.counts_by_outcome[o] ?? 0} />)}
        <Stat label="Overdue commitments" value={s.unresolved_commitment_count} tone="warn" />
      </div>
      {d1?.measurement && <Card className="p-4 text-sm"><b>D-0001 measured from data:</b> repriced funds' average monthly net flows moved from CAD {d1.measurement.avg_monthly_net_flows_before_cad_m}m to CAD {d1.measurement.avg_monthly_net_flows_after_cad_m}m;
        the non-repriced comparison group moved from CAD {d1.measurement.comparison_group_before_cad_m}m to CAD {d1.measurement.comparison_group_after_cad_m}m. <span className="text-muted">{d1.measurement.method}</span></Card>}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard id="decision_timeline" title="Decision timeline by outcome" option={opt} rows={q.data.decisions.map((d: any) => ({ id: d.id, date: d.decision_date, title: d.title, outcome: d.outcome_status }))} />
        <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Initiatives behind schedule & unresolved commitments</h3>
          <ul className="mb-3 space-y-1 text-xs">{s.behind_schedule_initiatives.map((i: any) => <li key={i.id}><Badge tone="warn">behind</Badge> {i.name} — {i.progress_pct}% vs planned {i.planned_progress_pct}%</li>)}</ul>
          <ul className="max-h-48 space-y-1 overflow-auto scroll-thin text-xs">{s.unresolved_commitments.map((u: any, i: number) => <li key={i}>{u.decision_id}: {u.action} · {u.owner} · due {u.due}</li>)}</ul></Card>
      </div>
      <DataTable label="Decisions" data={q.data.decisions} columns={cols} />
      {can("decisions:write") && (
        <Card className="space-y-2 p-4"><h3 className="text-sm font-semibold">Record a decision</h3>
          <div className="grid gap-2 md:grid-cols-4">
            {(["title", "target_kpi", "baseline_value", "target_value", "deadline", "expected_impact", "rationale", "assumptions"] as const).map((k) => (
              <div key={k}><Label>{k.replace("_", " ")}{k === "assumptions" ? " (; separated)" : ""}</Label><Input type={k === "deadline" ? "date" : "text"} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>))}
          </div>
          <Button variant="primary" onClick={() => add.mutate()} disabled={add.isPending}>Record decision</Button>
          {add.error && <ErrorState error={add.error} />}{add.data && <span className="ml-2 text-xs text-pos">Recorded {add.data.id}</span>}
        </Card>
      )}
    </div>
  );
}
