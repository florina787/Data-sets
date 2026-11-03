import { useState } from "react";
import { Plot } from "../components/Plot";
import { Badge, Button, Card, ChartCard, DataClassBadge, Markdown, Note, PageHeader, Spinner, Table } from "../components/ui";
import { api, useApi } from "../lib/api";
import { trendParams, useApp } from "../lib/store";
import { SERIES } from "../lib/format";

export default function Metrics() {
  const s = useApp();
  const live = useApi<any>("/metrics/live", undefined, 5000);
  const hist = useApi<any>("/metrics/history", trendParams(s));
  const alerts = useApi<any[]>("/metrics/alerts", { currency: s.currency, dc: s.dc });
  const [why, setWhy] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ask = async () => { setBusy(true); try { const r = await api<any>("/chat", { method: "POST", body: { message: "Why did Sherin spend more money today?", currency: s.currency, dc: s.dc } }); setWhy(r.text); } finally { setBusy(false); } };
  const h = hist.data;
  const L = live.data;
  return (
    <div>
      <PageHeader title="System Metrics" subtitle="OpenTelemetry traces, structured logs, latency percentiles, task outcomes, inference, tokens, infrastructure and budget alerts." />
      <div className="mb-4 grid gap-3 md:grid-cols-4 xl:grid-cols-8">
        {L ? [["API requests", L.requests], ["Failed (5xx)", L.failed], ["P50 ms", L.p50_ms], ["P95 ms", L.p95_ms], ["P99 ms", L.p99_ms], ["CPU %", L.host.cpu_pct], ["Memory %", L.host.memory_pct], ["GPU", L.host.gpu.available ? `${L.host.gpu.utilization_pct}%` : "n/a"]].map(([l, v]) => (
          <Card key={l as string} className="p-3"><div className="text-[10px] font-semibold uppercase tracking-wide text-muted">{l}</div><div className="font-display text-2xl font-semibold text-flo-900 tnum">{v ?? "—"}</div><Badge tone="green">measured live</Badge></Card>)) : <Spinner />}
      </div>
      {L && !L.host.gpu.available && <Note>{L.host.gpu.reason} GPU history below is synthetic.</Note>}
      <div className="mt-3 grid gap-4 xl:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-display text-xl font-semibold text-flo-900">Budget alerts</h2>
          <ul className="mt-2 space-y-1.5">{(alerts.data ?? []).map((a) => <li key={a.id} className="flex items-center justify-between rounded-xl border border-line px-3 py-2 text-sm"><span><strong>{a.title}</strong> — {a.detail}</span><Badge tone={a.level === "ok" ? "green" : a.level === "breach" ? "red" : "amber"}>{a.level}</Badge></li>)}</ul>
          <div className="mt-3"><Button onClick={ask} disabled={busy}>{busy ? "Analysing cost records…" : "Why did Sherin spend more money today?"}</Button></div>
          {why && <div className="mt-3 rounded-xl border border-line bg-flo-50/60 p-3"><Markdown text={why} /></div>}
        </Card>
        <Card className="p-5"><h2 className="font-display text-xl font-semibold text-flo-900">Live routes (this process)</h2>
          {L && <Table dense columns={[{ key: "route", label: "Route" }, { key: "count", label: "Calls", align: "right" }, { key: "p95_ms", label: "P95 ms", align: "right" }]} rows={L.routes} />}
          {L && <Note>Measured since {L.since}. Recent OpenTelemetry spans: {L.recent_spans.length}.</Note>}</Card>
      </div>
      {!h ? <Spinner /> : (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <ChartCard title="Latency percentiles" badges={<DataClassBadge dc={h.data_class} />}><Plot ariaLabel="Latency" height={320} data={[["p50_ms", "P50", SERIES.revenue], ["p95_ms", "P95", SERIES.ai], ["p99_ms", "P99", SERIES.cost]].map(([k, n, c]) => ({ type: "scatter", mode: "lines", name: n, x: h.x, y: h.series[k], line: { color: c } }))} layout={{ yaxis: { title: { text: "ms" } } }} /></ChartCard>
          <ChartCard title="Task outcomes" badges={<DataClassBadge dc={h.data_class} />}><Plot ariaLabel="Tasks" height={320} data={[{ type: "bar", name: "Succeeded", x: h.x, y: h.series.succeeded, marker: { color: SERIES.savings } }, { type: "bar", name: "Failed", x: h.x, y: h.series.failed, marker: { color: SERIES.cost } }, { type: "scatter", mode: "lines", name: "Human corrections (rework)", x: h.x, y: h.series.human_corrections, line: { color: SERIES.ai } }]} layout={{ barmode: "stack" }} /></ChartCard>
          <ChartCard title="Tool calls, retries, request volume" badges={<DataClassBadge dc={h.data_class} />}><Plot ariaLabel="Tool calls" height={320} data={[{ type: "scatter", mode: "lines", name: "Tool calls", x: h.x, y: h.series.tool_calls, line: { color: SERIES.revenue } }, { type: "scatter", mode: "lines", name: "Retries", x: h.x, y: h.series.retries, line: { color: SERIES.cost } }, { type: "scatter", mode: "lines", name: "Requests", x: h.x, y: h.series.requests, yaxis: "y2", line: { color: SERIES.opex, dash: "dot" } }]} layout={{ yaxis2: { overlaying: "y", side: "right", showgrid: false } }} /></ChartCard>
          <ChartCard title="Inference time and tokens" badges={<DataClassBadge dc={h.data_class} />}><Plot ariaLabel="Inference" height={320} data={[{ type: "bar", name: "Input tokens", x: h.x, y: h.series.input_tokens, marker: { color: SERIES.local } }, { type: "bar", name: "Output tokens", x: h.x, y: h.series.output_tokens, marker: { color: SERIES.paid } }, { type: "scatter", mode: "lines", name: "Avg model inference ms", x: h.x, y: h.series.inference_ms_avg, yaxis: "y2", line: { color: SERIES.profit } }]} layout={{ barmode: "stack", yaxis: { tickformat: "~s" }, yaxis2: { overlaying: "y", side: "right", showgrid: false } }} /></ChartCard>
          <ChartCard title="CPU, memory, GPU" className="xl:col-span-2" badges={<DataClassBadge dc={h.data_class} />}><Plot ariaLabel="Utilisation" height={300} data={[["cpu_pct", "CPU %", SERIES.revenue], ["mem_pct", "Memory %", SERIES.ai], ["gpu_pct", "GPU %", SERIES.cost]].map(([k, n, c]) => ({ type: "scatter", mode: "lines", name: n, x: h.x, y: h.series[k], line: { color: c } }))} layout={{ yaxis: { range: [0, 100] } }} /></ChartCard>
        </div>
      )}
    </div>
  );
}
