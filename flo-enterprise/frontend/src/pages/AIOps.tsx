import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { pct } from "@/lib/format";

const ch = createColumnHelper<any>();
type Tab = "overview" | "traces" | "registry" | "quality" | "evals";

export default function AIOps() {
  const [tab, setTab] = useState<Tab>("overview");
  return (
    <div className="space-y-4">
      <PageHeader title="AI Operations — Observability, Cost & Capacity" subtitle="Internal dashboard over privacy-redacted agent traces. Historical traces marked synthetic are demo data; live traces come from executions in this deployment." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview & capacity" }, { id: "traces", label: "Traces & workflows" }, { id: "registry", label: "Agent registry" },
        { id: "quality", label: "Data quality" }, { id: "evals", label: "Evaluations & load tests" }]} />
      {tab === "overview" && <Overview />}{tab === "traces" && <Traces />}{tab === "registry" && <Registry />}{tab === "quality" && <Quality />}{tab === "evals" && <Evals />}
    </div>
  );
}

function Overview() {
  const { can } = useApp();
  const qc = useQueryClient();
  const [live, setLive] = useState(false);
  const q = useQuery({ queryKey: ["aiops", live], queryFn: () => api(`/api/aiops/overview?include_synthetic=${!live}`), refetchInterval: 15000 });
  const fault = useMutation({ mutationFn: (mode: string) => api("/api/aiops/faults/market-data", { method: "POST", json: { mode } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["aiops"] }) });
  const reset = useMutation({ mutationFn: () => api("/api/aiops/breakers/reset", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["aiops"] }) });
  const tk = tokens();
  const d = q.data;
  const daily = useMemo(() => d && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis" }, xAxis: axis({ type: "category", data: d.daily.map((x: any) => x.date.slice(5)) }),
    yAxis: axis({ type: "value" }), series: [{ name: "Runs", type: "bar", stack: "r", data: d.daily.map((x: any) => x.runs - x.failures), itemStyle: { color: tk.series[0] } },
      { name: "Failures", type: "bar", stack: "r", data: d.daily.map((x: any) => x.failures), itemStyle: { color: tk.series[1], borderRadius: [3, 3, 0, 0] } }] }), [d, tk]);
  const lat = useMemo(() => d && ({ ...baseOption(), grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true }, tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `${v} ms` },
    yAxis: axis({ type: "category", data: d.agents.map((a: any) => a.agent.replace("_agent", "")) }), xAxis: axis({ type: "value" }),
    series: [{ name: "p95 latency", type: "bar", data: d.agents.map((a: any) => a.p95_ms), itemStyle: { color: tk.series[0], borderRadius: [0, 3, 3, 0] } }] }), [d, tk]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const t = d.totals;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2"><Button size="sm" variant={live ? "primary" : "secondary"} onClick={() => setLive(!live)}>{live ? "Live traces only" : "Including synthetic history"}</Button>
        <Badge tone="blue">telemetry: {d.observability_mode}</Badge>
        {can("aiops:manage") && <><Button size="sm" onClick={() => fault.mutate("down")}>Inject market-data outage</Button><Button size="sm" onClick={() => fault.mutate("none")}>Clear fault</Button>
          <Button size="sm" onClick={() => reset.mutate()}>Reset circuit breakers</Button></>}</div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Workflows" value={t.workflows} sub={`${t.traces} agent traces`} /><Stat label="Success rate" value={pct(t.success_rate, 1)} />
        <Stat label="Cost / workflow" value={`$${t.cost_per_workflow.toFixed(4)}`} sub="USD (estimates)" /><Stat label="Cost / successful wf" value={t.cost_per_successful_workflow != null ? `$${t.cost_per_successful_workflow.toFixed(4)}` : "—"} />
        <Stat label="Tokens" value={t.tokens.toLocaleString()} /><Stat label="Tool failure rate" value={pct(t.tool_failure_rate, 1)} />
        <Stat label="Active / max workflows" value={`${d.capacity.active_workflows} / ${d.capacity.max_concurrent_workflows}`} sub={`queue depth ${d.capacity.job_queue_depth}`} />
        <Stat label="Agent cache hit rate" value={pct(d.capacity.agent_result_cache.hit_rate, 1)} sub={`response cache ${pct(d.capacity.response_cache.hit_rate, 1)}`} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard id="agent_failures" title="Daily agent runs and failures" option={daily} rows={d.daily} />
        <ChartCard id="agent_failures" title="p95 latency by agent" option={lat} height={360} rows={d.agents} />
      </div>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Circuit breakers & model utilization</h3>
        <div className="flex flex-wrap gap-2">{d.breakers.length === 0 ? <span className="text-xs text-muted">No breakers tripped since start.</span> : d.breakers.map((b: any) => <Badge key={b.name} tone={b.state === "closed" ? "good" : "crit"}>{b.name}: {b.state} ({b.failures})</Badge>)}</div>
        <div className="mt-2 text-xs text-muted">{Object.entries(d.models).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div><p className="mt-2 text-[11px] text-muted">{d.note}</p></Card>
      <DataTable label="Agents" data={d.agents} columns={[ch.accessor("agent", { header: "Agent" }), ch.accessor("runs", { header: "Runs" }), ch.accessor("failure_rate", { header: "Failure rate", cell: (c) => pct(c.getValue(), 1) }),
        ch.accessor("p50_ms", { header: "p50 ms" }), ch.accessor("p95_ms", { header: "p95 ms" }), ch.accessor("retries", { header: "Retries" }), ch.accessor("cost_usd", { header: "Cost USD" }),
        ch.accessor("failure_classes", { header: "Failure classes", cell: (c) => Object.entries(c.getValue()).map(([k, v]) => `${k}:${v}`).join(" ") })]} />
    </div>
  );
}

function Traces() {
  const [wf, setWf] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["traces"], queryFn: () => api("/api/aiops/traces?limit=200") });
  const g = useQuery({ queryKey: ["wf", wf], queryFn: () => api(`/api/aiops/workflows/${wf}`), enabled: !!wf });
  const tk = tokens();
  const opt = useMemo(() => g.data && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => p.data.tip ?? p.name },
    series: [{ type: "graph", layout: "force", roam: true, zoom: 1.05, force: { repulsion: 240, edgeLength: 80 }, label: { show: true, color: tk.ink, fontSize: 11, position: "bottom" }, edgeSymbol: ["none", "arrow"],
      lineStyle: { color: tk.muted, opacity: 0.6 },
      data: Array.from(new Map(g.data.nodes.map((n: any) => [n.id, n])).values()).map((n: any) => ({ name: n.id, label: { formatter: n.label ?? n.id.replace("_agent", "") },
        symbolSize: n.type === "supervisor" ? 34 : n.type === "agent" ? 26 : 14, tip: `${n.type} ${n.status ?? ""} ${n.latency_ms ? n.latency_ms + "ms" : ""} ${n.failure_class ?? ""}`,
        itemStyle: { color: n.type === "supervisor" ? "#D4AF37" : n.status === "failed" || n.status === "deny" || n.status === "timeout" ? tk.series[1] : n.type === "agent" ? tk.series[0] : tk.series[2] } })),
      links: g.data.edges.map((e: any) => ({ source: e.from, target: e.to })) }] }), [g.data, tk]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-4">
      {wf && <ChartCard id="agent_failures" title={`Agent workflow diagram · ${wf}`} subtitle="Gold = supervisors, blue = agents, green = tool calls, orange = failed/denied" option={opt} height={380} loading={g.isLoading} error={g.error} />}
      <DataTable label="Traces" data={q.data.traces} onRowClick={(r: any) => setWf(r.workflow_id)} columns={[ch.accessor("started_at", { header: "Started", cell: (c) => c.getValue().slice(0, 19) }),
        ch.accessor("workflow_id", { header: "Workflow" }), ch.accessor("agent_id", { header: "Agent" }), ch.accessor("model", { header: "Model" }),
        ch.accessor("status", { header: "Status", cell: (c) => <Badge tone={c.getValue() === "succeeded" ? "good" : "crit"}>{c.getValue()}</Badge> }), ch.accessor("failure_class", { header: "Failure" }),
        ch.accessor("latency_ms", { header: "ms" }), ch.accessor("retry_count", { header: "Retries" }), ch.accessor("policy_outcome", { header: "Policy" }),
        ch.accessor("synthetic", { header: "Source", cell: (c) => (c.getValue() ? "synthetic" : "live") })]} />
    </div>
  );
}

function Registry() {
  const q = useQuery({ queryKey: ["agents"], queryFn: () => api("/api/agents") });
  const tools = useQuery({ queryKey: ["tools"], queryFn: () => api("/api/tools") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">Supervisors: {q.data.supervisors.join(" → ")}</p>
      <DataTable label="Agent registry" data={q.data.agents} columns={[ch.accessor("name", { header: "Agent" }), ch.accessor("version", { header: "Ver" }), ch.accessor("supervisor", { header: "Supervisor" }),
        ch.accessor("owner", { header: "Owner" }), ch.accessor("allowed_roles", { header: "Roles", cell: (c) => c.getValue().join(", ") }), ch.accessor("allowed_tools", { header: "Tools", cell: (c) => c.getValue().join(", ") }),
        ch.accessor("budget", { header: "Budget", cell: (c) => `${c.getValue().max_iterations} it · ${c.getValue().timeout_s}s · ${c.getValue().max_retries} retries` }),
        ch.accessor("data_classification", { header: "Class" }), ch.accessor("approval_requirements", { header: "Approvals", cell: (c) => c.getValue().join(", ") || "—" }),
        ch.accessor("evaluation_requirements", { header: "Evals", cell: (c) => c.getValue().join(", ") })]} />
      {tools.data && <DataTable label="Tool gateway catalog" data={tools.data.tools} columns={[ch.accessor("name", { header: "Tool" }), ch.accessor("permission", { header: "Permission" }),
        ch.accessor("upstream", { header: "Upstream" }), ch.accessor("side_effect", { header: "Side effect", cell: (c) => (c.getValue() ? "yes" : "no") }), ch.accessor("description", { header: "Description" })]} />}
    </div>
  );
}

function Quality() {
  const q = useQuery({ queryKey: ["dq"], queryFn: () => api("/api/aiops/data-quality") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-3"><div className="grid grid-cols-3 gap-3"><Stat label="Checks passing" value={`${q.data.passed} / ${q.data.total}`} tone={q.data.passed === q.data.total ? "good" : "warn"} />
      <Stat label="Pass rate" value={pct(q.data.pass_rate, 1)} /><Stat label="Dataset version" value={<span className="text-base">{q.data.dataset_version}</span>} sub={`as of ${q.data.as_of}`} /></div>
      <DataTable label="Data quality checks" data={q.data.checks} columns={[ch.accessor("check_id", { header: "Check" }), ch.accessor("data_product", { header: "Product" }), ch.accessor("name", { header: "Rule" }),
        ch.accessor("passed", { header: "Result", cell: (c) => <Badge tone={c.getValue() ? "good" : "crit"}>{c.getValue() ? "pass" : "fail"}</Badge> }), ch.accessor("severity", { header: "Severity" }), ch.accessor("detail", { header: "Measured" })]} /></div>
  );
}

function Evals() {
  const q = useQuery({ queryKey: ["evals"], queryFn: () => api("/api/aiops/evals") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const block = (title: string, v: any, hint: string) => (
    <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">{title}</h3>{v ? <pre className="max-h-96 overflow-auto scroll-thin text-[11px]">{JSON.stringify(v, null, 2)}</pre> : <p className="text-xs text-muted">Not yet generated — run <code>{hint}</code>.</p>}</Card>);
  return <div className="grid gap-4 xl:grid-cols-3">{block("Release gate", q.data.release_gate, "make release-gate")}{block("Evaluation report", q.data.eval_report, "make evals")}{block("Load test report (measured)", q.data.load_test_report, "make load-test")}</div>;
}
