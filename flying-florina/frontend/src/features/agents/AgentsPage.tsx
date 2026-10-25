import { useQueryClient } from "@tanstack/react-query";
import { Bot, Play, RotateCcw, Ban } from "lucide-react";
import { useState } from "react";
import { AgentGraph } from "@/components/AgentGraph";
import { AgentTimeline } from "@/components/AgentTimeline";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Loading, PageHeader, statusTone } from "@/components/ui";
import { post } from "@/lib/api";
import { datetime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { RunView } from "@/lib/types";
import { useRunPolling } from "@/features/copilot/MissionControl";

type AgentRow = { name: string; description: string; tools: { name: string; version: string }[]; steps_run: number; failures: number; avg_ms: number };
type RunRow = { id: string; user_id: string; persona: string; query: string; workflow: string; status: string; created: string; replay_of: string | null };

const AC204 = "Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan.";

export function AgentsPage() {
  const qc = useQueryClient();
  const catalog = useApi<AgentRow[]>(["agents"], "/api/agents/catalog");
  const runs = useApi<RunRow[]>(["runs"], "/api/workflows?limit=50");
  const [sel, setSel] = useState<string | null>(null);
  const [inject, setInject] = useState("parts");
  const [permanent, setPermanent] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const run = useRunPolling(sel);

  const start = async (options: Record<string, unknown>) => {
    setErr(null);
    try {
      const r = await post<RunView>("/api/chat/query", { query: AC204, wait: false, options });
      setSel(r.data.run_id);
      qc.invalidateQueries({ queryKey: ["runs"] });
    } catch (e) {
      setErr(e);
    }
  };
  const v = run.data?.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Agent Mission Control" subtitle="Typed agents with bounded tool access. The graph and timeline reflect persisted execution events only." icon={<Bot className="h-5 w-5" />} />
      <Card title="Run controls (demo)">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <button className="btn btn-primary" onClick={() => start({ step_delay_ms: 500 })} data-testid="run-paced"><Play className="h-4 w-4" /> Run AC-204 graph (paced 500 ms/step)</button>
          <label className="flex items-center gap-1">Inject failure in
            <select className="input !py-0.5 text-xs" value={inject} onChange={(e) => setInject(e.target.value)} aria-label="Failure step">
              {["telemetry", "retrieval", "history", "parts", "scheduling", "compliance"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={permanent} onChange={(e) => setPermanent(e.target.checked)} /> permanent (downstream skipped)</label>
          <button className="btn btn-ghost" onClick={() => start({ inject_failure: inject, inject_failure_permanent: permanent, step_delay_ms: 250 })} data-testid="run-failure">Run with failure</button>
          <button className="btn btn-ghost" onClick={() => start({ inject_tool_timeout: "hangar.find_slots" })}>Run with tool timeout</button>
        </div>
        {err ? <div className="mt-2"><ErrorBox error={err} /></div> : null}
      </Card>
      {sel && (
        <Card title={v ? <span className="flex items-center gap-2">Run {v.run_id} <Badge tone={statusTone(v.status)}>{v.status}</Badge></span> : "Loading run"}
          actions={v && <>
            <button className="btn btn-ghost !py-1 text-xs" disabled={v.finished} onClick={() => post(`/api/workflows/${v.run_id}/cancel`).then(() => run.refetch())}><Ban className="h-3.5 w-3.5" /> Cancel</button>
            <button className="btn btn-ghost !py-1 text-xs" disabled={!v.finished} onClick={async () => { const r = await post<RunView>(`/api/workflows/${v.run_id}/replay`); setSel(r.data.run_id); qc.invalidateQueries({ queryKey: ["runs"] }); }}><RotateCcw className="h-3.5 w-3.5" /> Replay</button>
          </>}>
          {run.isLoading && <Loading />}
          {v && (
            <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
              {v.graph ? <AgentGraph graph={v.graph} events={v.events} height={420} /> : <div className="muted text-xs">No graph (clarification).</div>}
              <div className="max-h-[420px] overflow-auto"><AgentTimeline events={v.events} /></div>
            </div>
          )}
          {v?.state.tool_calls?.length ? (
            <div className="mt-3"><DataTable columns={[{ key: "agent", label: "Agent" }, { key: "tool", label: "Tool" }, { key: "status", label: "Status" }]} rows={v.state.tool_calls} maxHeight={200} /></div>
          ) : null}
        </Card>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Agent catalog">
          {catalog.isLoading ? <Loading /> : catalog.error ? <ErrorBox error={catalog.error} /> : (
            <DataTable label="Agents" columns={[{ key: "name", label: "Agent" }, { key: "description", label: "Responsibility" }, { key: "tools", label: "Tools", render: (r) => (r.tools as AgentRow["tools"]).map((t) => `${t.name}@${t.version}`).join(", ") || "-" }, { key: "steps_run", label: "Steps run" }, { key: "failures", label: "Failures" }, { key: "avg_ms", label: "Avg ms" }]} rows={catalog.data!} />
          )}
        </Card>
        <Card title="Recent runs (replayable)">
          {runs.data && <DataTable label="Runs" columns={[
            { key: "id", label: "Run", render: (r) => <button className="text-purple underline dark:text-lavender" onClick={() => setSel(String(r.id))}>{String(r.id)}</button> },
            { key: "workflow", label: "Workflow" }, { key: "status", label: "Status" }, { key: "created", label: "Created", render: (r) => datetime(String(r.created)) }, { key: "query", label: "Query" }]} rows={runs.data} />}
        </Card>
      </div>
    </div>
  );
}
