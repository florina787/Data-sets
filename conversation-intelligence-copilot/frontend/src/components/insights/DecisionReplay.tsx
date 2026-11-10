import { ChevronDown, Database, History, Pause, Play, Search, SkipBack, SkipForward, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, ErrorState, Skeleton } from "@/components/common/ui";
import { humanize, ms } from "@/lib/format";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import { tokenText } from "./RoutingStrip";

interface Step { node: string; label: string; role: string; engine: string; status: string; duration_ms: number | null; output: Record<string, any>; meta: Record<string, any>; error: string | null }
interface Replay {
  request_id: string; question: string; latency_ms: number; routing: any; token_usage: any;
  decisions: { at: string; decision: string; why: string }[]; steps: Step[];
  operations: { op: string; engine: string; params: Record<string, any>; status: string; duration_ms: number; rows?: number; error?: string }[];
  retrieval: { engine: string; mode: string; methods: Record<string, string>; fusion: string; k: number; filters: Record<string, any>; returned: number; latency_ms: number; query: string }[];
  llm_calls: { purpose: string; prompt: string; model: string; total_tokens: number | null; tokens_reported: boolean; latency_ms: number; cache_hit: boolean; status: string }[];
  qa: { status: string; passed: number; total: number }; evidence_review: { verdict: string; challenges: string[] } | null;
  counts: Record<string, number>; sanitisation: string;
}

const STATUS_DOT: Record<string, string> = { completed: "bg-pos", failed: "bg-neg", skipped: "bg-faint" };

function Summary({ value }: { value: Record<string, any> }) {
  const entries = Object.entries(value ?? {}).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length));
  if (!entries.length) return <p className="text-faint">No output summary.</p>;
  return (
    <dl className="grid gap-x-3 gap-y-1 sm:grid-cols-[max-content_1fr]">
      {entries.map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-faint">{humanize(k)}</dt>
          <dd className="break-words font-mono text-[11px] text-ink/85">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>
      ))}
    </dl>
  );
}

/** AI Decision Replay: how this answer was produced, from what was recorded while it ran (nothing is re-executed). */
export function DecisionReplay({ requestId }: { requestId: string }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Replay | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cur, setCur] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!open || data) return;
    api.get<Replay>(`/api/replay/${requestId}`).then(setData).catch((e) => setErr((e as Error).message));
  }, [open, data, requestId]);
  useEffect(() => {
    if (!playing || !data) return;
    const t = setInterval(() => setCur((c) => { if (c >= data.steps.length - 1) { setPlaying(false); return c; } return c + 1; }), 900);
    return () => clearInterval(t);
  }, [playing, data]);
  const step = data?.steps[cur];
  return (
    <section className="rounded-xl border border-line bg-white/[0.02]" data-testid="decision-replay">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="focus-ring flex w-full items-center gap-2 rounded-xl px-4 py-3 text-left text-sm font-semibold">
        <History className="h-4 w-4 text-cyan" />AI decision replay
        <span className="text-xs font-normal text-faint">routing, every step, DuckDB and FAISS operations, model calls and checks</span>
        <ChevronDown className={cn("ml-auto h-4 w-4 text-faint transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-4 px-4 pb-4">
          {err ? <ErrorState message={err} /> : !data ? <Skeleton className="h-40" /> : (
            <>
              <div className="flex flex-wrap gap-1.5 text-[11px]">
                <Badge tone={data.routing?.route === "analytics_only" ? "positive" : "violet"}>{data.routing?.route === "analytics_only" ? "Zero-LLM route" : "Hybrid AI route"}</Badge>
                <Badge>{data.counts.nodes} steps</Badge><Badge><Database className="h-3 w-3" />{data.counts.duckdb_operations} DuckDB ops</Badge>
                <Badge><Search className="h-3 w-3" />{data.counts.faiss_searches} FAISS searches</Badge>
                <Badge><Sparkles className="h-3 w-3" />{data.counts.llm_calls} model calls</Badge>
                <Badge>tokens {tokenText(data.token_usage?.total_tokens, data.token_usage?.model_calls)}</Badge>
                <Badge>{ms(data.latency_ms)}</Badge><Badge tone={data.qa.status === "pass" ? "positive" : "warning"}>QA {data.qa.passed}/{data.qa.total}</Badge>
              </div>
              <ol className="space-y-1.5 text-xs" aria-label="Key decisions">
                {data.decisions.map((d) => (
                  <li key={d.at} className="flex gap-2"><span className="w-20 shrink-0 font-mono text-[10px] uppercase text-faint">{d.at}</span>
                    <span><span className="text-ink">{d.decision}</span>{d.why && <span className="text-muted"> — {d.why}</span>}</span></li>
                ))}
              </ol>
              <div className="grid gap-3 lg:grid-cols-[260px_1fr]">
                <div>
                  <div className="mb-2 flex items-center gap-1">
                    <Button size="icon" variant="ghost" aria-label="Previous step" onClick={() => setCur((c) => Math.max(0, c - 1))}><SkipBack className="h-3.5 w-3.5" /></Button>
                    <Button size="icon" variant="ghost" aria-label={playing ? "Pause replay" : "Play replay"} onClick={() => { if (cur >= data.steps.length - 1) setCur(0); setPlaying((p) => !p); }}>
                      {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}</Button>
                    <Button size="icon" variant="ghost" aria-label="Next step" onClick={() => setCur((c) => Math.min(data.steps.length - 1, c + 1))}><SkipForward className="h-3.5 w-3.5" /></Button>
                    <span className="ml-1 text-[11px] text-faint">step {cur + 1} / {data.steps.length}</span>
                  </div>
                  <ol className="space-y-0.5" aria-label="Execution steps">
                    {data.steps.map((s, i) => (
                      <li key={`${s.node}-${i}`}>
                        <button onClick={() => { setCur(i); setPlaying(false); }} aria-current={i === cur} data-testid={`replay-step-${s.node}`}
                          className={cn("focus-ring flex w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-xs transition", i === cur ? "bg-indigo/15 text-ink" : i < cur ? "text-muted" : "text-faint")}>
                          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[s.status] ?? "bg-warn")} />
                          <span className="flex-1 truncate">{s.label}</span><span className="font-mono text-[10px]">{ms(s.duration_ms)}</span>
                        </button>
                      </li>
                    ))}
                  </ol>
                </div>
                {step && (
                  <div className="rounded-lg border border-line p-3 text-xs" aria-live="polite">
                    <p className="font-semibold text-ink">{step.label} <span className="font-normal text-faint">· {step.engine} · {humanize(step.status)} · {ms(step.duration_ms)}</span></p>
                    <p className="mb-2 mt-0.5 text-muted">{step.role}</p>
                    {step.error && <p className="mb-2 text-neg">{step.error}</p>}
                    <Summary value={step.output} />
                  </div>
                )}
              </div>
              {data.operations.length > 0 && (
                <div><p className="label mb-1">DuckDB operations (registered, parameterised; no model-written SQL)</p>
                  <ul className="space-y-1 text-xs">{data.operations.map((o, i) => (
                    <li key={i} className="flex flex-wrap gap-x-2 rounded-lg border border-line px-2.5 py-1.5"><span className="font-mono text-cyan">{o.op}</span>
                      <span className="text-muted">{JSON.stringify(o.params)}</span><span className="ml-auto text-faint">{o.rows ?? 0} rows · {ms(o.duration_ms)} · {o.status}</span></li>))}</ul></div>
              )}
              {data.retrieval.map((rt, i) => (
                <div key={i}><p className="label mb-1">FAISS search</p>
                  <p className="text-xs text-muted">Mode <span className="text-ink">{rt.mode}</span> · {Object.values(rt.methods ?? {}).join(" + ")} · {rt.fusion} · k={rt.k} · {rt.returned} returned · {ms(rt.latency_ms)}</p>
                  <p className="mt-0.5 text-[11px] text-faint">Query: “{rt.query}” · filters {JSON.stringify(rt.filters)}</p></div>
              ))}
              <div><p className="label mb-1">Model calls</p>
                {data.llm_calls.length ? (
                  <ul className="space-y-1 text-xs">{data.llm_calls.map((c, i) => (
                    <li key={i} className="flex flex-wrap gap-x-2 rounded-lg border border-line px-2.5 py-1.5"><span className="text-ink">{c.purpose}</span><span className="font-mono text-muted">{c.prompt}</span>
                      <span className="text-muted">{c.model}</span><span className="ml-auto text-faint">{c.cache_hit ? "cache hit" : c.tokens_reported ? `${c.total_tokens} tokens` : "tokens not reported"} · {ms(c.latency_ms)} · {c.status}</span></li>))}</ul>
                ) : <p className="text-xs text-faint">None — this answer was produced without a model.</p>}
              </div>
              <p className="text-[10px] text-faint">{data.sanitisation}</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
