import { Activity, Play } from "lucide-react";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { Workspace } from "@/components/Workspace";
import { AgentTimeline } from "@/components/AgentTimeline";
import { useWorkflow } from "@/lib/hooks";

const Q = "Compare aircraft maintenance recovery options using verified inventory availability.";
const Q2 = "Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options.";

export function AogPage() {
  const wf = useWorkflow();
  return (
    <div className="space-y-4">
      <PageHeader title="AOG Recovery" subtitle="Seeded incident INC-001: AC-204 vibration anomaly. Plans are drafts; return to service is always a human decision." icon={<Activity className="h-5 w-5" />}
        actions={<>
          <button className="btn btn-primary" onClick={() => wf.run_({ query: Q })} disabled={wf.pending} data-testid="run-recovery"><Play className="h-4 w-4" /> Compare recovery options (24/48/72 h)</button>
          <button className="btn btn-ghost" onClick={() => wf.run_({ query: Q2 })} disabled={wf.pending}>Investigate + draft work order</button>
        </>} />
      {wf.pending && <Loading label="Agents are working" />}
      {wf.error ? <ErrorBox error={wf.error} /> : null}
      {!wf.run && !wf.pending && <Card title="How this works"><p className="muted text-sm">The recovery workflow runs telemetry, retrieval and history agents in parallel, then parts and planner agents, a compliance checklist, and a deterministic delay simulation. Only verified inventory and approved alternates (with a current authority document) are proposed.</p></Card>}
      {wf.run && (
        <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
          <Workspace blocks={wf.run.state.workspace} runId={wf.run.run_id} />
          <Card title="Execution log"><AgentTimeline events={wf.run.events} /></Card>
        </div>
      )}
    </div>
  );
}
