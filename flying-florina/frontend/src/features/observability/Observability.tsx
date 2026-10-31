import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Gauge, Play, RefreshCw, Timer } from "lucide-react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHeader } from "@/components/ui";
import { post } from "@/lib/api";
import { datetime } from "@/lib/format";
import { useApi } from "@/lib/hooks";

type Disc = { found: boolean; runtime: string | null; model: string | null; quantization: string | null; path: string | null; base_url: string | null; size_bytes: number | null;
  parameter_size: string | null; reason: string; searched: string[]; candidates: Record<string, unknown>[]; llama_cpp_installed: boolean; gpu_offload_supported: boolean | null };
type Metrics = {
  calls: number; live_calls: number; cached_calls: number; errors: number; cache_hit_rate: number | null;
  latency_ms: { p50: number | null; p95: number | null; max: number | null }; first_token_ms: { p50: number | null; p95: number | null }; tokens_per_s: { p50: number | null; mean: number | null };
  prompt_tokens: number; completion_tokens: number; by_agent: { agent: string; calls: number; cached: number; errors: number; prompt_tokens: number; completion_tokens: number; p50_ms: number | null }[];
  recent: Record<string, unknown>[]; recent_errors: Record<string, unknown>[]; load: { model_load_ms?: number; loaded_at?: string };
  system: { platform: string; cpu_count: number; cpu_load_pct?: number; load_avg_1m?: number; process_rss_mb: number | null; system_mem_total_mb?: number; system_mem_available_mb?: number;
    gpu: { available: boolean | null; name?: string; utilization_pct?: number; memory_used_mb?: number; memory_total_mb?: number; detail?: string } };
  status: { available: boolean; mode: string; label: string; required?: boolean; discovery: Disc; runtime_info: Record<string, unknown>; last_error: string | null; external_fallback: boolean };
};
type Wf = { runs: number; success_rate: number | null; workflow_ms: { p50: number | null; p95: number | null }; by_workflow: Record<string, unknown>[];
  by_agent: { agent: string; steps: number; failed: number; retries: number; skipped: number; p50_ms: number | null; p95_ms: number | null }[];
  tools: { tool: string; status: string; n: number; ms: number }[]; policy: { policy_id: string; decision: string; n: number }[]; approvals: { status: string; n: number }[];
  route_methods: Record<string, number>; schema_failures: number; challenger: { explanations: number; rejected: number; unsupported_items: number } };
type Ev = { file: string; split: string; items: number; routing_accuracy: number; macro_f1: number; four_family_routing_accuracy: number; follow_up_accuracy: number; workflow_correctness: number;
  evidence_accuracy: number; unsupported_claim_rate: number | null; answer_completeness: number; latency_ms: { p50: number; p95: number }; governance: Record<string, unknown>;
  qwen: { available: boolean; model: string | null }; route_methods: Record<string, number> };

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);
const ms = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v).toLocaleString()} ms`);

export function Observability() {
  const qc = useQueryClient();
  const m = useApi<Metrics>(["llm-metrics"], "/api/llm/metrics");
  const w = useApi<Wf>(["obs-wf"], "/api/observability/workflows");
  const ev = useApi<Ev[]>(["obs-eval"], "/api/observability/eval");
  const refresh = useMutation({ mutationFn: () => post("/api/llm/refresh"), onSuccess: () => qc.invalidateQueries() });
  const test = useMutation({ mutationFn: () => post<Record<string, unknown>>("/api/llm/test", {}), onSettled: () => qc.invalidateQueries({ queryKey: ["llm-metrics"] }) });
  const bench = useMutation({ mutationFn: () => post<Record<string, unknown>>("/api/llm/benchmark", { repeats: 2 }), onSettled: () => qc.invalidateQueries({ queryKey: ["llm-metrics"] }) });
  const d = m.data;
  const st = d?.status;
  const disc = st?.discovery;
  return (
    <div className="space-y-5">
      <PageHeader title="Evaluation & Observability" icon={<Gauge className="h-5 w-5" />}
        subtitle="Measured values only: local Qwen inference telemetry, agent and tool reliability, governance outcomes and the four-question evaluation."
        actions={<div className="flex flex-wrap gap-2">
          <button className="btn btn-ghost !py-1 text-xs" onClick={() => refresh.mutate()} disabled={refresh.isPending}><RefreshCw className="h-3.5 w-3.5" />Re-detect Qwen</button>
          <button className="btn btn-ghost !py-1 text-xs" onClick={() => test.mutate()} disabled={test.isPending || !st?.available} data-testid="qwen-test"><Play className="h-3.5 w-3.5" />{test.isPending ? "Running…" : "Run live test"}</button>
          <button className="btn btn-primary !py-1 text-xs" onClick={() => bench.mutate()} disabled={bench.isPending || !st?.available}><Timer className="h-3.5 w-3.5" />{bench.isPending ? "Benchmarking…" : "Benchmark (uncached)"}</button>
        </div>} />
      {m.isLoading && <Loading label="Reading telemetry" />}
      {m.error ? <ErrorBox error={m.error} /> : null}
      {d && st && disc && (
        <>
          <Card title={<span className="flex items-center gap-2"><BrainCircuit className="h-4 w-4 text-cyan" />Local Qwen status</span>}
            subtitle="Discovered on this machine. Flying_Florina never downloads a model and has no external inference fallback."
            actions={<Badge tone={st.available ? "teal" : st.required ? "red" : "amber"}>{st.available ? "Local Qwen · connected" : st.mode === "off" ? "switched off" : st.required ? "required · not reachable" : "not found"}</Badge>}>
            <div className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4" data-testid="qwen-status-panel">
              <Field k="Model" v={disc.model ?? "—"} />
              <Field k="Quantization" v={disc.quantization ?? "—"} />
              <Field k="Runtime" v={disc.runtime ?? "—"} />
              <Field k="Location" v={disc.path ?? disc.base_url ?? "—"} />
              <Field k="Parameters / size" v={`${disc.parameter_size ?? "—"} · ${disc.size_bytes ? `${(disc.size_bytes / 1e9).toFixed(2)} GB` : "—"}`} />
              <Field k="GPU offload" v={disc.gpu_offload_supported === null ? "unknown" : disc.gpu_offload_supported ? "supported" : "CPU only"} />
              <Field k="Model load time" v={ms(d.load.model_load_ms)} />
              <Field k="External fallback" v={st.external_fallback ? "yes" : "none (by design)"} />
            </div>
            {!st.available && (
              <div className={`mt-3 rounded-xl border p-3 text-xs ${st.required ? "border-neg/30 bg-neg/[0.06]" : "border-warn/30 bg-warn/[0.05]"}`}>
                <p className="font-medium">{st.required ? "Local Qwen is required but could not be reached" : "Why Qwen isn't connected"}</p>
                <p className="muted mt-1">{disc.reason}</p>
                <p className="muted mt-2">Searched: {disc.searched.join(" · ")}</p>
                {disc.candidates.length > 0 && <p className="mt-1">Candidates found: {disc.candidates.map((c) => String(c.path ?? c.name)).join(", ")}</p>}
                <p className="mt-2"><b>Fix:</b> run <code>sh scripts/setup.sh</code> (installs the llama.cpp runtime; your model is reused), or set <code>FF_QWEN_MODEL_PATH=/path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf</code>, or start Ollama with your Qwen model. Then click Re-detect.</p>
              </div>
            )}
            {test.data && <p className="mt-3 text-xs" role="status">Live test: “{String(test.data.data.text).slice(0, 200)}” · {String(test.data.data.latency_ms)} ms · {String(test.data.data.tokens_per_s)} tok/s</p>}
            {test.error ? <div className="mt-3"><ErrorBox error={test.error} /></div> : null}
            {bench.data && <p className="mt-2 text-xs" role="status">Benchmark: p50 {String((bench.data.data.latency_ms as Record<string, unknown>).p50)} ms · p95 {String((bench.data.data.latency_ms as Record<string, unknown>).p95)} ms · TTFT p50 {String((bench.data.data.first_token_ms as Record<string, unknown>).p50)} ms · {String((bench.data.data.tokens_per_s as Record<string, unknown>).mean)} tok/s ({String(bench.data.data.ok)}/{String(bench.data.data.runs)} ok)</p>}
            {bench.error ? <div className="mt-3"><ErrorBox error={bench.error} /></div> : null}
          </Card>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8" data-testid="qwen-kpis">
            <Kpi label="Inference calls" value={d.calls} hint={`${d.live_calls} live · ${d.cached_calls} cached`} />
            <Kpi label="Latency p50" value={ms(d.latency_ms.p50)} />
            <Kpi label="Latency p95" value={ms(d.latency_ms.p95)} />
            <Kpi label="Time to first token p50" value={ms(d.first_token_ms.p50)} />
            <Kpi label="Tokens / s (mean)" value={d.tokens_per_s.mean ?? "—"} />
            <Kpi label="Cache hit rate" value={pct(d.cache_hit_rate)} />
            <Kpi label="Model errors" value={d.errors} tone={d.errors ? "amber" : "teal"} />
            <Kpi label="Tokens (prompt + completion)" value={`${d.prompt_tokens.toLocaleString()} + ${d.completion_tokens.toLocaleString()}`} />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="System resources" subtitle="Measured from the OS at request time">
              <div className="grid grid-cols-2 gap-3">
                <Kpi label="CPU cores" value={d.system.cpu_count} />
                <Kpi label="CPU load" value={d.system.cpu_load_pct !== undefined ? `${d.system.cpu_load_pct}%` : "—"} />
                <Kpi label="Process memory" value={d.system.process_rss_mb ? `${d.system.process_rss_mb} MB` : "—"} />
                <Kpi label="System memory free" value={d.system.system_mem_available_mb ? `${d.system.system_mem_available_mb.toLocaleString()} MB` : "—"} />
                <div className="col-span-2"><Kpi label="GPU" value={d.system.gpu.available ? `${d.system.gpu.name} · ${d.system.gpu.utilization_pct}%` : "not measured"} hint={d.system.gpu.detail} /></div>
              </div>
            </Card>
            <Card title="Inference latency (recent calls)" subtitle="Live (uncached) calls, ms" className="xl:col-span-2">
              {d.recent.length ? (
                <Chart title="Inference latency" spec={{ kind: "line", x: d.recent.map((r) => String(r.ts).slice(11, 19)), series: [{ name: "Latency ms", data: d.recent.map((r) => (r.cached ? null : (r.latency_ms as number))) }, { name: "First token ms", data: d.recent.map((r) => (r.first_token_ms as number) ?? null) }] }} height={240} />
              ) : <p className="muted p-6 text-center text-xs">No inference calls recorded yet{st.available ? ". Ask a question or run the live test." : ": Qwen isn't connected on this machine."}</p>}
            </Card>
          </div>

          <Card title="Agent-level inference usage" subtitle="Which agents use the governed gateway, and how much">
            {d.by_agent.length ? (
              <div className="grid gap-4 xl:grid-cols-2">
                <Chart title="Calls per agent" spec={{ kind: "bar", x: d.by_agent.map((a) => a.agent), series: [{ name: "Calls", data: d.by_agent.map((a) => a.calls) }, { name: "Cached", data: d.by_agent.map((a) => a.cached) }, { name: "Errors", data: d.by_agent.map((a) => a.errors) }] }} height={240} />
                <DataTable label="Agent usage" maxHeight={240} columns={[{ key: "agent", label: "Agent" }, { key: "calls", label: "Calls" }, { key: "cached", label: "Cached" }, { key: "errors", label: "Errors" }, { key: "prompt_tokens", label: "Prompt tok" }, { key: "completion_tokens", label: "Completion tok" }, { key: "p50_ms", label: "p50 ms" }]} rows={d.by_agent} />
              </div>
            ) : <p className="muted text-xs">No agent has called the model yet.</p>}
          </Card>
        </>
      )}

      {w.data && (
        <Card title="Workflow & agent reliability" subtitle="From persisted workflow events, tool invocations, policy decisions and approvals">
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <Kpi label="Workflow runs" value={w.data.runs} />
            <Kpi label="Success rate" value={pct(w.data.success_rate)} tone="teal" />
            <Kpi label="Workflow p50" value={ms(w.data.workflow_ms.p50)} />
            <Kpi label="Workflow p95" value={ms(w.data.workflow_ms.p95)} />
            <Kpi label="Schema failures" value={w.data.schema_failures} />
            <Kpi label="Qwen explanations" value={w.data.challenger.explanations} hint={`${w.data.challenger.rejected} rejected by the Challenger`} />
            <Kpi label="Unsupported items caught" value={w.data.challenger.unsupported_items} />
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart title="Agent step duration" spec={{ kind: "bar", x: w.data.by_agent.map((a) => a.agent), series: [{ name: "p50 ms", data: w.data.by_agent.map((a) => a.p50_ms) }, { name: "p95 ms", data: w.data.by_agent.map((a) => a.p95_ms) }] }} height={260} />
            <Chart title="Routing methods" spec={{ kind: "pie", x: Object.keys(w.data.route_methods), series: [{ name: "Runs", data: Object.values(w.data.route_methods) }] }} height={260} />
          </div>
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <DataTable label="Agents" maxHeight={260} columns={[{ key: "agent", label: "Agent" }, { key: "steps", label: "Steps" }, { key: "failed", label: "Failed" }, { key: "retries", label: "Retries" }, { key: "skipped", label: "Skipped" }]} rows={w.data.by_agent} />
            <DataTable label="Tools" maxHeight={260} columns={[{ key: "tool", label: "Tool" }, { key: "status", label: "Status" }, { key: "n", label: "Calls" }]} rows={w.data.tools} />
            <DataTable label="Policy" maxHeight={260} columns={[{ key: "policy_id", label: "Policy" }, { key: "decision", label: "Decision" }, { key: "n", label: "Count" }]} rows={w.data.policy} />
          </div>
        </Card>
      )}

      <Card title="Four-question evaluation (measured)" subtitle="From docs/eval/*.json written by scripts/eval_four_questions.py. Held-out splits were never used for tuning.">
        {ev.isLoading ? <Loading /> : ev.data && ev.data.length ? (
          <div className="space-y-4" data-testid="eval-results">
            <DataTable label="Evaluation runs" columns={[{ key: "file", label: "Run" }, { key: "items", label: "Items" }, { key: "routing_accuracy", label: "Routing acc.", render: (r) => pct(r.routing_accuracy as number) },
              { key: "macro_f1", label: "Macro-F1" }, { key: "four_family_routing_accuracy", label: "4-family acc.", render: (r) => pct(r.four_family_routing_accuracy as number) },
              { key: "follow_up_accuracy", label: "Follow-up", render: (r) => pct(r.follow_up_accuracy as number) }, { key: "workflow_correctness", label: "Workflow", render: (r) => pct(r.workflow_correctness as number) },
              { key: "evidence_accuracy", label: "Evidence", render: (r) => pct(r.evidence_accuracy as number) }, { key: "unsupported_claim_rate", label: "Unsupported claims", render: (r) => (r.unsupported_claim_rate === null ? "not measured (no Qwen)" : pct(r.unsupported_claim_rate as number)) },
              { key: "answer_completeness", label: "Completeness", render: (r) => pct(r.answer_completeness as number) }, { key: "qwen", label: "Qwen used", render: (r) => ((r.qwen as Ev["qwen"]).available ? (r.qwen as Ev["qwen"]).model ?? "yes" : "no") }]} rows={ev.data as unknown as Record<string, unknown>[]} />
            <Chart title="Routing accuracy by run" spec={{ kind: "bar", x: ev.data.map((e) => e.file.replace("four_questions_", "").replace(".json", "")), series: [{ name: "Routing accuracy", data: ev.data.map((e) => +(e.routing_accuracy * 100).toFixed(1)) }, { name: "Macro-F1 ×100", data: ev.data.map((e) => +(e.macro_f1 * 100).toFixed(1)) }], markLine: { y: 95, label: "95% target" } }} height={240} />
          </div>
        ) : <p className="muted text-xs">No evaluation results yet. Run scripts/eval_four_questions.py.</p>}
      </Card>
      <p className="text-[11px] text-faint">Telemetry is stored locally in SQLite (llm_calls); no external telemetry service is used. Measured {d ? datetime(new Date().toISOString()) : ""}.</p>
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return <div className="rounded-xl border border-token bg-white/[0.02] p-3"><p className="label">{k}</p><p className="mt-1 break-all text-sm">{v}</p></div>;
}
