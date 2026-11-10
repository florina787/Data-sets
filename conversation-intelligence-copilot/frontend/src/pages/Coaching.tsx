import { HeartHandshake, UserCheck } from "lucide-react";
import { useState } from "react";
import { DataTable } from "@/components/charts/ChartRenderer";
import { Card, CardHeader, PageHeader } from "@/components/common/ui";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { AskButton, Chart, DashboardShell, useDashboard, WindowSelect } from "@/components/dashboard/Dashboard";

export default function Coaching() {
  const [win, setWin] = useState("all");
  const { data, loading, error, reload } = useDashboard("coaching", win);
  const { openConversation } = useEvidence();
  const r = data?.results.agent_coaching_review;
  return (
    <DashboardShell loading={loading} error={error} reload={reload}
      header={<PageHeader title="Agent Coaching" icon={<HeartHandshake className="h-5 w-5" />}
        subtitle="Observable communication signals — acknowledgement after frustration, and whether the closing action fits the issue."
        actions={<div className="flex gap-2"><WindowSelect value={win} onChange={setWin} /><AskButton question="Which support agents may benefit from additional coaching on empathy or customer communication, and what evidence supports that view?" /></div>} />}>
      {data && r && (
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-xl border border-warn/30 bg-warn/[0.06] p-4 text-sm" role="note">
            <UserCheck className="mt-0.5 h-5 w-5 shrink-0 text-warn" aria-hidden />
            <div><p className="font-medium text-ink">Decision support, not a performance assessment</p>
              <p className="mt-1 text-xs leading-relaxed text-muted">{r.uncertainty_notes.join(" ")}</p></div>
          </div>
          <Chart d={data} id="_coach_kpis" />
          <Chart d={data} id="coaching_heatmap" />
          <Card>
            <CardHeader title="Conversation review queue" subtitle={r.method_notes[0]} />
            <div className="p-4"><DataTable rows={r.table?.rows ?? []} onRow={(row) => openConversation(row.conversation_id)} /></div>
          </Card>
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart d={data} id="empathy_distribution" />
            <Chart d={data} id="sample_size" />
            <Chart d={data} id="coaching_by_topic" />
            <Chart d={data} id="resolution_misfit" />
          </div>
          <Card>
            <CardHeader title={`Agents (${r.series.agents.rows[0]?.note ?? "none eligible"})`} subtitle="Pooled across each agent's conversations, with 95% CI on the empathy response rate." />
            <div className="p-4"><DataTable rows={r.series.agents.rows} /></div>
          </Card>
        </div>
      )}
    </DashboardShell>
  );
}
