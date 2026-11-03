import { Fragment, useState } from "react";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card py-3">
      <div className="label">{label}</div>
      <div className={`mt-1 ${/^[\d.]/.test(value) ? "kpi" : "text-lg font-semibold text-navy-900"}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-navy-600">{sub}</div>}
    </div>
  );
}

export default function Observability() {
  const { data: r, error } = usePoll<any>("/api/system/resources", 5000);
  const { data: runs } = usePoll<any>("/api/agents/runs?limit=40", 10000);
  const [open, setOpen] = useState<string | null>(null);
  const llm = r?.llm;
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">System observability</h1>
        <p className="text-sm text-navy-600">Measured on the machine running the backend. Refreshes every 5 seconds with one lightweight sample; no background monitoring agents.</p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!r ? <Empty>Loading…</Empty> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <Stat label="Machine CPU" value={`${r.cpu_percent}%`} sub={`${r.cpu_count} logical cores${r.load_avg ? ` · load ${r.load_avg[0]}` : ""}`} />
            <Stat label="Machine RAM" value={`${r.ram_percent}%`} sub={`${r.ram_used_gb} / ${r.ram_total_gb} GB`} />
            <Stat label="Backend process" value={`${r.process.rss_mb} MB`} sub={`CPU ${r.process.cpu_percent}% · ${r.process.threads} threads`} />
            <Stat label="Vision queue" value={`${r.vision_queue.running} running`} sub={`${r.vision_queue.queued} queued / limit ${r.vision_queue.queue_limit} · ${r.vision_queue.rejected} rejected`} />
            <Stat label="Local model" value={llm?.configured ? (llm.model ?? "configured") : "Not configured"}
              sub={llm?.configured ? `${llm.in_flight} running · ${llm.queue_depth} queued · p50 ${llm.latency_ms?.p50 ?? "–"} ms` : "DEMO answers only"} />
            <Stat label="Memory database" value={`${(r.memory_db.bytes / 1e6).toFixed(2)} MB`} sub={`${r.memory_db.conversations} conversations · ${r.memory_db.agent_runs} agent runs`} />
          </div>
          {llm?.configured && (
            <Card title="Local model calls">
              <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
                {Object.entries(llm.stats).map(([k, v]) => <div key={k}><span className="text-navy-600">{k.replace(/_/g, " ")}</span> <b className="font-mono">{String(v)}</b></div>)}
              </div>
            </Card>
          )}
        </>
      )}
      <Card title="Recent agent executions (recorded traces)">
        {!runs?.runs?.length ? <Empty>No agent runs recorded yet. Ask the copilot or inspect an image.</Empty> : (
          <table className="table">
            <thead><tr><th>Agent</th><th>Status</th><th>Started</th><th>Duration</th><th>Tools</th><th>Input</th></tr></thead>
            <tbody>{runs.runs.map((a: any) => (
              <Fragment key={a.id}>
                <tr className="cursor-pointer" onClick={() => setOpen(open === a.id ? null : a.id)} aria-expanded={open === a.id}>
                  <td className="font-mono text-xs">{a.agent}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs ${a.status === "ok" ? "bg-leaf-100 text-leaf-700" : a.status === "error" ? "bg-brick-100 text-brick-700" : "bg-amber-100 text-amber-700"}`}>{a.status}</span></td>
                  <td className="text-xs">{new Date(a.started_at).toLocaleTimeString()}</td>
                  <td className="font-mono text-xs">{a.duration_ms} ms</td>
                  <td className="text-xs">{a.tool_calls.length}</td>
                  <td className="max-w-[360px] truncate text-xs">{a.input_summary}</td>
                </tr>
                {open === a.id && (
                  <tr><td colSpan={6}>
                    <ul className="space-y-0.5 font-mono text-xs">{a.tool_calls.map((t: any) => (
                      <li key={t.id}>{t.status === "ok" ? "✓" : "✗"} {t.tool} · {t.duration_ms} ms{t.error ? ` · ${t.error}` : ""}</li>
                    ))}</ul>
                    <p className="mt-1 text-xs text-navy-600">Output: {a.output_summary}</p>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
