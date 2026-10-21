import { useEffect, useMemo, useState } from "react";
import { api, sessionHeaders } from "../lib/api";
import { useApp } from "../lib/state";
import { fmtDate, fmtInt, fmtPct } from "../lib/format";
import { Badge, Button, Card, Empty, ErrorBox, Notice, PageHeader, Spinner, Table } from "../components/ui";

function TraceLink({ requestId }: { requestId: string }) {
  const [r, setR] = useState<any>(null);
  return r ? (r.available ? <a className="text-teal underline" href={r.url} target="_blank" rel="noreferrer noopener">Open trace</a> : <span className="text-[11px] text-muted">{r.reason}</span>)
    : <Button size="sm" variant="ghost" onClick={async () => setR(await api(`/api/flo/runs/${requestId}/trace-link`, { headers: await sessionHeaders() }))}>Trace link</Button>;
}

export function Observability() {
  const { status, refreshStatus, dataset, mode } = useApp();
  const [sum, setSum] = useState<any>(null);
  const [runs, setRuns] = useState<any[] | null>(null);
  const [evals, setEvals] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = async () => {
    refreshStatus();
    api("/api/observability/summary").then(setSum).catch((e) => setErr(e.message));
    api<any>("/api/observability/evals").then(setEvals).catch(() => undefined);
    const h = await sessionHeaders().catch(() => null);
    if (h) api<any>("/api/flo/runs", { headers: h }).then((r) => setRuns(r.runs)).catch(() => setRuns([]));
  };
  useEffect(() => { load(); }, []);
  const groups = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const r of evals?.results ?? []) (g[r.suite] ??= []).push(r);
    return g;
  }, [evals]);
  const runEvals = async () => {
    setRunning(true); setErr(null);
    try {
      await api("/api/observability/evals/run", { method: "POST", params: { system: mode === "demo" ? "rules" : "llm", dataset_id: dataset?.id } });
      await load();
    } catch (e: any) { setErr(e.message); } finally { setRunning(false); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Observability and evaluation" description="Actual execution summary from this server, evaluation results by language, and authorised links to LangSmith traces." />
      {err && <ErrorBox>{err}</ErrorBox>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Model provider">
          {!status ? <Spinner /> : <div className="space-y-1 text-sm"><div>Provider: <strong>{status.model.provider}</strong></div><div>{status.model.configured ? <Badge tone="green">configured · {status.model.model_id}</Badge> : <Badge tone="amber">not configured</Badge>}</div><div className="text-xs text-muted">Credentials stay on the backend. Demonstration mode never calls a model.</div></div>}
        </Card>
        <Card title="LangSmith">
          {!status ? <Spinner /> : status.langsmith.configured ? <div className="text-sm"><Badge tone="green">{status.langsmith.label}</Badge><div className="mt-1 text-xs text-muted">Project {status.langsmith.project}. {status.langsmith.redaction}</div></div>
            : <div className="text-sm"><Badge tone="amber">LangSmith not configured</Badge><div className="mt-1 text-xs text-muted">Set {status.langsmith.missing?.join(" and ")} on the backend to enable tracing. The application works without it.</div></div>}
        </Card>
        <Card title="Retrieval">
          {!status ? <Spinner /> : <div className="text-sm">Keyword (BM25): <Badge tone="green">available</Badge><div className="mt-1">Semantic (sentence-transformers + FAISS): {status.retrieval.available ? <Badge tone="green">{status.retrieval.model}</Badge> : <Badge tone="amber">{status.retrieval.available === null ? "not loaded yet" : "unavailable"}</Badge>}</div>{status.retrieval.reason && <div className="mt-1 text-xs text-muted">{status.retrieval.reason}</div>}</div>}
        </Card>
      </div>
      <Card title="Execution summary (all sessions on this server)" actions={<Button size="sm" onClick={load}>Refresh</Button>}>
        {!sum ? <Spinner /> : !sum.runs.length ? <Empty title="No Flo runs yet" /> : (
          <div className="grid gap-4 lg:grid-cols-2">
            <Table head={["Mode", "Status", "Runs", "Avg latency", "Input tokens", "Output tokens"]} rows={sum.runs.map((r: any) => [r.mode, r.status, r.count, `${fmtInt(r.avg_latency_ms)} ms`, fmtInt(r.input_tokens), fmtInt(r.output_tokens)])} />
            <Table head={["Tool", "Calls", "Errors"]} rows={sum.tools.map((t: any) => [<code key="t" className="text-xs">{t.tool}</code>, t.calls, t.errors])} />
            <Table head={["Model", "Prompt versions", "Runs"]} rows={sum.models.map((m: any) => [m.model_id, Object.entries(m.prompt_versions ?? {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "rules", m.runs])} />
            <div className="text-xs text-muted"><div>Feedback: {fmtInt(sum.feedback.helpful ?? 0)} helpful · {fmtInt(sum.feedback.not_helpful ?? 0)} not helpful</div><div className="mt-1">{sum.cost}</div></div>
          </div>
        )}
      </Card>
      <Card title="Graph runs in this session">
        {!runs ? <Spinner /> : !runs.length ? <Empty title="No runs in this session" /> : (
          <Table head={["Started", "Question", "Type", "Mode", "Status", "Tools", "Latency", "Tokens in/out", "Trace"]}
            rows={runs.map((r) => [fmtDate(r.started_at, { timeStyle: "short", dateStyle: "short" } as any), <span key="q" className="line-clamp-1 max-w-xs">{r.question}</span>, r.question_type ?? "–", r.mode,
              <Badge key="s" tone={r.status === "completed" ? "green" : r.status === "failed" ? "red" : "amber"}>{r.status}</Badge>, r.tool_count, `${fmtInt(r.latency_ms)} ms`, `${r.input_tokens}/${r.output_tokens}`,
              r.langsmith_run_id ? <TraceLink key="t" requestId={r.request_id} /> : <span key="t" className="text-[11px] text-muted">not traced</span>])} />
        )}
      </Card>
      <Card title="Evaluation results" subtitle="Reported per suite and language with sample sizes. Deterministic checks, human judgments and LLM-judge scores are kept separate."
        actions={<Button size="sm" variant="primary" disabled={running || !dataset} onClick={runEvals}>{running ? "Running…" : mode === "demo" ? "Run deterministic evaluations (rules system)" : "Run evaluations (configured model)"}</Button>}>
        <Notice tone="neutral">Demonstration evaluations measure the rules system against synthetic reference labels. They say nothing about model quality on real data. CLI: <code>{evals?.commands?.demo}</code> · connected: <code>{evals?.commands?.connected}</code></Notice>
        {!evals ? <Spinner /> : !evals.results.length ? <div className="mt-3"><Empty title="No evaluation has been run">Results appear only after an evaluation actually runs.</Empty></div> : (
          <div className="mt-3 space-y-4">
            {Object.entries(groups).map(([suite, rows]) => (
              <div key={suite}>
                <div className="mb-1 text-sm font-semibold">{suite.replace(/_/g, " ")}</div>
                <Table head={["Language", "Judgment", "System", "n", "Passed", "Score", "Run", "LangSmith experiment"]}
                  rows={rows.sort((a, b) => a.language.localeCompare(b.language)).map((r) => [r.language, <Badge key="j" tone={r.judgment === "deterministic" ? "teal" : r.judgment === "human" ? "green" : "amber"}>{r.judgment === "llm_judge" ? "LLM-judge (not ground truth)" : r.judgment}</Badge>,
                    r.system, r.n, r.passed, <span key="s" className={r.n < 5 ? "text-muted" : ""}>{fmtPct(r.score)}{r.n < 5 ? " (small n)" : ""}</span>, fmtDate(r.created_at), r.langsmith_experiment ?? "–"])} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
