import { BookText, FlaskConical } from "lucide-react";
import { useState } from "react";
import { Badge, Card, CardHeader, ErrorState, PageHeader, Skeleton } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { ms, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

export default function Prompts() {
  const { data, error, loading, reload } = useAsync(() => api.get<{ statuses: string[]; prompts: any[] }>("/api/prompts"), []);
  const [sel, setSel] = useState(0);
  const p = data?.prompts[sel];
  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader title="Prompt Library" icon={<BookText className="h-5 w-5" />}
        subtitle="Versioned prompts with schemas, model configuration, test cases, live usage and evaluation results. Lifecycle changes are made by pull request." />
      {error ? <ErrorState message={error.message} onRetry={reload} /> : loading || !data ? <Skeleton className="h-96" /> : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1 pb-1">{data.statuses.map((s) => <Badge key={s} tone={s === "active" ? "positive" : "default"}>{s}</Badge>)}</div>
            {data.prompts.map((x, i) => (
              <button key={`${x.id}@${x.version}`} onClick={() => setSel(i)} className={cn("focus-ring w-full rounded-xl border p-3 text-left transition", i === sel ? "border-indigo/50 bg-indigo/10" : "border-line bg-surface/60 hover:border-indigo/30")}>
                <div className="flex items-center justify-between"><p className="text-sm font-medium">{x.name}</p><Badge tone={x.status === "active" ? "positive" : "default"}>{x.status}</Badge></div>
                <p className="mt-1 font-mono text-[11px] text-faint">{x.id}@{x.version}</p>
                <p className="mt-1 text-[11px] text-muted">{x.usage ? `${x.usage.calls} calls · ${x.usage.ok} ok · ${x.usage.cache_hits} cached` : "No calls recorded yet"}</p>
              </button>
            ))}
          </div>
          {p && (
            <div className="space-y-4">
              <Card>
                <CardHeader title={`${p.name} · v${p.version}`} subtitle={p.purpose} />
                <div className="grid gap-3 p-5 pt-3 text-xs sm:grid-cols-4">
                  {[["Owner", p.owner], ["Created", p.created_at], ["Output schema", p.output_schema ?? "text"], ["Model config", JSON.stringify(p.model_config)]].map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-line p-2.5"><p className="label">{k}</p><p className="mt-1 break-words text-ink">{v}</p></div>
                  ))}
                </div>
              </Card>
              <Card><CardHeader title="System instruction" />
                <pre className="m-5 mt-3 whitespace-pre-wrap rounded-xl border border-line bg-bg/60 p-4 font-mono text-[12px] leading-relaxed text-ink/85">{p.system}</pre></Card>
              <Card><CardHeader title="User template" subtitle={`Variables: ${p.input_variables.join(", ")}`} />
                <pre className="m-5 mt-3 whitespace-pre-wrap rounded-xl border border-line bg-bg/60 p-4 font-mono text-[12px] text-ink/85">{p.user_template}</pre></Card>
              <div className="grid gap-4 xl:grid-cols-2">
                <Card><CardHeader title="Test cases" icon={<FlaskConical className="h-4 w-4" />} />
                  <ul className="space-y-2 p-5 pt-3 text-xs">{p.test_cases.map((t: any, i: number) => (
                    <li key={i} className="rounded-lg border border-line p-2.5"><p className="text-ink">{typeof t.input === "string" ? t.input : JSON.stringify(t.input)}</p>
                      <p className="mt-1 font-mono text-[11px] text-cyan">expect {JSON.stringify(t.expect)}</p></li>))}</ul></Card>
                <Card><CardHeader title="Evaluation & usage" />
                  <div className="space-y-2 p-5 pt-3 text-xs">
                    {p.usage ? <p className="text-muted">{p.usage.calls} calls, {p.usage.ok} succeeded, avg {ms(p.usage.avg_ms)}, {p.usage.tokens ?? 0} tokens.</p>
                      : <p className="text-muted">No live calls recorded: Gemini has not been reachable from this deployment.</p>}
                    {p.evaluation ? <pre className="whitespace-pre-wrap rounded-lg border border-line bg-bg/60 p-2.5 font-mono text-[11px] text-ink/80">{JSON.stringify(p.evaluation, null, 2)}</pre>
                      : <p className="text-faint">No evaluation run recorded for this prompt.</p>}
                    {p.evaluation?.schema_validity !== undefined && <p>Schema validity {pct(p.evaluation.schema_validity)}</p>}
                  </div></Card>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
