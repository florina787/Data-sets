import { CheckCircle2, CircleSlash, ClipboardCheck, RotateCw, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useApp } from "@/app/AppState";
import { DataTable } from "@/components/charts/ChartRenderer";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton, Stat } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { humanize, pct, timeAgo } from "@/lib/format";
import { api } from "@/services/api";

function HumanReview() {
  const [reviewer, setReviewer] = useState(() => { try { return localStorage.getItem("cic.reviewer") ?? ""; } catch { return ""; } });
  const [started, setStarted] = useState(false);
  const [idx, setIdx] = useState(0);
  const sample = useAsync(() => (started ? api.get<{ labels: string[]; items: any[] }>(`/api/review/sample?reviewer=${encodeURIComponent(reviewer)}&n=10`) : Promise.resolve(null)), [started, reviewer]);
  const metrics = useAsync(() => api.get<any>("/api/review/metrics"), [idx]);
  const item = sample.data?.items[idx];
  const submit = async (sentiment: string) => {
    await api.post("/api/review/labels", { message_id: item.message_id, reviewer, sentiment });
    setIdx((i) => i + 1);
  };
  return (
    <Card>
      <CardHeader title="Human review (blind)" icon={<ClipboardCheck className="h-4 w-4" />}
        subtitle="Label sampled messages without seeing the system's label. Agreement metrics are computed only from labels people submit." />
      <div className="grid gap-5 p-5 pt-3 lg:grid-cols-2">
        <div>
          {!started ? (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (reviewer.trim()) { try { localStorage.setItem("cic.reviewer", reviewer); } catch { /* ignore */ } setStarted(true); } }}>
              <label htmlFor="rv" className="sr-only">Reviewer name</label>
              <input id="rv" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your reviewer name" maxLength={40}
                className="focus-ring flex-1 rounded-xl border border-line bg-surface px-3 py-2 text-sm" />
              <Button variant="primary" disabled={!reviewer.trim()}>Start reviewing</Button>
            </form>
          ) : sample.loading ? <Skeleton className="h-40" /> : !item ? <EmptyState title="Sample complete" description="Thanks — your labels are included in the metrics." action={<Button size="sm" onClick={() => { setIdx(0); sample.reload(); }}>Load more</Button>} /> : (
            <div className="space-y-3">
              <p className="text-[11px] text-faint">Item {idx + 1} of {sample.data!.items.length} · {item.message_id} · {item.speaker_role} message</p>
              <blockquote className="rounded-xl border border-line bg-white/[0.03] p-4 text-sm text-ink">“{item.text}”</blockquote>
              <p className="text-xs text-muted">What sentiment does the {item.speaker_role} express?</p>
              <div className="flex flex-wrap gap-2">{sample.data!.labels.map((l) => <Button key={l} size="sm" variant="outline" onClick={() => submit(l)}>{l}</Button>)}</div>
            </div>
          )}
        </div>
        <div>
          {metrics.loading ? <Skeleton className="h-40" /> : metrics.data?.status !== "ok" ? <EmptyState title="No human labels yet" description={metrics.data?.note} /> : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <Stat label="Reviews" value={metrics.data.reviews} hint={`${metrics.data.reviewers} reviewer(s)`} />
                <Stat label="Accuracy" value={pct(metrics.data.accuracy)} />
                <Stat label="Cohen's κ" value={metrics.data.cohen_kappa_vs_system ?? "—"} />
              </div>
              <DataTable rows={metrics.data.per_class} />
              {metrics.data.inter_annotator && <p className="text-xs text-muted">Inter-annotator: {pct(metrics.data.inter_annotator.percent_agreement)} agreement, κ {metrics.data.inter_annotator.cohen_kappa} over {metrics.data.inter_annotator.items} items.</p>}
              <p className="text-[11px] text-faint">{metrics.data.note}</p>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function Governance() {
  const { refreshModel } = useApp();
  const { data, error, loading, reload } = useAsync(() => api.get<any>("/api/governance/status"), []);
  const audit = useAsync(() => api.get<any[]>("/api/governance/audit?limit=60"), []);
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <PageHeader title="Governance" icon={<ShieldCheck className="h-5 w-5" />} subtitle="Controls actually enforced in this prototype, their status, the audit trail and human review." />
      {loading || !data ? <Skeleton className="h-96" /> : (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <Card><CardHeader title="Controls" subtitle="Status reflects the running code; not-implemented items are listed honestly." />
              <ul className="divide-y divide-line px-5 pb-3">
                {data.controls.map((c: any) => (
                  <li key={c.id} className="flex items-start gap-3 py-3">
                    {c.status === "implemented" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-pos" /> : <CircleSlash className="mt-0.5 h-4 w-4 shrink-0 text-warn" />}
                    <div className="min-w-0 flex-1"><p className="text-sm text-ink"><span className="mr-2 font-mono text-[11px] text-faint">{c.id}</span>{c.name}</p>
                      <p className="mt-0.5 text-xs text-muted">{c.detail}</p></div>
                    <Badge tone={c.status === "implemented" ? "positive" : "warning"}>{humanize(c.status)}</Badge>
                  </li>
                ))}
              </ul></Card>
            <div className="space-y-4">
              <Card><CardHeader title="Model availability" actions={<Button size="sm" variant="outline" onClick={async () => { await api.post("/api/model/retry", {}); refreshModel(); reload(); }}><RotateCw className="h-3.5 w-3.5" />Retry model</Button>} />
                <div className="space-y-1.5 p-5 pt-3 text-xs">
                  <p><Badge tone={data.model.available ? "positive" : "warning"}>{data.model.available ? "available" : "unavailable"}</Badge> <span className="ml-1 text-muted">{data.model.model} · circuit {data.model.circuit}</span></p>
                  {data.model.reason && <p className="break-words text-muted">{String(data.model.reason).slice(0, 300)}</p>}
                  <p className="text-faint">When unavailable, analytics, retrieval and memory still work; answers use the deterministic explainer and say so.</p>
                </div></Card>
              <Card><CardHeader title="Audit summary" />
                <div className="p-4"><DataTable rows={data.audit_summary} /></div></Card>
            </div>
          </div>
          <HumanReview />
          <Card><CardHeader title="Audit log" subtitle="Most recent first" />
            <div className="p-4">{audit.loading ? <Skeleton className="h-40" /> : !audit.data?.length ? <EmptyState title="No audit events yet" /> :
              <DataTable rows={audit.data.map((a) => ({ when: timeAgo(a.created_at), category: a.category, action: a.action, request: a.request_id, detail: JSON.stringify(a.detail).slice(0, 160) }))} />}</div></Card>
        </>
      )}
    </div>
  );
}
