import { useState } from "react";
import { api, dsPath, filtersParam } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { fmtPct } from "../lib/format";
import { Badge, Button, Card, ErrorBox, PageHeader, Spinner, inputCls } from "../components/ui";
import { ChartCard } from "../charts/ChartCard";
import { OpportunityScatter } from "../charts/charts";
import { EvidenceLinks } from "../assistant/Flo";

const W = [
  { key: "frequency", label: "Observed frequency" },
  { key: "severity", label: "Severity" },
  { key: "evidence", label: "Evidence strength" },
  { key: "effort", label: "Lower effort" },
] as const;

function EffortForm({ c, onSaved }: { c: any; onSaved: () => void }) {
  const { dataset } = useApp();
  const [effort, setEffort] = useState<string>(c.effort ? String(c.effort) : "");
  const [severity, setSeverity] = useState<string>(c.severity_source === "reviewer" ? String(c.severity) : "");
  const [source, setSource] = useState(c.effort_source ?? "");
  const [reviewer, setReviewer] = useState(c.reviewer ?? "");
  const [err, setErr] = useState<string | null>(null);
  return (
    <form className="mt-2 grid grid-cols-2 gap-2 rounded-md bg-app p-2 text-xs lg:grid-cols-5" onSubmit={async (e) => {
      e.preventDefault();
      try {
        await api(dsPath(dataset!.id, `opportunities/${encodeURIComponent(c.key)}`), { method: "PUT", body: { effort: effort ? Number(effort) : null, severity: severity ? Number(severity) : null, effort_source: source || null, reviewer } });
        setErr(null); onSaved();
      } catch (ex: any) { setErr(ex.message); }
    }}>
      <label className="flex flex-col">Effort (1–5)<select className={inputCls} value={effort} onChange={(e) => setEffort(e.target.value)}><option value="">not estimated</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
      <label className="flex flex-col">Severity override<select className={inputCls} value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="">use rubric</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
      <label className="flex flex-col">Effort source<input className={inputCls} value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. engineering estimate" /></label>
      <label className="flex flex-col">Reviewer<input className={inputCls} required value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></label>
      <div className="flex items-end"><Button type="submit" size="sm" variant="primary">Save review</Button></div>
      {err && <div className="col-span-full text-red">{err}</div>}
    </form>
  );
}

export function Opportunities() {
  const { dataset, ask, busy } = useApp();
  const [w, setW] = useState({ frequency: 0.35, severity: 0.35, evidence: 0.2, effort: 0.1 });
  const [edit, setEdit] = useState<string | null>(null);
  const opp = useData<any>((id, f) => api(dsPath(id, "opportunities"), { params: { filters: filtersParam(f), w_frequency: w.frequency, w_severity: w.severity, w_evidence: w.evidence, w_effort: w.effort } }), [JSON.stringify(w)]);
  if (!dataset) return <PageHeader title="Opportunity portfolio" />;
  const d = opp.data;
  const withEffort = d?.candidates.filter((c: any) => c.effort) ?? [];
  return (
    <div className="space-y-4">
      <PageHeader title="Opportunity portfolio" description="Improvement candidates grouped by topic and subtheme, scored transparently. Effort is entered by reviewers only." />
      {opp.error && <ErrorBox onRetry={opp.reload}>{opp.error}</ErrorBox>}
      <Card title="Prioritisation weights" subtitle="Adjust and the ranking updates. The formula is shown below the table.">
        <div className="grid gap-4 md:grid-cols-4">
          {W.map(({ key, label }) => (
            <label key={key} className="text-xs text-muted">{label}: <span className="tnum font-semibold text-ink">{w[key].toFixed(2)}</span>
              <input type="range" min={0} max={1} step={0.05} value={w[key]} onChange={(e) => setW({ ...w, [key]: Number(e.target.value) })} className="mt-1 w-full accent-[#087F8C]" />
            </label>
          ))}
        </div>
      </Card>
      {!d ? <Spinner /> : (
        <>
          <Card title="Improvement candidates" subtitle={`Denominator: ${d.denominator} conversations in scope`}>
            <div className="space-y-3">
              {d.candidates.map((c: any, i: number) => (
                <div key={c.key} className="rounded-md border border-line p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold"><span className="tnum mr-2 text-muted">#{i + 1}</span>{c.title}</div>
                      <div className="mt-0.5 text-xs"><Badge tone="teal">Recommendation</Badge> {c.intervention}</div>
                      <div className="mt-0.5 text-[11px] text-muted">Proposed department: {c.proposed_department} (proposal)</div>
                    </div>
                    <div className="text-right">
                      <div className="tnum text-lg font-semibold">{c.score.toFixed(2)}</div>
                      <div className="text-[11px] text-muted">{c.score_complete ? "score" : "score without effort (incomplete)"}</div>
                    </div>
                  </div>
                  <div className="tnum mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-6">
                    <div><div className="text-muted">Observed frequency</div>{c.frequency.numerator} of {c.frequency.denominator} ({fmtPct(c.frequency.share)})</div>
                    <div><div className="text-muted">Explicitly unresolved</div>{c.unresolved.numerator} of {c.unresolved.denominator} known</div>
                    <div><div className="text-muted">Escalation requested</div>{c.escalation.numerator} of {c.escalation.denominator} known</div>
                    <div><div className="text-muted">Severity (1–5)</div>{c.severity} <Badge>{c.severity_source}</Badge></div>
                    <div><div className="text-muted">Evidence strength</div><Badge tone={c.evidence_strength === "strong" ? "green" : c.evidence_strength === "moderate" ? "amber" : "neutral"}>{c.evidence_strength}</Badge></div>
                    <div><div className="text-muted">Effort (reviewer)</div>{c.effort ?? <Badge tone="amber">needs estimate</Badge>}{c.effort_source && <div className="text-[10px] text-muted">{c.effort_source}</div>}</div>
                  </div>
                  <div className="mt-1 text-[11px] text-muted">Score parts: {Object.entries(c.score_parts).map(([k, v]) => `${k} ${v === null ? "n/a" : v}`).join(" + ")}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]">Evidence: <EvidenceLinks ids={c.evidence_ids} datasetId={dataset.id} /></div>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" onClick={() => setEdit(edit === c.key ? null : c.key)}>{edit === c.key ? "Close review" : "Review effort / severity"}</Button>
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => ask("Prepare a decision brief.", { topics: [c.topic] })}>Prepare decision brief with Flo</Button>
                  </div>
                  {edit === c.key && <EffortForm c={c} onSaved={() => { setEdit(null); opp.reload(); }} />}
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-1 rounded-md bg-app p-3 text-xs text-muted">
              <div><span className="font-medium text-ink">Score:</span> {d.rubric.score}</div>
              <div><span className="font-medium text-ink">Severity rubric:</span> {d.rubric.severity}</div>
              <div><span className="font-medium text-ink">Evidence strength:</span> {d.rubric.evidence_strength}</div>
              <div><span className="font-medium text-ink">Effort:</span> {d.rubric.effort}</div>
            </div>
          </Card>
          <ChartCard title="Opportunity frequency vs reviewer-estimated effort" scope={`${withEffort.length} of ${d.candidates.length} candidates have a reviewer effort estimate`} units="conversations; effort 1–5"
            empty={!withEffort.length ? "No reviewer has entered an effort estimate yet. Effort is never inferred; use “Review effort / severity”." : null}
            table={{ head: ["Candidate", "Conversations", "Effort", "Score"], rows: withEffort.map((c: any) => [c.title, c.frequency.numerator, c.effort, c.score]) }}
            askQuestion="Which improvement candidates have the strongest evidence?">
            <OpportunityScatter points={withEffort.map((c: any) => ({ title: c.title, effort: c.effort, count: c.frequency.numerator, topic: c.topic, score: c.score }))} />
          </ChartCard>
        </>
      )}
    </div>
  );
}
