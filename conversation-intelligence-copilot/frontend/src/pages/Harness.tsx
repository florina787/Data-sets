import { Network } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { Badge, Card, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/common/ui";
import { AgentGraph, type NodeState } from "@/components/workflow/AgentGraph";
import { useAsync } from "@/hooks/useAsync";
import { humanize, ms, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import type { GraphDefinition, Trace } from "@/types/api";

function Json({ value }: { value: unknown }) {
  if (value === null || value === undefined || (typeof value === "object" && !Object.keys(value as object).length)) return <p className="text-xs text-faint">—</p>;
  return <pre className="max-h-64 overflow-auto rounded-lg border border-line bg-bg/60 p-2.5 font-mono text-[11px] leading-relaxed text-ink/80">{JSON.stringify(value, null, 2)}</pre>;
}

export default function Harness() {
  const { requestId } = useParams();
  const nav = useNavigate();
  const { turns } = useApp();
  const graph = useAsync(() => api.graph(), []);
  const recent = useAsync(() => api.get<any[]>("/api/traces?limit=25"), [turns.length, turns.at(-1)?.status]);
  const live = turns.find((t) => t.requestId && (t.requestId === requestId || (!requestId && t === turns.at(-1))));
  const activeId = requestId ?? live?.requestId ?? recent.data?.[0]?.request_id;
  const isLive = live?.status === "streaming" && live.requestId === activeId;
  const trace = useAsync(() => (activeId && !isLive ? api.trace(activeId) : Promise.resolve(null as Trace | null)), [activeId, isLive]);
  const [selected, setSelected] = useState<string | null>("supervisor");

  const states: Record<string, NodeState> = useMemo(() => {
    if (isLive && live) return Object.fromEntries(Object.entries(live.nodes).map(([k, v]) => [k, { status: v.status, duration_ms: v.duration_ms }]));
    const out: Record<string, NodeState> = {};
    trace.data?.nodes.forEach((n) => { out[n.node] = { status: n.status, duration_ms: n.duration_ms, retries: n.retries }; });
    return out;
  }, [isLive, live, trace.data]);

  const def = graph.data as GraphDefinition | null;
  const nodeInfo = def?.nodes.find((n) => n.id === selected);
  const nodeTrace = trace.data?.nodes.find((n) => n.node === selected);
  const liveNode = isLive && selected ? live?.nodes[selected] : undefined;
  const req = trace.data?.request;

  return (
    <div className="mx-auto max-w-[1600px]">
      <PageHeader title="Agent Harness" icon={<Network className="h-5 w-5" />}
        subtitle="The real LangGraph execution for each question: which agents ran, in what order, how long they took, and what they produced." />
      <div className="grid gap-5 xl:grid-cols-[270px_1fr] 2xl:grid-cols-[270px_1fr_380px]">
        <Card className="p-3">
          <p className="label px-2 pb-2">Recent requests</p>
          {recent.loading && !recent.data ? <Skeleton className="h-64" /> : !recent.data?.length ? <EmptyState title="No requests yet" description="Ask a question in Ask Intelligence." /> : (
            <ul className="max-h-[680px] space-y-0.5 overflow-y-auto">
              {recent.data.map((r) => (
                <li key={r.request_id}>
                  <button onClick={() => nav(`/harness/${r.request_id}`)} className={cn("focus-ring w-full rounded-lg px-2 py-2 text-left text-xs hover:bg-white/[0.04]", r.request_id === activeId && "bg-indigo/10")}>
                    <p className="line-clamp-2 text-ink/90">{r.question}</p>
                    <p className="mt-1 flex gap-2 text-[10px] text-faint"><span>{humanize(r.intent?.category)}</span><span>{ms(r.latency_ms)}</span><span>{timeAgo(r.created_at)}</span>
                      <span className={r.status === "completed" ? "text-pos" : "text-warn"}>{r.status}</span></p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="space-y-3">
          {req && (
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <Badge tone="indigo">{humanize(req.intent?.category)}</Badge><Badge>{ms(req.latency_ms)}</Badge><Badge>{req.llm_mode ?? "—"} mode</Badge>
              <Badge tone={req.quality_status === "pass" ? "positive" : "warning"}>QA {req.quality_status ?? "—"}</Badge>
              <span className="truncate text-muted">“{req.question}”</span>
            </div>
          )}
          {isLive && <Badge tone="cyan">Live — statuses update as nodes start and finish</Badge>}
          {graph.error ? <ErrorState message={graph.error.message} onRetry={graph.reload} /> : !def ? <Skeleton className="h-[640px]" /> :
            <AgentGraph definition={def} states={states} selected={selected} onSelect={setSelected} finished={!isLive && !!trace.data} />}
          <div className="flex flex-wrap gap-3 text-[11px] text-faint">
            {[["bg-pos", "completed"], ["bg-cyan", "running"], ["bg-neg", "failed"], ["border border-dashed border-faint", "skipped (not needed for this question)"], ["bg-faint", "pending"]].map(([c, l]) => (
              <span key={l} className="flex items-center gap-1.5"><span className={cn("h-2.5 w-2.5 rounded-full", c)} />{l}</span>
            ))}
            <span>Dashed edges are conditional routes chosen by the supervisor.</span>
          </div>
        </div>
        <Card className="h-fit xl:col-start-2 2xl:col-start-auto">
          <CardHeader title={nodeInfo?.label ?? "Select a node"} subtitle={nodeInfo?.role} />
          <div className="space-y-3 p-5 pt-3 text-xs">
            {!selected ? null : trace.loading && !isLive ? <Skeleton className="h-40" /> : (
              <>
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-lg border border-line p-2"><p className="label">Status</p><p className="mt-1 capitalize text-ink">{liveNode?.status ?? nodeTrace?.status ?? "—"}</p></div>
                  <div className="rounded-lg border border-line p-2"><p className="label">Duration</p><p className="num mt-1 text-ink">{ms(liveNode?.duration_ms ?? nodeTrace?.duration_ms)}</p></div>
                  <div className="rounded-lg border border-line p-2"><p className="label">Retries</p><p className="num mt-1 text-ink">{nodeTrace?.retries ?? 0}</p></div>
                </div>
                {(nodeTrace?.error || liveNode?.error) && <ErrorState message={(nodeTrace?.error ?? liveNode?.error) as string} />}
                <div><p className="label mb-1">Input (sanitised)</p><Json value={nodeTrace?.input_summary} /></div>
                <div><p className="label mb-1">Output summary</p><Json value={liveNode?.summary ?? nodeTrace?.output_summary} /></div>
                <div><p className="label mb-1">Tool / model metadata</p><Json value={nodeTrace?.meta_json} /></div>
              </>
            )}
            {trace.data && (
              <div>
                <p className="label mb-1">Model calls in this request</p>
                {trace.data.llm_calls.length === 0 ? <p className="text-faint">None — deterministic path (see model status in the header).</p> : (
                  <ul className="space-y-1">{trace.data.llm_calls.map((c) => (
                    <li key={c.id} className="rounded-lg border border-line p-2"><span className="text-ink">{c.purpose}</span> · {c.prompt_id}@{c.prompt_version} · {c.status}
                      · {c.total_tokens} tok · {ms(c.latency_ms)}{c.cache_hit ? " · cache" : ""}{c.error ? <span className="block text-neg">{String(c.error).slice(0, 140)}</span> : null}</li>
                  ))}</ul>
                )}
              </div>
            )}
            {activeId && <Link to="/" className="text-violet hover:underline">← Back to the conversation</Link>}
          </div>
        </Card>
      </div>
    </div>
  );
}
