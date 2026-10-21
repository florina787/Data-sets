import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/state";
import { fmtInt, fmtPct } from "../lib/format";
import { Badge, Button, Card, Empty, ErrorBox, Field, PageHeader, Table, inputCls } from "../components/ui";

export function Impact() {
  const { dataset, datasets, filters } = useApp();
  const [actions, setActions] = useState<any[]>([]);
  const [actionId, setActionId] = useState<string>("");
  const [baseline, setBaseline] = useState("");
  const [followup, setFollowup] = useState("");
  const [date, setDate] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<any>("/api/actions").then((r) => setActions(r.actions)).catch(() => undefined); }, []);
  useEffect(() => { if (dataset) { setBaseline(dataset.id); setFollowup(dataset.id); } }, [dataset?.id]);
  const ready = datasets.filter((d) => d.status === "ready");
  const run = async () => {
    setErr(null);
    try {
      const a = actions.find((x) => String(x.id) === actionId);
      setRes(await api("/api/impact", { body: { baseline_dataset: baseline, followup_dataset: followup || null, intervention_date: date, filters: a?.investigation?.filters ?? filters, action_id: a?.id ?? null, reviewer: reviewer || "reviewer" } }));
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Impact review" description="Compare a baseline and a follow-up selection with comparable denominators. Observed changes are not proof of impact." />
      <Card title="Selection">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Action (optional; uses its investigation scope)">
            <select className={inputCls} value={actionId} onChange={(e) => setActionId(e.target.value)}>
              <option value="">Current page filters</option>
              {actions.map((a) => <option key={a.id} value={a.id}>#{a.id} {a.title}</option>)}
            </select>
          </Field>
          <Field label="Baseline dataset"><select className={inputCls} value={baseline} onChange={(e) => setBaseline(e.target.value)}>{ready.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
          <Field label="Follow-up dataset" hint="Conversations on or after the intervention date are used as follow-up."><select className={inputCls} value={followup} onChange={(e) => setFollowup(e.target.value)}>{ready.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
          <Field label="Intervention date (entered by reviewer)"><input type="date" className={inputCls} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Reviewer"><input className={inputCls} value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></Field>
          <div className="flex items-end"><Button variant="primary" disabled={!date || !baseline} onClick={run}>Compare</Button></div>
        </div>
      </Card>
      {err && <ErrorBox>{err}</ErrorBox>}
      {res && (
        <Card title={res.metric} subtitle={`Intervention date ${res.intervention_date}`}>
          <div className="mb-3 flex items-start gap-2 rounded-md border border-[#ecd3ad] bg-amber-light px-3 py-2 text-sm text-[#7a4805]" role="note">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />{res.warning}
          </div>
          {!res.followup_available ? <Empty title="Follow-up data unavailable">{res.empty_state}</Empty> : (
            <>
              <Table head={["", "Dataset", "Conversations", "Known outcomes", "Unknown", "Explicitly unresolved", "Rate", "Outcome coverage"]}
                rows={[["Baseline (before)", res.baseline], ["Follow-up (on/after)", res.followup]].map(([l, s]: any) => [l, s.dataset, fmtInt(s.conversations), fmtInt(s.known_outcomes), fmtInt(s.unknown_outcomes), fmtInt(s.explicitly_unresolved), fmtPct(s.rate, 1), fmtPct(s.coverage)])} />
              <div className="mt-3 text-sm">
                {res.comparable && res.observed_change ? (
                  <p>Observed change: explicitly unresolved rate is <strong>{res.observed_change.direction}</strong> by <span className="tnum">{Math.abs(res.observed_change.rate_difference_points)}</span> percentage points. This is an observed difference, not a measured effect of the action.</p>
                ) : <p className="text-red">Not comparable: at least one comparability check failed, so no change is reported.</p>}
              </div>
              <ul className="mt-3 space-y-1 text-xs">
                {res.checks.map((c: any) => <li key={c.check}><Badge tone={c.passed ? "green" : "red"}>{c.passed ? "pass" : "fail"}</Badge> {c.check}{c.detail ? ` (${c.detail})` : ""}</li>)}
              </ul>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
