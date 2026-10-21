import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Check, ChevronDown, CircleSlash, ExternalLink, Loader2, Save, Send, Square, ThumbsDown, ThumbsUp, Wrench, X } from "lucide-react";
import { api, sessionHeaders, type Filters } from "../lib/api";
import { Markdown } from "../lib/markdown";
import { useApp, type FloTurn } from "../lib/state";
import { Badge, Button, Monogram, inputCls } from "../components/ui";
import { RESOLUTION_LABELS, TOPIC_LABELS, SENTIMENT_LABELS, ESCALATION_LABELS, HANDOFF_LABELS } from "../lib/palette";

export const OPENING = "Hello, I’m Flo. I can help you investigate customer issues, compare conversation patterns, and prepare evidence-backed decisions.";
export const SUGGESTIONS = [
  "Brief me on this dataset.",
  "Investigate unresolved issues.",
  "Compare resolved and unresolved conversations.",
  "Show the evidence behind this chart.",
  "Prepare a decision brief.",
  "Explain the limitations of this analysis.",
];

export function describeFilters(f: Filters): { key: keyof Filters; value: string; label: string }[] {
  const out: { key: keyof Filters; value: string; label: string }[] = [];
  f.topics?.forEach((v) => out.push({ key: "topics", value: v, label: `Topic: ${TOPIC_LABELS[v] ?? v}` }));
  f.resolution?.forEach((v) => out.push({ key: "resolution", value: v, label: `Outcome: ${RESOLUTION_LABELS[v] ?? v}` }));
  f.sentiment_end?.forEach((v) => out.push({ key: "sentiment_end", value: v, label: `Ending sentiment: ${SENTIMENT_LABELS[v] ?? v}` }));
  f.escalation?.forEach((v) => out.push({ key: "escalation", value: v, label: ESCALATION_LABELS[v] ?? v }));
  f.handoff?.forEach((v) => out.push({ key: "handoff", value: v, label: HANDOFF_LABELS[v] ?? v }));
  f.languages?.forEach((v) => out.push({ key: "languages", value: v, label: `Language: ${v}` }));
  f.brands?.forEach((v) => out.push({ key: "brands", value: v, label: `Account: ${v}` }));
  if (f.date_from || f.date_to) out.push({ key: "date_from", value: "", label: `Dates: ${f.date_from ?? "…"} – ${f.date_to ?? "…"}` });
  return out;
}

export function ScopeChips({ editable = true }: { editable?: boolean }) {
  const { filters, setFilters } = useApp();
  const chips = describeFilters(filters);
  if (!chips.length) return <span className="text-xs text-muted">All conversations in the selected dataset</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {chips.map((c) => (
        <span key={c.label} className="inline-flex items-center gap-1 rounded-full border border-[#bfe0e2] bg-teal-light px-2 py-0.5 text-[11px] font-medium text-teal">
          {c.label}
          {editable && (
            <button type="button" aria-label={`Remove filter ${c.label}`} onClick={() => {
              const next = { ...filters } as any;
              if (c.key === "date_from") { delete next.date_from; delete next.date_to; }
              else next[c.key] = (next[c.key] as string[]).filter((x: string) => x !== c.value);
              setFilters(next);
            }}><X className="h-3 w-3" aria-hidden /></button>
          )}
        </span>
      ))}
    </div>
  );
}

function ToolActivityList({ turn, defaultOpen }: { turn: FloTurn; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(!!defaultOpen);
  if (!turn.tools.length) return null;
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-2 rounded-md border border-line bg-app/60">
      <Collapsible.Trigger className="flex w-full items-center justify-between px-2.5 py-1.5 text-xs font-medium text-muted">
        <span className="inline-flex items-center gap-1.5"><Wrench className="h-3.5 w-3.5" aria-hidden />Tool activity ({turn.tools.length})</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </Collapsible.Trigger>
      <Collapsible.Content>
        <ol className="space-y-1.5 px-2.5 pb-2">
          {turn.tools.map((t) => (
            <li key={t.step} className="text-xs">
              <div className="flex items-center gap-1.5">
                {t.status === "running" ? <Loader2 className="h-3 w-3 animate-spin text-teal" aria-hidden /> : t.status === "ok" ? <Check className="h-3 w-3 text-green" aria-hidden /> : <CircleSlash className="h-3 w-3 text-red" aria-hidden />}
                <code className="font-mono text-[11px] text-ink">{t.tool}</code>
                <span className="text-muted">— {t.purpose}</span>
                <span className="sr-only">status {t.status}</span>
              </div>
              {t.filters && <div className="ml-4.5 pl-[18px] text-muted">Filters: {t.filters}</div>}
              {t.summary && <div className="pl-[18px] text-ink">{t.summary}</div>}
            </li>
          ))}
        </ol>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

function EvidenceList({ evidence, highlight, datasetId }: { evidence: any[]; highlight: string | null; datasetId: string }) {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  useEffect(() => { if (highlight) setOpen(true); }, [highlight]);
  if (!evidence?.length) return null;
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-2 rounded-md border border-line">
      <Collapsible.Trigger className="flex w-full items-center justify-between px-2.5 py-1.5 text-xs font-medium text-ink">
        <span>Evidence ({evidence.length} validated message{evidence.length > 1 ? "s" : ""})</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </Collapsible.Trigger>
      <Collapsible.Content>
        <ul className="divide-y divide-line">
          {evidence.map((e) => (
            <li key={e.id} id={`ev-${e.ref}`} className={`px-2.5 py-2 text-xs ${highlight === e.ref ? "bg-teal-light" : ""}`}>
              <div className="mb-0.5 flex flex-wrap items-center gap-1.5">
                <Badge tone="teal">{e.ref}</Badge>
                <Badge>{e.role}</Badge>
                {e.language && e.language !== "en" && <Badge title="Language of the original message">lang: {e.language}</Badge>}
                {e.translated && <Badge tone="amber">Translated quotation</Badge>}
              </div>
              <blockquote className="border-l-2 border-line pl-2 text-[13px] text-ink">“{e.quote}”</blockquote>
              <button type="button" className="mt-1 inline-flex items-center gap-1 text-teal hover:underline"
                onClick={() => nav(`/explorer?dataset=${encodeURIComponent(datasetId)}&conversation=${encodeURIComponent(e.conversation_key)}&message=${encodeURIComponent(e.message_id)}`)}>
                <ExternalLink className="h-3 w-3" aria-hidden />Open message {e.message_id} in conversation
              </button>
            </li>
          ))}
        </ul>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

function MetricsList({ metrics, highlight }: { metrics: any[]; highlight: string | null }) {
  const [open, setOpen] = useState(false);
  useEffect(() => { if (highlight) setOpen(true); }, [highlight]);
  if (!metrics?.length) return null;
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-2 rounded-md border border-line">
      <Collapsible.Trigger className="flex w-full items-center justify-between px-2.5 py-1.5 text-xs font-medium text-ink">
        <span>Validated metrics ({metrics.length}) — SQL counts</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </Collapsible.Trigger>
      <Collapsible.Content>
        <table className="w-full text-xs">
          <thead><tr className="text-left text-muted"><th className="px-2 py-1 font-medium">Ref</th><th className="px-2 py-1 font-medium">Metric</th><th className="px-2 py-1 text-right font-medium">Value</th><th className="px-2 py-1 text-right font-medium">Unknown</th></tr></thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.id} className={`border-t border-line ${highlight === m.id ? "bg-teal-light" : ""}`}>
                <td className="px-2 py-1 font-semibold text-teal">{m.id}</td>
                <td className="px-2 py-1">{m.label}<div className="text-[10px] text-muted">{m.scope}</div></td>
                <td className="tnum px-2 py-1 text-right">{m.denominator ? `${m.numerator} of ${m.denominator}` : m.numerator}</td>
                <td className="tnum px-2 py-1 text-right">{m.unknown ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}

export function DecisionBrief({ brief, datasetId }: { brief: any; datasetId: string }) {
  const rows: [string, React.ReactNode][] = [
    ["Decision proposed", brief.decision_proposed],
    ["Business question", brief.business_question],
    ["Dataset and scope", brief.dataset_and_scope],
    ["Observed finding", brief.observed_finding],
    ["Numerator / denominator", `${brief.numerator} of ${brief.denominator} with known outcome (${brief.unknown} unknown; ${brief.conversations_in_scope} in scope)`],
    ["Evidence links", <EvidenceLinks key="e" ids={brief.evidence_ids ?? []} datasetId={datasetId} />],
    ["Hypothesis", <span key="h"><Badge tone="amber">Hypothesis</Badge> {brief.hypothesis}</span>],
    ["Alternative explanations", <ul key="a" className="list-disc pl-4">{brief.alternative_explanations?.map((a: string) => <li key={a}>{a}</li>)}</ul>],
    ["Proposed intervention", <span key="i"><Badge tone="teal">Recommendation</Badge> {brief.proposed_intervention}</span>],
    ["Proposed owner", `${brief.proposed_owner?.department ?? "—"} (${brief.proposed_owner?.status})`],
    ["Estimated effort and source", `${brief.estimated_effort?.value ?? "—"} · ${brief.estimated_effort?.source}`],
    ["Success measure", brief.success_measure],
    ["Required additional data", <ul key="r" className="list-disc pl-4">{brief.required_additional_data?.map((a: string) => <li key={a}>{a}</li>)}</ul>],
    ["Limitations", <ul key="l" className="list-disc pl-4">{brief.limitations?.map((a: string) => <li key={a}>{a}</li>)}</ul>],
    ["Review status", <Badge key="s" tone="amber">{brief.review_status}</Badge>],
  ];
  return (
    <div className="mt-2 rounded-md border border-line">
      <div className="border-b border-line bg-app px-2.5 py-1.5 text-xs font-semibold">Leadership decision brief (draft for review)</div>
      <dl className="divide-y divide-line text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[140px_1fr] gap-2 px-2.5 py-1.5">
            <dt className="font-medium text-muted">{k}</dt><dd className="text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="px-2.5 py-1.5 text-[11px] text-muted">No revenue, churn, savings or ROI figures are produced. Effort must be entered by a reviewer.</div>
    </div>
  );
}

export function EvidenceLinks({ ids, datasetId }: { ids: string[]; datasetId: string }) {
  const nav = useNavigate();
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => {
        const [conv, rest] = id.split("/");
        const msg = rest?.split("#")[0];
        return (
          <button key={id} type="button" className="rounded bg-teal-light px-1.5 text-[11px] text-teal hover:underline"
            onClick={() => nav(`/explorer?dataset=${encodeURIComponent(datasetId)}&conversation=${conv}&message=${msg}`)}>{msg}</button>
        );
      })}
      {!ids.length && "—"}
    </span>
  );
}

function ApprovalCard({ turn }: { turn: FloTurn }) {
  const { decide, busy } = useApp();
  const p = turn.approval?.proposed_action ?? turn.response?.proposed_action;
  const [owner, setOwner] = useState(p?.owner ?? "");
  const [due, setDue] = useState(p?.due_date ?? "");
  const [reviewer, setReviewer] = useState("");
  const [measure, setMeasure] = useState(p?.success_measure ?? "");
  if (!p) return null;
  const submitted = turn.approval?.submitted;
  const record = turn.response?.action_record;
  const edits = { owner: owner || null, due_date: due || null, success_measure: measure };
  return (
    <div className="mt-2 rounded-md border-2 border-[#ecd3ad] bg-amber-light/50 p-2.5 text-xs">
      <div className="mb-1 font-semibold text-[#7a4805]">Proposed action — not saved yet</div>
      <div className="mb-2 text-ink"><span className="font-medium">{p.title}</span><br />{p.intervention}</div>
      <div className="mb-1 text-muted">Proposed department: {p.proposed_department ?? "—"} (proposal, not a confirmed owner)</div>
      {record ? (
        <div className="rounded bg-white px-2 py-1.5 text-ink" role="status">
          <Check className="mr-1 inline h-3.5 w-3.5 text-green" aria-hidden />Saved as action #{record.id} with status <strong>{record.status}</strong>{record.created ? "" : " (already existed — not duplicated)"}.
        </div>
      ) : submitted === "reject" ? (
        <div className="rounded bg-white px-2 py-1.5 text-muted">Rejected. Nothing was saved.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-0.5">Owner (you enter or confirm)<input className={inputCls} value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="e.g. Billing operations lead" /></label>
            <label className="flex flex-col gap-0.5">Due date<input type="date" className={inputCls} value={due} onChange={(e) => setDue(e.target.value)} /></label>
            <label className="col-span-2 flex flex-col gap-0.5">Success measure<input className={inputCls} value={measure} onChange={(e) => setMeasure(e.target.value)} /></label>
            <label className="col-span-2 flex flex-col gap-0.5">Your name (reviewer)<input className={inputCls} value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></label>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" variant="primary" disabled={busy || !!submitted || !owner || !reviewer} onClick={() => decide(turn.id, "approve", edits, reviewer)}>Approve and save</Button>
            <Button size="sm" disabled={busy || !!submitted || !reviewer} onClick={() => decide(turn.id, "save_as_proposed", edits, reviewer)}>Save as proposed</Button>
            <Button size="sm" variant="danger" disabled={busy || !!submitted} onClick={() => decide(turn.id, "reject", {}, reviewer || "reviewer")}>Reject</Button>
          </div>
          <p className="mt-1.5 text-[11px] text-muted">Approval requires an owner. Flo never sends emails, contacts people or changes external systems.</p>
        </>
      )}
    </div>
  );
}

function Feedback({ requestId }: { requestId: string }) {
  const [state, setState] = useState<"idle" | "sent" | "correct">("idle");
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const send = async (score: number, correction?: string) => {
    try {
      const r = await api<{ sent_to_langsmith: boolean }>(`/api/flo/runs/${requestId}/feedback`, { body: { score, correction }, headers: await sessionHeaders() });
      setState("sent");
      setNote(r.sent_to_langsmith ? "Feedback saved and sent to LangSmith." : "Feedback saved locally (LangSmith not configured).");
    } catch (e: any) { setNote(e.message); }
  };
  if (state === "sent") return <div className="mt-2 text-[11px] text-muted">{note}</div>;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
      Was this useful?
      <Button size="sm" variant="ghost" aria-label="Helpful" onClick={() => send(1)}><ThumbsUp className="h-3.5 w-3.5" aria-hidden /></Button>
      <Button size="sm" variant="ghost" aria-label="Not helpful" onClick={() => setState("correct")}><ThumbsDown className="h-3.5 w-3.5" aria-hidden /></Button>
      {state === "correct" && (
        <div className="flex w-full gap-1.5">
          <input className={`${inputCls} flex-1 text-xs`} value={text} onChange={(e) => setText(e.target.value)} placeholder="What should be corrected?" aria-label="Correction" />
          <Button size="sm" onClick={() => send(0, text)}>Send</Button>
        </div>
      )}
      {note && <span>{note}</span>}
    </div>
  );
}

function SaveInvestigation({ turn }: { turn: FloTurn }) {
  const [saved, setSaved] = useState<string | null>(null);
  return saved ? <span className="text-[11px] text-green">{saved}</span> : (
    <Button size="sm" variant="ghost" onClick={async () => {
      try {
        await api("/api/flo/investigations", { body: { request_id: turn.requestId, title: turn.question.slice(0, 120) }, headers: await sessionHeaders() });
        setSaved("Saved to investigations");
      } catch (e: any) { setSaved(e.message); }
    }}><Save className="h-3.5 w-3.5" aria-hidden />Save investigation</Button>
  );
}

export function TurnView({ turn, compact }: { turn: FloTurn; compact?: boolean }) {
  const { ask, busy, setFilters } = useApp();
  const [hl, setHl] = useState<string | null>(null);
  const r = turn.response;
  const streaming = turn.status === "streaming";
  const scope = describeFilters(turn.filters);
  return (
    <div className="space-y-2">
      <div className="ml-6 rounded-lg bg-sidebar px-3 py-2 text-sm text-white">
        {turn.question}
        <div className="mt-0.5 text-[10px] text-white/70">{turn.page} · {scope.length ? scope.map((s) => s.label).join("; ") : "all conversations"}</div>
      </div>
      <div className="flex gap-2">
        <Monogram size={22} />
        <div className="min-w-0 flex-1 rounded-lg border border-line bg-white px-3 py-2">
          <div className="mb-1 flex flex-wrap items-center gap-1">
            {turn.mode === "demo" ? <Badge tone="amber">Demonstration · rules-based, no model call</Badge> : <Badge tone="teal">{turn.method ?? "Connected analysis"}</Badge>}
            {r?.validation?.status === "passed" && <Badge tone="green"><Check className="h-3 w-3" aria-hidden />Claims validated</Badge>}
            {r?.validation?.status === "failed" && <Badge tone="red">Validation failed</Badge>}
            {r?.kind === "unsupported" && <Badge tone="amber">Not available in data</Badge>}
            {r?.kind === "insufficient" && <Badge tone="amber">Insufficient evidence</Badge>}
          </div>
          {streaming && !r && (
            <div className="text-xs text-muted" aria-live="polite">
              <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" aria-hidden />
              {turn.nodeOrder.length ? `Running ${turn.nodeOrder[turn.nodeOrder.length - 1].replace(/_/g, " ")}…` : "Starting…"}
            </div>
          )}
          {streaming && !r && turn.streamedText && <Markdown text={turn.streamedText} />}
          {r && <Markdown text={r.text ?? ""} onCite={(ref) => setHl(ref)} />}
          {(turn.status === "error" || turn.status === "failed") && (
            <div className="mt-2 rounded border border-[#e8c3c6] bg-red-light px-2 py-1.5 text-xs text-red" role="alert">
              {turn.error ?? "The run failed."} No result was substituted.
              <Button size="sm" variant="danger" className="ml-2" disabled={busy} onClick={() => ask(turn.question, turn.filters)}>Retry</Button>
            </div>
          )}
          {turn.status === "cancelled" && !r && <div className="mt-1 text-xs text-muted">Cancelled. Nothing was saved.</div>}
          <ToolActivityList turn={turn} defaultOpen={streaming && !compact} />
          {r && <MetricsList metrics={r.metrics} highlight={hl?.startsWith("M") ? hl : null} />}
          {r && <EvidenceList evidence={r.evidence} highlight={hl?.startsWith("E") ? hl : null} datasetId={turn.datasetId} />}
          {r?.brief && <DecisionBrief brief={r.brief} datasetId={turn.datasetId} />}
          {(turn.approval || r?.proposed_action) && <ApprovalCard turn={turn} />}
          {r?.follow_up_chips?.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {r.follow_up_chips.map((c: any) => (
                <button key={c.label} type="button" disabled={busy}
                  className="rounded-full border border-line bg-app px-2 py-0.5 text-[11px] text-ink hover:border-teal hover:text-teal disabled:opacity-50"
                  onClick={() => (c.question ? ask(c.question, c.filters) : setFilters(c.filters))}>{c.label}</button>
              ))}
            </div>
          )}
          {r && turn.requestId && turn.status !== "streaming" && (
            <div className="mt-1 flex flex-wrap items-center justify-between gap-1">
              <Feedback requestId={turn.requestId} />
              {r.kind !== "error" && <SaveInvestigation turn={turn} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function FloChat({ variant }: { variant: "panel" | "page" }) {
  const { turns, ask, busy, cancel, page, dataset, mode, status } = useApp();
  const [q, setQ] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [turns]);
  const connectedNoModel = mode === "connected" && status && !status.model?.configured;
  const submit = () => { if (q.trim()) { ask(q.trim()); setQ(""); } };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-line px-3 py-2">
        <div className="mb-1 text-[11px] text-muted">Context: <span className="font-medium text-ink">{page}</span> · {dataset?.name ?? "no dataset"}</div>
        <ScopeChips />
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3" aria-live="polite">
        <div className="flex gap-2">
          <Monogram size={22} />
          <div className="rounded-lg border border-line bg-white px-3 py-2 text-sm">{OPENING}</div>
        </div>
        {connectedNoModel && (
          <div className="rounded-md border border-[#ecd3ad] bg-amber-light px-3 py-2 text-xs text-[#7a4805]">
            Connected analysis needs a configured model. Flo will report an error rather than switch to demonstration rules.
          </div>
        )}
        {!turns.length && (
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" disabled={busy || !dataset} onClick={() => ask(s)}
                className="rounded-full border border-line bg-white px-2.5 py-1 text-xs text-ink hover:border-teal hover:text-teal disabled:opacity-50">{s}</button>
            ))}
          </div>
        )}
        {turns.map((t) => <TurnView key={t.id} turn={t} compact={variant === "panel"} />)}
        <div ref={endRef} />
      </div>
      <form className="border-t border-line p-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <div className="flex items-end gap-1.5">
          <textarea aria-label="Ask Flo" rows={variant === "page" ? 2 : 1} value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder={dataset ? "Ask about the selected scope…" : "Select a dataset first"} disabled={!dataset}
            className={`${inputCls} max-h-32 flex-1 resize-none`} />
          {busy ? (
            <Button variant="danger" onClick={cancel} aria-label="Cancel"><Square className="h-3.5 w-3.5" aria-hidden />Cancel</Button>
          ) : (
            <Button variant="primary" type="submit" disabled={!q.trim() || !dataset} aria-label="Send"><Send className="h-3.5 w-3.5" aria-hidden /></Button>
          )}
        </div>
        <p className="mt-1 text-[10px] text-muted">Flo shows tool activity and validation, not private reasoning. Answers describe this data and may be wrong; check the cited messages.</p>
      </form>
    </div>
  );
}

export function FloPanel() {
  const { floOpen, setFloOpen } = useApp();
  if (!floOpen) return null;
  return (
    <aside aria-label="Flo assistant" className="flex w-[400px] shrink-0 flex-col border-l border-line bg-[#FAFBFC]">
      <div className="flex items-center justify-between border-b border-line bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <Monogram />
          <div>
            <div className="text-sm font-semibold">Flo</div>
            <div className="text-[11px] text-muted">Your customer intelligence and decision-support assistant.</div>
          </div>
        </div>
        <Button size="sm" variant="ghost" aria-label="Collapse Flo" onClick={() => setFloOpen(false)}><X className="h-4 w-4" aria-hidden /></Button>
      </div>
      <div className="min-h-0 flex-1"><FloChat variant="panel" /></div>
    </aside>
  );
}
