import { post, waitForJob } from "../api";
import { ActionMessage, Card, Empty, Notice, Provenance, Status, Time } from "../components/ui";
import { can, roleHint, useApp } from "../context";
import { useAction, usePoll } from "../hooks";

export default function Board() {
  const { runId, user, refreshAll } = useApp();
  const detail = usePoll<any>(runId ? `/api/runs/${runId}` : null, 2500);
  const acts = usePoll<any>(runId ? `/api/runs/${runId}/activity` : null, 2500);
  const action = useAction();
  const run = detail.data?.run;
  const flows = detail.data?.flows ?? {};
  if (!runId) return <Empty>No run selected. Submit a brief or run the guided demo.</Empty>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Delivery board</h1>
        {run && <div className="flex items-center gap-2 text-sm"><span className="font-mono">{run.id}</span><Status value={run.status} /> <span className="text-navy-600">stage: {run.stage}</span></div>}
      </div>
      {detail.error && <Notice kind="error">{detail.error}</Notice>}
      <Card title="Run controls" actions={
        <>
          <button className="btn-primary" disabled={!can(user, "run.advance") || action.busy}
            title={can(user, "run.advance") ? undefined : roleHint("run.advance")}
            onClick={() => action.run(async () => { const { job_id } = await post(`/api/runs/${runId}/continue`); await waitForJob(job_id); detail.refresh(); refreshAll(); }, "Workflow advanced until the next human gate, pause or end.")}>
            {action.busy ? "Agents working…" : "Continue"}
          </button>
          <button className="btn-ghost" disabled={!can(user, "run.control")} title={can(user, "run.control") ? "Stops after the current node; state is checkpointed" : roleHint("run.control")}
            onClick={() => action.run(async () => { await post(`/api/runs/${runId}/pause`); }, "Pause requested: the run stops after the current node.")}>
            Pause
          </button>
          <label className="flex items-center gap-1 text-sm" title={can(user, "run.control") ? "Pause after every agent step" : roleHint("run.control")}>
            <input type="checkbox" disabled={!can(user, "run.control")} checked={!!run?.step_mode}
              onChange={(e) => action.run(async () => { await post(`/api/runs/${runId}/step-mode`, { enabled: e.target.checked }); detail.refresh(); })} />
            Step mode
          </label>
        </>
      }>
        <div className="space-y-2 text-sm">
          {run?.waiting_for && <Notice kind="warn">Waiting for a human: {run.waiting_for.replaceAll("_", " ")}</Notice>}
          {run?.error && <Notice kind="error">Last step failed: {run.error}. Continue resumes from the last checkpoint.</Notice>}
          <ActionMessage message={action.message} />
          <div className="flex flex-wrap gap-3 text-xs text-navy-600">
            {Object.entries(flows).map(([name, f]: any) => (
              <span key={name}>LangGraph thread <span className="font-mono">{name}</span>: {f.done ? "complete" : f.interrupts.length ? "interrupted (human gate)" : f.next.length ? `next: ${f.next.join(", ")}` : "not started"}</span>
            ))}
          </div>
        </div>
      </Card>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {(detail.data?.board ?? []).map((s: any) => (
          <div key={s.stage} className={`rounded-xl border p-3 ${s.status === "active" || s.status === "waiting" ? "border-leaf-500 bg-white shadow" : s.status === "blocked" ? "border-brick-700 bg-brick-100" : "border-cream-300 bg-cream-50"}`}>
            <div className="flex items-start justify-between gap-2"><div className="text-sm font-semibold">{s.title}</div><Status value={s.status} /></div>
            <div className="mt-1 text-xs text-navy-600">Owner: {s.owner}</div>
            {s.depends_on.length > 0 && <div className="text-xs text-navy-600">Depends on: {s.depends_on.join(", ")}</div>}
            {s.blockers.map((b: string) => <div key={b} className="mt-1 text-xs font-semibold text-brick-700">{b}</div>)}
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Agent activity" className="lg:col-span-2">
          <p className="mb-2 text-xs text-navy-600">Concise summaries of agent actions and tool results. No model chain-of-thought is stored or shown.</p>
          {!acts.data?.activity?.length ? <Empty>No activity yet.</Empty> : (
            <ol className="max-h-[520px] space-y-1 overflow-auto">
              {[...acts.data.activity].reverse().map((a: any) => (
                <li key={a.seq} className="rounded-md border border-cream-200 px-2 py-1.5 text-sm">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Time value={a.ts} /><span className="font-semibold text-navy-800">{a.agent}</span><span className="text-navy-600">{a.kind}</span><Provenance kind={a.provenance} />
                  </div>
                  <div>{a.summary}</div>
                </li>
              ))}
            </ol>
          )}
        </Card>
        <Card title="Status history">
          <ol className="space-y-1 text-xs">
            {(detail.data?.history ?? []).map((h: any) => (
              <li key={h.seq} className="flex flex-wrap items-center gap-1"><Time value={h.ts} /> <Status value={h.from_status} /> → <Status value={h.to_status} /> <span className="text-navy-600">{h.actor}</span></li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}
