import { Fragment, useState } from "react";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { useApp } from "../context";
import { HBars } from "../components/charts";

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
      <TokenUsage />
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

const fmt = (n: number | null | undefined) => (n == null ? "–" : n.toLocaleString());

function TokenUsage() {
  const { user } = useApp();
  const [days, setDays] = useState(30);
  const [mine, setMine] = useState(false);
  const { data: u, error } = usePoll<any>(user ? `/api/llm/usage?days=${days}&mine=${mine}` : null, 15000);
  const t = u?.totals;
  const maxDay = Math.max(1, ...(u?.by_day ?? []).map((d: any) => d.prompt_tokens + d.completion_tokens));
  return (
    <Card title="Local-model token usage">
      {!user ? <p className="text-sm text-navy-600">Sign in to see token usage.</p> : error ? <Notice kind="error">{error}</Notice> : !u ? <Empty>Loading…</Empty> : (
        <div className="space-y-4" data-testid="token-usage">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {[1, 7, 30].map((d) => (
              <button key={d} className={days === d ? "btn-primary" : "btn-ghost"} aria-pressed={days === d} onClick={() => setDays(d)}>{d === 1 ? "24 h" : `${d} days`}</button>
            ))}
            <label className="ml-2 flex items-center gap-1.5 text-navy-600">
              <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only my calls
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Prompt tokens" value={fmt(t.prompt_tokens)} sub="reported by the model server" />
            <Stat label="Completion tokens" value={fmt(t.completion_tokens)} sub="reported by the model server" />
            <Stat label="Model calls" value={fmt(t.calls)} sub={`${fmt(t.ok)} ok · ${fmt(t.failed)} failed`} />
            <Stat label="Cache hits" value={fmt(t.cached)} sub={t.cache_hit_rate == null ? "no calls yet" : `${Math.round(t.cache_hit_rate * 100)}% of calls · 0 tokens each`} />
            <Stat label="Latency p50 / p95" value={u.latency_ms.p50 == null ? "–" : `${Math.round(u.latency_ms.p50)} / ${Math.round(u.latency_ms.p95)} ms`} sub={`${u.latency_ms.samples} uncached calls`} />
            <Stat label="Calls without counts" value={fmt(t.unreported)} sub="server sent no usage; never estimated" />
          </div>
          {t.calls === 0 ? <Empty>No local-model calls in this window. Configure FOODCARE_LLM_BASE_URL and ask the copilot in LIVE mode.</Empty> : (
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <div className="label mb-2">Tokens per day</div>
                <div className="space-y-1.5" role="list" aria-label="Tokens per day">
                  {u.by_day.map((d: any) => {
                    const total = d.prompt_tokens + d.completion_tokens;
                    return (
                      <div key={d.day} role="listitem" className="flex items-center gap-2 text-xs">
                        <span className="w-20 font-mono text-navy-600">{d.day.slice(5)}</span>
                        <div className="flex h-3 flex-1 overflow-hidden rounded bg-navy-100" title={`${fmt(d.prompt_tokens)} prompt + ${fmt(d.completion_tokens)} completion`}>
                          <div style={{ background: "#38bdf8", width: `${(d.prompt_tokens / maxDay) * 100}%` }} />
                          <div style={{ background: "#fbbf24", width: `${(d.completion_tokens / maxDay) * 100}%` }} />
                        </div>
                        <span className="w-24 text-right font-mono">{fmt(total)}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs text-navy-600"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#38bdf8" }} /> prompt · <span className="inline-block h-2 w-2 rounded-sm" style={{ background: "#fbbf24" }} /> completion</p>
              </div>
              <div>
                <div className="label mb-2">Tokens by purpose</div>
                <HBars ariaLabel="Tokens by purpose" format={fmt}
                  items={u.by_purpose.map((p: any) => ({ label: p.purpose, value: p.prompt_tokens + p.completion_tokens, note: `${p.calls} calls · ${p.model}` }))} />
              </div>
            </div>
          )}
          <p className="text-xs text-navy-600">{u.note} Prometheus: <code>/metrics</code> → <code>foodcare_llm_tokens_total</code>.</p>
        </div>
      )}
    </Card>
  );
}
