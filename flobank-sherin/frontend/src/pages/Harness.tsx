import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Play } from "lucide-react";
import { AgentGraph } from "../components/AgentGraph";
import { RunInline } from "../components/RunInline";
import { Badge, Button, Card, ChartCard, ErrorBox, Note, PageHeader, StatusBadge, Table } from "../components/ui";
import { api, useApi } from "../lib/api";
import { periodParams, useApp } from "../lib/store";
import { compact, money } from "../lib/format";

export default function Harness() {
  const s = useApp();
  const [sp, setSp] = useSearchParams();
  const agents = useApi<any>("/harness/agents", periodParams(s), 3000);
  const runs = useApi<any[]>("/harness/runs", undefined, 3000);
  const runId = sp.get("run") ?? runs.data?.[0]?.id;
  const run = useApi<any>(runId ? `/harness/runs/${runId}` : null, undefined, 1500);
  const [req, setReq] = useState("Evaluate trade TP-1001 and check the portfolio risk");
  const [file, setFile] = useState<{ name: string; content: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const start = async () => {
    setErr(null);
    try { const r = await api<any>("/harness/runs", { method: "POST", body: { request: req, attachments: file ? [file] : [] } }); setSp({ run: r.run_id }); runs.reload(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <div>
      <PageHeader title="Agent Harness" subtitle="LangGraph orchestration of 15 agents: planning, routing, tool permissions, checkpointing, retries, verification, human approval and cost accounting." />
      <div className="grid gap-4 2xl:grid-cols-[1fr_420px]">
        <ChartCard title="Live agent execution graph" subtitle={run.data ? `Run ${run.data.id}: ${run.data.request}` : "Start a run to watch the agents work"} badges={run.data && <StatusBadge s={run.data.status} />}>
          <AgentGraph agents={agents.data?.agents ?? []} run={run.data} cur={s.currency} height={600} />
        </ChartCard>
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-2 font-display text-lg font-semibold text-flo-900">Start an agent run</h2>
            <textarea aria-label="Run request" value={req} onChange={(e) => setReq(e.target.value)} rows={3} className="w-full rounded-xl border border-line p-2 text-sm" />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label className="cursor-pointer rounded-full border border-line px-3 py-1 text-xs font-semibold">Attach file
                <input type="file" className="hidden" accept=".py,.yml,.yaml,.log,.txt,.json,.bicep,.tf" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setFile({ name: f.name, content: await f.text() }); }} /></label>
              {file && <Badge tone="green">{file.name}</Badge>}
              <Button onClick={start}><Play className="h-4 w-4" />Run</Button>
            </div>
            <ErrorBox error={err} />
            {runId && <RunInline runId={runId} />}
          </Card>
          <Card className="p-4">
            <h2 className="mb-2 font-display text-lg font-semibold text-flo-900">Recent runs</h2>
            <ul className="space-y-1 text-sm">{(runs.data ?? []).slice(0, 12).map((r) => (
              <li key={r.id}><button type="button" onClick={() => setSp({ run: r.id })} className={`flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1 text-left ${r.id === runId ? "bg-flo-100" : "hover:bg-flo-50"}`}>
                <span className="min-w-0 truncate"><code className="text-xs">{r.id}</code> {r.request}</span><StatusBadge s={r.status} /></button></li>))}</ul>
          </Card>
        </div>
      </div>
      {run.data && (
        <ChartCard title="Execution trace" subtitle="Every node, tool call, retry, verification and approval event (persisted and checkpointed)" className="mt-4">
          <ol className="space-y-1 text-xs">{run.data.trace.map((t: any, i: number) => <li key={i} className="flex gap-2"><code className="text-muted">{t.at.slice(11, 23)}</code><Badge tone="slate">{t.node}</Badge><span>{t.message}</span>{t.status && <StatusBadge s={t.status} />}</li>)}</ol>
        </ChartCard>
      )}
      <ChartCard title="Agents" subtitle={`Resource and cost accounting for ${agents.data?.period?.start ?? ""} → ${agents.data?.period?.end ?? ""}`} className="mt-4">
        <Table dense columns={[{ key: "label", label: "Agent" }, { key: "status", label: "Status", render: (r) => <StatusBadge s={r.status} /> }, { key: "current_task", label: "Current / last task" },
          { key: "time_hours", label: "Time (h)", align: "right" }, { key: "tokens", label: "Tokens", align: "right", render: (r) => compact(r.tokens) }, { key: "c", label: "Compute cost", align: "right", render: (r) => money(r.compute_cost, s.currency) },
          { key: "q", label: "Quality", align: "right", render: (r) => (r.quality_pass_rate !== null && r.quality_pass_rate !== undefined ? `${r.quality_pass_rate}%` : "—") }, { key: "verified_tasks", label: "Verified", align: "right" },
          { key: "e", label: "Economic contribution", align: "right", render: (r) => money(r.economic_contribution, s.currency) }]} rows={agents.data?.agents ?? []} />
        <Note>Tool permissions are enforced per agent; any call outside an agent's allow-list is denied and audited. State-changing actions pause the graph until a human decides.</Note>
      </ChartCard>
    </div>
  );
}
