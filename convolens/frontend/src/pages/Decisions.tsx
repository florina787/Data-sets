import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/state";
import { fmtDate } from "../lib/format";
import { Badge, Button, Card, Empty, ErrorBox, Field, PageHeader, Spinner, inputCls } from "../components/ui";
import { DecisionBrief, EvidenceLinks } from "../assistant/Flo";
import { TOPIC_LABELS } from "../lib/palette";

const STATUSES = ["proposed", "approved", "in_progress", "completed", "rejected"] as const;
const LABEL: Record<string, string> = { proposed: "Proposed", approved: "Approved", in_progress: "In progress", completed: "Completed", rejected: "Rejected" };
const TONE: Record<string, any> = { proposed: "amber", approved: "teal", in_progress: "teal", completed: "green", rejected: "red" };
const NEXT: Record<string, string[]> = { proposed: ["approved", "rejected"], approved: ["in_progress", "rejected"], in_progress: ["completed"], completed: [], rejected: ["proposed"] };

function Detail({ a, onChange }: { a: any; onChange: () => void }) {
  const [actor, setActor] = useState("");
  const [owner, setOwner] = useState(a.owner ?? "");
  const [due, setDue] = useState(a.due_date ?? "");
  const [measure, setMeasure] = useState(a.success_measure ?? "");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setOwner(a.owner ?? ""); setDue(a.due_date ?? ""); setMeasure(a.success_measure ?? ""); }, [a.id]);
  const patch = async (body: any) => {
    if (!actor) { setErr("Enter your name first; every change is recorded in the approval history."); return; }
    try { await api(`/api/actions/${a.id}`, { method: "PATCH", body: { actor, note: note || undefined, ...body } }); setErr(null); setNote(""); onChange(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <Card title={`Action #${a.id}: ${a.title}`} subtitle={<span><Badge tone={TONE[a.status]}>{LABEL[a.status]}</Badge> · created {fmtDate(a.created_at)} · issue: {TOPIC_LABELS[a.issue] ?? a.issue}</span>}>
      <dl className="grid gap-2 text-sm md:grid-cols-[160px_1fr]">
        <dt className="text-muted">Intervention</dt><dd>{a.intervention}</dd>
        <dt className="text-muted">Proposed department</dt><dd>{a.proposed_department ?? "—"} <Badge tone="amber">proposed</Badge></dd>
        <dt className="text-muted">Owner</dt><dd>{a.owner ?? "not set"} {a.owner && (a.owner_confirmed ? <Badge tone="green">confirmed by reviewer</Badge> : <Badge tone="amber">unconfirmed</Badge>)}</dd>
        <dt className="text-muted">Due date</dt><dd>{a.due_date ?? "—"}</dd>
        <dt className="text-muted">Intended outcome</dt><dd>{a.intended_outcome || "—"}</dd>
        <dt className="text-muted">Success measure</dt><dd>{a.success_measure || "—"}</dd>
        <dt className="text-muted">Supporting investigation</dt>
        <dd>“{a.investigation?.question}” · run {a.investigation?.request_id}<div className="mt-1"><EvidenceLinks ids={a.investigation?.evidence_ids ?? []} datasetId={a.dataset_id} /></div></dd>
      </dl>
      <div className="mt-4 grid gap-3 rounded-md bg-app p-3 md:grid-cols-2">
        <Field label="Your name (recorded)"><input className={inputCls} value={actor} onChange={(e) => setActor(e.target.value)} /></Field>
        <Field label="Note (optional)"><input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <Field label="Owner"><input className={inputCls} value={owner} onChange={(e) => setOwner(e.target.value)} /></Field>
        <Field label="Due date"><input type="date" className={inputCls} value={due} onChange={(e) => setDue(e.target.value)} /></Field>
        <Field label="Success measure"><input className={inputCls} value={measure} onChange={(e) => setMeasure(e.target.value)} /></Field>
        <div className="flex items-end gap-2">
          <Button size="sm" onClick={() => patch({ owner, confirm_owner: true, due_date: due || undefined, success_measure: measure })}>Save and confirm owner</Button>
        </div>
        <div className="col-span-full flex flex-wrap gap-2">
          {NEXT[a.status].map((s) => <Button key={s} size="sm" variant={s === "rejected" ? "danger" : "primary"} onClick={() => patch({ status: s })}>Move to {LABEL[s]}</Button>)}
        </div>
        {err && <div className="col-span-full"><ErrorBox>{err}</ErrorBox></div>}
      </div>
      <div className="mt-4">
        <div className="text-xs font-semibold text-muted">Approval history</div>
        <ol className="mt-1 space-y-1 text-xs">
          {a.history.map((h: any, i: number) => (
            <li key={i}><span className="tnum text-muted">{fmtDate(h.at, { dateStyle: "medium", timeStyle: "short" } as any)}</span> · {h.actor}: {h.from ? `${LABEL[h.from]} → ` : ""}{LABEL[h.to]}{h.note ? ` — ${h.note}` : ""}</li>
          ))}
        </ol>
      </div>
      {a.brief?.decision_proposed && <DecisionBrief brief={a.brief} datasetId={a.dataset_id} />}
    </Card>
  );
}

export function Decisions() {
  const { dataset } = useApp();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const load = () => api<any>("/api/actions", { params: { dataset_id: dataset?.id } }).then(setData).catch((e) => setErr(e.message));
  useEffect(() => { if (dataset) load(); }, [dataset?.id]);
  if (!dataset) return <PageHeader title="Decisions and actions" />;
  const actions = data?.actions ?? [];
  const current = actions.find((a: any) => a.id === sel);
  return (
    <div className="space-y-4">
      <PageHeader title="Decisions and actions" description="Internal action records created only after a reviewer confirms a Flo proposal. Nothing here sends messages or changes external systems." />
      {err && <ErrorBox onRetry={load}>{err}</ErrorBox>}
      {!data ? <Spinner /> : !actions.length ? <Empty title="No action records yet">Ask Flo to “Propose an action” for a scope, then approve or save it.</Empty> : (
        <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
          <div className="space-y-3">
            {STATUSES.map((s) => {
              const items = actions.filter((a: any) => a.status === s);
              return (
                <Card key={s} title={<span>{LABEL[s]} <span className="tnum text-muted">({items.length})</span></span>}>
                  {!items.length ? <p className="text-xs text-muted">None</p> : (
                    <ul className="divide-y divide-line">{items.map((a: any) => (
                      <li key={a.id}><button type="button" onClick={() => setSel(a.id)} aria-current={sel === a.id}
                        className={`w-full py-1.5 text-left text-sm hover:text-teal ${sel === a.id ? "font-medium text-teal" : ""}`}>
                        #{a.id} {a.title}<div className="text-[11px] text-muted">owner: {a.owner ?? "not set"} · due {a.due_date ?? "—"}</div>
                      </button></li>
                    ))}</ul>
                  )}
                </Card>
              );
            })}
          </div>
          {current ? <Detail a={current} onChange={load} /> : <Empty title="Select an action">Open an action to review its brief, owner, due date and history.</Empty>}
        </div>
      )}
    </div>
  );
}
