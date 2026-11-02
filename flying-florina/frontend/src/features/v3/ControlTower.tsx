import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { TowerControl } from "lucide-react";
import { AgentGraph } from "@/components/AgentGraph";
import { AgentTimeline } from "@/components/AgentTimeline";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Kpi, PageHeader, Skeleton, statusTone } from "@/components/ui";
import { get } from "@/lib/api";
import type { RunView, WorkflowEvent } from "@/lib/types";
import { Banner, Metric, num, pct } from "./common";

type CT = {
  runs: { id: string; workflow: string; query: string; status: string; created: string }[];
  selected: { run: { id: string; workflow: string; query: string; status: string }; graph: NonNullable<RunView["graph"]> | null;
    nodes: { step: string; agent: string; status: string; attempts: number; retries: number; duration_ms: number }[]; tools: { tool: string; status: string; duration_ms: number; ts: string }[];
    plan: { intent: string; agents_json: string[]; tools_json: string[]; budget_json: Record<string, number>; usage_json: Record<string, unknown>; outcome: string } | null } | null;
  timeline: WorkflowEvent[] | null;
  governance: { allowed: number; denied: number; by_policy: [string, number][]; blocked: { decision: string; policy_id: string; action: string; tool: string | null; reason: string; ts: string }[];
    pending_approvals: { id: string; title: string; requested_by: string; requested_at: string }[]; approved: number; validation_failures: { step: string; status: string; summary: string }[] };
  model: { qwen: { available: boolean; model: string | null; mode: string; required: boolean; reason: string }; queue_depth: number; note: string;
    metrics: { calls?: number; latency_ms?: { p50?: number; p95?: number }; first_token_ms?: { p50?: number }; tokens_per_s?: { p50?: number }; cache_hit_rate?: number; prompt_tokens?: number; completion_tokens?: number;
      system?: { cpu_load_1m?: number; process_rss_mb?: number; mem_available_mb?: number; mem_total_mb?: number; gpu?: unknown } } & Record<string, unknown> };
  evaluation: { task_success_rate: number | null; harness_runs: number; evidence_coverage: number | null; tool_call_reliability: number | null; tool_calls: number;
    hallucination_eval: { explanations_checked: number; passed: number; note: string }; forecast_quality: Record<string, number>; workflow_failure_rate: number | null; mean_tool_calls_per_run: number | null };
  recovery: { failed_runs: { id: string; workflow: string; status: string; created: string }[]; retries: { run_id: string; step: string; agent: string; attempt: number; summary: string }[];
    escalations: unknown[]; partial_results: { run_id: string; intent: string; outcome: string }[] };
  mode: string;
};

export function ControlTower() {
  const [params] = useSearchParams();
  const [run, setRun] = useState<string | null>(params.get("run"));
  const { data, error } = useQuery({ queryKey: ["ct", run], queryFn: () => get<CT>(`/api/harness/control-tower${run ? `?run_id=${run}` : ""}`), refetchInterval: 5000 });
  if (error) return <ErrorBox error={error} />;
  const d = data?.data;
  const m = d?.model.metrics;
  const sys = (m?.system ?? {}) as Record<string, number | undefined>;
  return (
    <div className="space-y-4">
      <PageHeader title="Agent Harness Control Tower" icon={<TowerControl className="h-5 w-5" />}
        subtitle="The governed execution harness: plans, specialist agents, tool calls, policy outcomes, model performance, evaluation and recovery — all read from recorded execution events." />
      <Banner>Live mode: every panel is built from rows written while workflows ran (workflow_events, tool_invocations, policy_decisions, approvals, harness_plans, llm_calls). Nothing is animated or simulated. Refreshes every 5 s.</Banner>
      {!d ? <Skeleton className="h-96" /> : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="label">Run</span>
            <select className="input !py-1 w-full min-w-0 max-w-[560px] text-xs sm:w-auto" value={d.selected?.run.id ?? ""} onChange={(e) => setRun(e.target.value)} aria-label="Select run">
              {d.runs.map((r) => <option key={r.id} value={r.id}>{r.created.slice(5, 16).replace("T", " ")} · {r.workflow} · {r.status} · {r.query.slice(0, 60)}</option>)}
            </select>
            {d.selected && <Badge tone={statusTone(d.selected.run.status)}>{d.selected.run.status}</Badge>}
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
            <Card title="1 · Agent execution graph" subtitle={d.selected?.plan ? `Plan: ${d.selected.plan.agents_json.join(", ")} · budget ${d.selected.plan.budget_json.max_tool_calls} tool calls / ${d.selected.plan.budget_json.max_wall_s}s · outcome ${d.selected.plan.outcome}` : "2.0 workflow (no harness plan)"}>
              {d.selected?.graph && d.timeline ? <AgentGraph graph={d.selected.graph} events={d.timeline} height={320} /> : <p className="text-sm muted">No run selected.</p>}
              {d.selected && <DataTable rows={d.selected.nodes as unknown as Record<string, unknown>[]} columns={[{ key: "step", label: "Step" }, { key: "agent", label: "Agent" }, { key: "status", label: "Status" },
                { key: "attempts", label: "Attempts" }, { key: "retries", label: "Retries" }, { key: "duration_ms", label: "ms" }]} />}
            </Card>
            <Card title="2 · Workflow timeline">{d.timeline ? <AgentTimeline events={d.timeline} compact /> : null}
              {d.selected?.tools.length ? <p className="mt-2 text-xs muted">Tool calls: {d.selected.tools.map((t) => `${t.tool} (${t.status}, ${Math.round(t.duration_ms)} ms)`).join(" · ")}</p> : null}
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="3 · Governance">
              <div className="grid grid-cols-3 gap-2"><Metric k="Allowed" v={d.governance.allowed} /><Metric k="Blocked" v={d.governance.denied} /><Metric k="Pending approvals" v={d.governance.pending_approvals.length} /></div>
              <p className="label mt-3">Blocked operations</p>
              <ul className="mt-1 space-y-1 text-xs">{d.governance.blocked.slice(0, 6).map((b, i) => <li key={i}><Badge tone="red">{b.policy_id}</Badge> {b.action} {b.tool ?? ""} — <span className="muted">{b.reason.slice(0, 90)}</span></li>)}</ul>
              <p className="label mt-3">Validation failures</p>
              <ul className="mt-1 space-y-1 text-xs">{d.governance.validation_failures.length ? d.governance.validation_failures.slice(0, 5).map((v, i) => <li key={i}>{v.step}: <span className="muted">{v.summary.slice(0, 100)}</span></li>) : <li className="muted">None recorded.</li>}</ul>
            </Card>
            <Card title="4 · Model performance (local Qwen)" subtitle={d.model.qwen.available ? `${d.model.qwen.model} · ${d.model.qwen.mode}` : `Not reachable: ${d.model.qwen.reason ?? ""}`.slice(0, 140)}>
              <div className="grid grid-cols-2 gap-2">
                <Metric k="Calls" v={m?.calls ?? 0} /><Metric k="Latency p50 / p95 (ms)" v={`${num(m?.latency_ms?.p50, 0)} / ${num(m?.latency_ms?.p95, 0)}`} />
                <Metric k="First token p50 (ms)" v={num(m?.first_token_ms?.p50, 0)} /><Metric k="Tokens/s p50" v={num(m?.tokens_per_s?.p50, 1)} />
                <Metric k="Tokens in / out" v={`${m?.prompt_tokens ?? 0} / ${m?.completion_tokens ?? 0}`} /><Metric k="Cache hit rate" v={pct(m?.cache_hit_rate as number | undefined)} />
                <Metric k="CPU load (1 min)" v={num(sys.cpu_load_1m, 2)} /><Metric k="Process memory (MB)" v={num(sys.process_rss_mb, 0)} />
                <Metric k="Queue depth" v={d.model.queue_depth} /><Metric k="Model load" v={d.model.qwen.available ? "loaded" : "not loaded"} />
              </div>
              <p className="mt-2 text-[11px] muted">{d.model.note}</p>
            </Card>
            <Card title="5 · Agent evaluation">
              <div className="grid grid-cols-2 gap-2">
                <Metric k="Task success rate" v={pct(d.evaluation.task_success_rate)} hint={`${d.evaluation.harness_runs} harness runs`} />
                <Metric k="Evidence coverage" v={pct(d.evaluation.evidence_coverage)} />
                <Metric k="Tool-call reliability" v={pct(d.evaluation.tool_call_reliability)} hint={`${d.evaluation.tool_calls} calls (30 days)`} />
                <Metric k="Workflow failure rate" v={pct(d.evaluation.workflow_failure_rate)} />
                <Metric k="Hallucination checks" v={`${d.evaluation.hallucination_eval.passed}/${d.evaluation.hallucination_eval.explanations_checked} passed`} hint={d.evaluation.hallucination_eval.note} />
                <Metric k="Forecast MAE 30d / coverage" v={`${num(d.evaluation.forecast_quality.mae)} / ${pct(d.evaluation.forecast_quality.coverage_80)}`} />
              </div>
            </Card>
          </div>
          <Card title="6 · Recovery">
            <div className="grid gap-3 sm:grid-cols-4">
              <Kpi label="Failed / halted runs" value={d.recovery.failed_runs.length} /><Kpi label="Retry attempts" value={d.recovery.retries.length} />
              <Kpi label="Escalations (pending approvals)" value={d.recovery.escalations.length} /><Kpi label="Partial results (missing evidence)" value={d.recovery.partial_results.length} />
            </div>
            {!!d.recovery.retries.length && <DataTable rows={d.recovery.retries as unknown as Record<string, unknown>[]} columns={[{ key: "run_id", label: "Run" }, { key: "step", label: "Step" }, { key: "agent", label: "Agent" }, { key: "attempt", label: "Attempt" }, { key: "summary", label: "Error" }]} />}
          </Card>
        </>
      )}
    </div>
  );
}
