import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../context";
import { ProvenanceChip, SignInPrompt, Skeleton } from "../components/pulse/shared";

const LABELS: Record<string, string> = {
  incidents_opened: "Incidents opened", incidents_resolved: "Incidents resolved", deployments: "Deployments",
  agent_runs: "Agent runs", inspections: "Your inspection batches", decisions_made: "Decisions recorded",
  outcomes_recorded: "Outcomes recorded", model_calls: "Local-model calls",
};

const cad = (cents: number) => `CAD ${(cents / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/** Reports: the weekly CTO review and an evidence-backed Enterprise Time Machine. */
export default function Reports() {
  const { user } = useApp();
  const [weekly, setWeekly] = useState<any>(null);
  const [hist, setHist] = useState<any>(null);
  const [a, setA] = useState<string>("");
  const [b, setB] = useState<string>("");
  useEffect(() => {
    if (!user) return;
    api("/api/reports/weekly").then(setWeekly).catch(() => setWeekly(false));
    api("/api/reports/history").then((h) => {
      setHist(h);
      const s = h.sales.series;
      if (s.length >= 2) { setA(s[s.length - 5]?.week ?? s[0].week); setB(s[s.length - 1].week); }
    }).catch(() => setHist(false));
  }, [user?.username]);
  const cmp = useMemo(() => {
    if (!hist) return null;
    const find = (w: string) => hist.sales.series.find((x: any) => x.week === w);
    const qa = (w: string) => hist.quality.series.find((x: any) => x.week === w);
    return { a: find(a), b: find(b), qa: qa(a), qb: qa(b) };
  }, [hist, a, b]);
  if (!user) return <SignInPrompt what="reports" />;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header>
        <div className="eyebrow">Reports</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Weekly CTO review</h1>
        <p className="mt-1 text-ink-muted">This week next to last week. Counts are side by side; no causal claims are made.</p>
      </header>
      {weekly === null ? <Skeleton lines={6} /> : weekly === false ? <p className="text-brick-700">Couldn't load the weekly review.</p> : (
        <>
          <section className="panel" aria-labelledby="ops-h" data-testid="weekly-review">
            <div className="flex items-center justify-between gap-2"><h2 id="ops-h" className="text-lg font-semibold text-ink">Operations and technology</h2><ProvenanceChip kind="operational_record" /></div>
            <table className="table mt-3">
              <thead><tr><th>Measure</th><th className="text-right">Last 7 days</th><th className="text-right">Previous 7 days</th></tr></thead>
              <tbody>{Object.keys(LABELS).map((k) => (
                <tr key={k}><td>{LABELS[k]}</td><td className="text-right font-mono">{weekly.this_week[k]}</td><td className="text-right font-mono text-ink-muted">{weekly.last_week[k]}</td></tr>
              ))}</tbody>
            </table>
          </section>
          <div className="grid gap-6 lg:grid-cols-2">
            <section className="panel">
              <div className="flex items-center justify-between gap-2"><h2 className="text-lg font-semibold text-ink">Business</h2><ProvenanceChip kind="synthetic" /></div>
              {weekly.business ? <p className="mt-2 text-sm text-ink-muted">Week of {weekly.business.week}: <b className="text-ink">{cad(weekly.business.revenue)}</b> revenue, {weekly.business.change_pct}% vs the week of {weekly.business.previous_week}.</p> : <p className="mt-2 text-sm">No weekly sales data.</p>}
            </section>
            <section className="panel">
              <h2 className="text-lg font-semibold text-ink">Unresolved high priorities</h2>
              {weekly.unresolved.length === 0 ? <p className="mt-2 text-sm">None.</p> : <ul className="mt-2 space-y-1 text-sm">{weekly.unresolved.map((u: any) => <li key={u.id} className="flex items-center gap-2 text-ink">• {u.title} <ProvenanceChip kind={u.provenance} /></li>)}</ul>}
              <p className="mt-3 text-xs text-ink-muted">{weekly.decisions.length} decision(s) recorded or completed this week.</p>
            </section>
          </div>
          <p className="text-xs text-ink-faint">{weekly.note}</p>
        </>
      )}

      <section className="panel" aria-labelledby="tm-h" data-testid="time-machine">
        <h2 id="tm-h" className="text-xl font-semibold text-ink">Enterprise Time Machine</h2>
        <p className="text-sm text-ink-muted">Compare two weeks using stored history. Only domains with history are shown; others are listed as gaps.</p>
        {!hist ? <div className="mt-3"><Skeleton /></div> : (
          <>
            <div className="mt-3 flex flex-wrap items-end gap-3 text-sm">
              <label className="text-ink-muted">Then <select className="ml-1 rounded-lg border px-2 py-1" value={a} onChange={(e) => setA(e.target.value)}>{hist.sales.series.map((w: any) => <option key={w.week}>{w.week}</option>)}</select></label>
              <label className="text-ink-muted">Now <select className="ml-1 rounded-lg border px-2 py-1" value={b} onChange={(e) => setB(e.target.value)}>{hist.sales.series.map((w: any) => <option key={w.week}>{w.week}</option>)}</select></label>
            </div>
            {cmp?.a && cmp?.b && (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-surface-line bg-midnight/40 p-4">
                  <div className="flex items-center justify-between"><span className="text-sm font-semibold text-ink">Weekly revenue</span><ProvenanceChip kind="synthetic" /></div>
                  <p className="mt-2 text-sm text-ink-muted">{a}: <b className="text-ink">{cad(cmp.a.revenue)}</b> · {b}: <b className="text-ink">{cad(cmp.b.revenue)}</b></p>
                  <p className="text-sm text-ink-muted">Change: <b className="text-teal-soft">{cmp.a.revenue ? (100 * (cmp.b.revenue - cmp.a.revenue) / cmp.a.revenue).toFixed(1) : "—"}%</b> · units {cmp.a.units.toLocaleString()} → {cmp.b.units.toLocaleString()}</p>
                </div>
                <div className="rounded-xl border border-surface-line bg-midnight/40 p-4">
                  <div className="flex items-center justify-between"><span className="text-sm font-semibold text-ink">Potato quality (your inspections)</span><ProvenanceChip kind="operational_record" /></div>
                  <p className="mt-2 text-sm text-ink-muted">{cmp.qa || cmp.qb ? `${a}: ${cmp.qa ? `${cmp.qa.not_good}/${cmp.qa.graded} Not Good` : "no inspections"} · ${b}: ${cmp.qb ? `${cmp.qb.not_good}/${cmp.qb.graded} Not Good` : "no inspections"}` : "No inspections in either week."}</p>
                </div>
              </div>
            )}
            <p className="mt-3 text-xs text-ink-faint">{hist.note}</p>
          </>
        )}
      </section>
    </div>
  );
}
