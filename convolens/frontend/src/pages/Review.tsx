import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { api, dsPath } from "../lib/api";
import { useApp } from "../lib/state";
import { fmtPct } from "../lib/format";
import { Badge, Button, Card, Empty, ErrorBox, Field, Notice, PageHeader, Spinner, Table, inputCls } from "../components/ui";

const FIELD_LABELS: Record<string, string> = {
  primary_topic: "Primary topic", resolution_status: "Resolution", sentiment_start: "Starting sentiment",
  sentiment_end: "Ending sentiment", escalation_requested: "Escalation requested",
};
type Option = { key: string; label: string };
type Next = { reviewed: number; target: number; options: Record<string, Option[]>;
  item: null | { conversation_key: string; brand: string | null; customer_turns: number; messages: { message_id: string; role: string; text: string; language: string }[] } };

export function Review() {
  const { dataset } = useApp();
  const [next, setNext] = useState<Next | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [reviewer, setReviewer] = useState(() => { try { return localStorage.getItem("convolens.reviewer") ?? ""; } catch { return ""; } });
  const [reveal, setReveal] = useState<any>(null);
  const [acc, setAcc] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!dataset) return;
    setErr(null); setLabels({}); setReveal(null);
    api<Next>(dsPath(dataset.id, "review/next")).then(setNext).catch((e) => setErr(e.message));
    api<any>(dsPath(dataset.id, "review/accuracy")).then(setAcc).catch(() => undefined);
  };
  useEffect(load, [dataset?.id]);

  const fields = Object.keys(FIELD_LABELS);
  const complete = fields.every((f) => labels[f]) && reviewer.trim();
  const submit = async () => {
    if (!dataset || !next?.item) return;
    setSaving(true); setErr(null);
    try {
      try { localStorage.setItem("convolens.reviewer", reviewer.trim()); } catch { /* storage unavailable */ }
      setReveal(await api<any>(dsPath(dataset.id, `review/${next.item.conversation_key}`), { body: { reviewer: reviewer.trim(), labels } }));
      api<any>(dsPath(dataset.id, "review/accuracy")).then(setAcc).catch(() => undefined);
    } catch (e: any) { setErr(e.message); } finally { setSaving(false); }
  };

  if (!dataset) return <Spinner />;
  const item = next?.item;
  return (
    <div className="space-y-4">
      <PageHeader title="Human review"
        description="Label conversations blind, then see how the rules and the model labelled the same one. Reviewed conversations become the gold set every labelling system is scored against." />
      {err && <ErrorBox onRetry={load}>{err}</ErrorBox>}
      {next && (
        <div className="flex items-center gap-3 text-sm">
          <div className="h-2 w-64 overflow-hidden rounded bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={next.target} aria-valuenow={next.reviewed} aria-label="Reviews completed">
            <div className="h-full bg-teal" style={{ width: `${Math.min(100, (next.reviewed / next.target) * 100)}%` }} />
          </div>
          <span className="tnum whitespace-nowrap">{next.reviewed} of {next.target} reviewed</span>
          <span className="text-muted">Order is fixed pseudo-random per dataset, so the reviewed set is a fair sample.</span>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card title={item ? `Conversation ${item.conversation_key}` : "Queue"} subtitle={item ? `${item.brand ?? "Unknown brand"} · ${item.customer_turns} customer message(s)` : undefined}>
          {!next ? <Spinner /> : !item ? <Empty title="Queue complete">Every conversation in this dataset has a human label.</Empty> : (
            <ol className="space-y-2">
              {item.messages.map((m) => (
                <li key={m.message_id} className={`rounded-md border px-3 py-2 ${m.role === "customer" ? "border-line bg-white" : "border-[#bfe0e2] bg-teal-light/40"}`}>
                  <div className="mb-1 flex items-center gap-2 text-xs text-muted">
                    <Badge tone={m.role === "customer" ? "neutral" : "teal"}>{m.role === "customer" ? "Customer" : "Support"}</Badge>
                    <span>{m.language}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm">{m.text}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
        {item && (
          <Card title={reveal ? "How the systems compared" : "Your labels"} subtitle={reveal ? "Your answer is saved; it does not change dashboard labels." : "System labels stay hidden until you submit."}>
            {!reveal ? (
              <div className="space-y-3">
                {fields.map((f) => (
                  <Field key={f} label={FIELD_LABELS[f]}>
                    <select className={inputCls} value={labels[f] ?? ""} onChange={(e) => setLabels({ ...labels, [f]: e.target.value })}>
                      <option value="" disabled>Choose…</option>
                      {next!.options[f].map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                    </select>
                  </Field>
                ))}
                <Field label="Reviewer"><input className={inputCls} value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></Field>
                <Notice tone="neutral">Choose "Unknown" when the messages do not show the answer. Do not guess.</Notice>
                <Button variant="primary" disabled={!complete || saving} onClick={submit}>{saving ? "Saving…" : "Submit and reveal"}</Button>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(reveal.comparison as Record<string, Record<string, any>>).map(([sys, rows]) => (
                  <div key={sys}>
                    <div className="mb-1 text-xs font-medium text-muted">{sys}</div>
                    <ul className="space-y-1 text-sm">
                      {fields.map((f) => (
                        <li key={f} className="flex items-center gap-2">
                          {rows[f].agree ? <CheckCircle2 className="h-4 w-4 text-green" aria-label="agrees" /> : <XCircle className="h-4 w-4 text-red" aria-label="disagrees" />}
                          <span className="w-36 text-muted">{FIELD_LABELS[f]}</span>
                          <span>{rows[f].system ?? "none"}</span>
                          {!rows[f].agree && <span className="text-muted">(you: {rows[f].human})</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                {Object.keys(reveal.comparison).length === 0 && <p className="text-sm text-muted">No stored system labels for this conversation.</p>}
                <Button variant="primary" onClick={load}>Next conversation</Button>
              </div>
            )}
          </Card>
        )}
      </div>
      {acc && (
        <Card title="Label accuracy against human review" subtitle={`${acc.reviewed} reviewed conversation(s). Active labels: ${acc.active_analysis ?? "none"}`}>
          {acc.reviewed < 30 && <Notice>Fewer than 30 reviews: intervals are wide and systems cannot be told apart yet. Aim for {acc.target}.</Notice>}
          {Object.keys(acc.systems).length === 0 ? <Empty title="No reviews yet">Submit a label set to start scoring.</Empty> : (
            <Table caption="Accuracy per field with Wilson 95% intervals. 'When answered' excludes conversations where the system said unknown."
              head={["System", "Field", "Reviewed", "Accuracy", "95% interval", "Said unknown", "Accuracy when answered", "Most common miss (system → human)"]}
              rows={Object.entries(acc.systems as Record<string, Record<string, any>>).flatMap(([sys, fs]) => fields.filter((f) => fs[f]).map((f) => [
                sys, FIELD_LABELS[f], fs[f].n, fmtPct(fs[f].accuracy), fs[f].ci95 ? `${fmtPct(fs[f].ci95[0])} – ${fmtPct(fs[f].ci95[1])}` : "–",
                fs[f].abstained, fs[f].precision_when_answered == null ? "–" : `${fmtPct(fs[f].precision_when_answered)} of ${fs[f].answered}`,
                fs[f].top_disagreements[0] ? `${fs[f].top_disagreements[0].system_to_human} (${fs[f].top_disagreements[0].count})` : "–",
              ]))} />
          )}
          {acc.inter_reviewer && <p className="mt-2 text-sm">Inter-reviewer agreement: {fmtPct(acc.inter_reviewer.agreement)} over {acc.inter_reviewer.pairs} paired labels.</p>}
        </Card>
      )}
    </div>
  );
}
