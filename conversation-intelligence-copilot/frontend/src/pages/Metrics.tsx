import { Gauge } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataTable } from "@/components/charts/ChartRenderer";
import { Badge, Card, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton, Stat } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { humanize, ms, num, pct } from "@/lib/format";
import { api } from "@/services/api";

export default function Metrics() {
  const { data, error, loading, reload } = useAsync(() => api.get<any>("/api/telemetry/summary"), []);
  const ev = useAsync(() => api.get<any>("/api/evaluation/results"), []);
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-[600px]" />;
  const r = data.requests, l = data.llm, p = data.pipeline;
  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <PageHeader title="System Metrics" icon={<Gauge className="h-5 w-5" />} subtitle="Measured from this deployment's telemetry store — latency, usage, failures, coverage and quality. Nothing here is simulated." />
      <section className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Requests" value={num(r.n)} hint={`${num(r.sessions)} sessions`} />
        <Stat label="Completed" value={num(r.ok)} hint={`${num(r.failed)} other statuses`} />
        <Stat label="p50 latency" value={ms(r.p50_ms)} />
        <Stat label="p95 latency" value={ms(r.p95_ms)} />
        <Stat label="Follow-ups" value={num(r.follow_ups)} hint="used session memory" />
        <Stat label="LLM calls" value={num(l.calls)} hint={`${num(l.failures)} failed · ${num(l.cache_hits)} cached`} tone={l.failures ? "warning" : "default"} />
        <Stat label="Tokens" value={num(l.total_tokens)} hint={`in ${num(l.input_tokens)} / out ${num(l.output_tokens)}`} />
        <Stat label="Est. cost" value={`$${(l.cost ?? 0).toFixed(4)}`} hint="configurable rates" />
      </section>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card><CardHeader title="Node latency (average)" subtitle="Per LangGraph node, across all requests" />
          <div className="p-4"><ResponsiveContainer width="100%" height={340}>
            <BarChart data={data.nodes.filter((n: any) => n.runs > n.skipped)} layout="vertical" margin={{ left: 20, right: 16 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.08)" horizontal={false} /><XAxis type="number" tickFormatter={(v) => `${v} ms`} />
              <YAxis type="category" dataKey="node" width={130} tick={{ fill: "#CBD5E1", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#17233C", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 10, fontSize: 12 }} formatter={(v: number) => ms(v)} />
              <Bar dataKey="avg_ms" fill="#6366F1" radius={[0, 6, 6, 0]} />
            </BarChart></ResponsiveContainer></div></Card>
        <Card><CardHeader title="Questions by intent" subtitle="Adoption: what analysts actually ask" />
          <div className="p-4">{data.by_intent.length ? <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data.by_intent.map((x: any) => ({ ...x, intent: humanize(x.intent) }))} layout="vertical" margin={{ left: 20, right: 16 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.08)" horizontal={false} /><XAxis type="number" allowDecimals={false} />
              <YAxis type="category" dataKey="intent" width={150} tick={{ fill: "#CBD5E1", fontSize: 11 }} />
              <Tooltip contentStyle={{ background: "#17233C", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 10, fontSize: 12 }} />
              <Bar dataKey="n" name="Questions" fill="#22D3EE" radius={[0, 6, 6, 0]} />
            </BarChart></ResponsiveContainer> : <EmptyState title="No questions yet" />}</div></Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card><CardHeader title="Data pipeline" />
          <div className="grid grid-cols-2 gap-2 p-5 pt-3">
            <Stat label="Conversations" value={num(p.conversations)} /><Stat label="Labelled" value={pct(p.labelled / p.conversations, 0)} hint={`${num(p.provisional)} provisional`} />
            <Stat label="Indexed chunks" value={num(p.embedding.chunks)} hint={p.embedding.backend} /><Stat label="Label source" value={p.label_coverage.label_source} hint={JSON.stringify(p.label_coverage.by_method)} />
          </div>
          {p.embedding.fallback_reason && <p className="px-5 pb-4 text-[11px] text-warn">{p.embedding.fallback_reason}</p>}
        </Card>
        <Card><CardHeader title="Data-quality findings" subtitle="Warnings and errors from the ingestion report" />
          <ul className="space-y-2 p-5 pt-3 text-xs">{p.quality_failures.map((q: any) => (
            <li key={q.check} className="rounded-lg border border-line p-2.5"><div className="flex justify-between"><span className="text-ink">{humanize(q.check)}</span><Badge tone="warning">{q.count}/{q.total}</Badge></div>
              <p className="mt-1 text-muted">{q.description}</p></li>))}</ul></Card>
        <Card><CardHeader title="Model reliability" />
          <div className="space-y-2 p-5 pt-3 text-xs">
            <p className="text-muted">Modes used: {data.llm_modes.map((m: any) => `${m.llm_mode ?? "n/a"} × ${m.n}`).join(", ") || "—"}</p>
            <p className="text-muted">Retries: {num(l.retries)} · Rate-limit events: {num(l.rate_limited)}</p>
            {data.llm_errors.length ? <ul className="space-y-1">{data.llm_errors.map((e: any) => <li key={e.error} className="rounded-lg border border-neg/20 bg-neg/5 p-2 text-[11px] text-ink/80">{e.n}× {String(e.error).slice(0, 160)}</li>)}</ul>
              : <p className="text-faint">No model errors recorded.</p>}
          </div></Card>
      </div>
      <Card><CardHeader title="Evaluation results" subtitle={ev.data?.generated_at ? `Generated ${ev.data.generated_at}` : "Run `make evaluate`"} />
        <div className="p-5 pt-3">{ev.loading ? <Skeleton className="h-24" /> : !ev.data || ev.data.status === "not_run" ? <EmptyState title="No evaluation run yet" description={ev.data?.note} /> : (
          <div className="grid gap-3 md:grid-cols-4">{(ev.data.summary ?? []).map((s: any) => <Stat key={s.metric} label={s.metric} value={s.display} hint={s.note} />)}</div>
        )}</div></Card>
      <Card><CardHeader title="UI interactions" subtitle="Drilldowns and evidence opens recorded by the app" />
        <div className="p-4">{data.ui_events.length ? <DataTable rows={data.ui_events} /> : <EmptyState title="No interactions recorded yet" />}</div></Card>
    </div>
  );
}
