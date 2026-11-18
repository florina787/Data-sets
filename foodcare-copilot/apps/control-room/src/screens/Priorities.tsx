import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../context";
import { openInvestigation } from "../components/pulse/InvestigationPanel";
import { Priority, SignInPrompt, Skeleton, sortForLens, useLens } from "../components/pulse/shared";
import { openCopilot } from "./Copilot";
import { PriorityCard } from "./Pulse";

type Change = { metric: string; then: unknown; now: unknown };

/** My Priorities: every open priority, plus the Decision Journal and saved investigations. */
export default function Priorities() {
  const { user } = useApp();
  const lens = useLens();
  const [prios, setPrios] = useState<Priority[] | null>(null);
  const [decisions, setDecisions] = useState<any[] | null>(null);
  const [invs, setInvs] = useState<any[] | null>(null);
  const load = () => {
    api<{ priorities: Priority[] }>("/api/priorities").then((d) => setPrios(d.priorities)).catch(() => setPrios([]));
    api<{ decisions: any[] }>("/api/decisions").then((d) => setDecisions(d.decisions)).catch(() => setDecisions([]));
    api<{ investigations: any[] }>("/api/investigations").then((d) => setInvs(d.investigations)).catch(() => setInvs([]));
  };
  useEffect(() => { if (user) load(); }, [user?.username]);
  useEffect(() => {
    const on = () => load();
    window.addEventListener("focus", on);
    return () => window.removeEventListener("focus", on);
  }, [user?.username]);
  if (!user) return <SignInPrompt what="your priorities" />;
  const patch = (path: string, body: object) => api(path, { method: "PATCH", body: JSON.stringify(body) }).then(load);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <div className="eyebrow">My priorities</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">What needs a decision, and what you decided</h1>
        <p className="mt-1 text-ink-muted">Priorities are derived from current records. Decisions and investigations are your own notes in Flo &amp; Jerry; recording them does not execute anything in other systems.</p>
      </header>

      <section aria-labelledby="all-prio">
        <h2 id="all-prio" className="mb-3 text-xl font-semibold text-ink">Open priorities</h2>
        {!prios ? <Skeleton lines={4} /> : (
          <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{sortForLens(prios, lens).map((p) => <PriorityCard key={p.id} p={p} />)}</ol>
        )}
      </section>

      <section aria-labelledby="inv-h" className="panel">
        <h2 id="inv-h" className="text-xl font-semibold text-ink">Investigations</h2>
        <p className="text-sm text-ink-muted">Resume where you left off. Each compares today's measures with the moment you saved it.</p>
        {!invs ? <div className="mt-3"><Skeleton /></div> : invs.length === 0 ? (
          <p className="mt-3 text-sm text-ink">No investigations yet. Open a priority and choose “Save investigation”.</p>
        ) : (
          <ul className="mt-3 space-y-3" data-testid="investigations">{invs.map((i) => (
            <li key={i.id} className="rounded-xl border border-surface-line bg-midnight/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-ink">{i.title}</h3>
                <span className="chip border-surface-line text-ink-muted">{i.status}{i.still_open === false ? " · priority no longer open" : ""}</span>
              </div>
              <p className="mt-1 text-xs text-ink-faint">Saved {new Date(i.created_at).toLocaleString()} · updated {new Date(i.updated_at).toLocaleString()}</p>
              <Changes changes={i.changes} />
              <Notes value={i.notes} onSave={(notes) => patch(`/api/investigations/${i.id}`, { notes })} />
              <div className="mt-2 flex flex-wrap gap-2">
                {i.priority_id && <button className="btn-ghost text-xs" onClick={() => { const p = prios?.find((x) => x.id === i.priority_id); if (p) openInvestigation(p); }} disabled={!prios?.some((x) => x.id === i.priority_id)}>Reopen the guided panel</button>}
                <button className="btn-ghost text-xs" onClick={() => openCopilot("What happened to the quality issue we discussed last week?")}><span aria-hidden>✦</span> Ask Jerry what changed</button>
                <button className="btn-ghost text-xs" onClick={() => patch(`/api/investigations/${i.id}`, { status: i.status === "open" ? "closed" : "open" })}>{i.status === "open" ? "Close" : "Reopen"}</button>
              </div>
            </li>
          ))}</ul>
        )}
      </section>

      <section aria-labelledby="dec-h" className="panel">
        <h2 id="dec-h" className="text-xl font-semibold text-ink">Decision journal</h2>
        <p className="text-sm text-ink-muted">Problem, evidence, recommendation, decision, owner, follow-up and observed outcome — in one place.</p>
        {!decisions ? <div className="mt-3"><Skeleton /></div> : decisions.length === 0 ? (
          <p className="mt-3 text-sm text-ink">No decisions recorded yet. Open a priority and record what you decided.</p>
        ) : (
          <ul className="mt-3 space-y-3" data-testid="decisions">{decisions.map((d) => (
            <li key={d.id} className="rounded-xl border border-surface-line bg-midnight/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold text-ink">{d.title}</h3>
                <span className="chip border-surface-line text-ink-muted">{d.status}{d.follow_up_on ? ` · follow up ${d.follow_up_on}` : ""}</span>
              </div>
              <dl className="mt-2 grid gap-2 text-sm md:grid-cols-2">
                <div><dt className="text-xs text-ink-faint">Problem</dt><dd className="text-ink-muted">{d.problem || "—"}</dd></div>
                <div><dt className="text-xs text-ink-faint">Recommendation</dt><dd className="text-ink-muted">{d.recommendation || "—"}</dd></div>
                <div><dt className="text-xs text-ink-faint">Decision</dt><dd className="text-ink">{d.decision}</dd></div>
                <div><dt className="text-xs text-ink-faint">Owner</dt><dd className="text-ink-muted">{d.owner || "—"}</dd></div>
                <div><dt className="text-xs text-ink-faint">Evidence</dt><dd className="text-ink-muted">{d.evidence.map((e: any) => e.label).join("; ") || "—"}</dd></div>
                <div><dt className="text-xs text-ink-faint">Observed outcome</dt><dd className="text-ink-muted">{d.outcome ?? "Not recorded yet"}</dd></div>
              </dl>
              <Changes changes={d.comparison ?? []} />
              <p className="mt-2 text-[11px] text-ink-faint">{d.note}</p>
              {d.status === "open" && <Outcome onSave={(outcome) => patch(`/api/decisions/${d.id}`, { outcome, status: "done" })} />}
            </li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}

function Changes({ changes }: { changes: Change[] }) {
  if (!changes.length) return <p className="mt-2 text-xs text-ink-muted">No tracked measure has changed since it was saved.</p>;
  return (
    <div className="mt-2 text-xs">
      <div className="text-ink-faint">Since it was saved (side by side; not proof of cause):</div>
      <ul className="mt-1 flex flex-wrap gap-2">{changes.map((c) => (
        <li key={c.metric} className="rounded-lg border border-surface-line px-2 py-1 text-ink-muted">{c.metric.replace(/_/g, " ")}: <b className="text-ink">{String(c.then)}</b> → <b className="text-teal-soft">{String(c.now)}</b></li>
      ))}</ul>
    </div>
  );
}

function Notes({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value);
  return (
    <label className="mt-2 block text-xs text-ink-muted">Notes
      <textarea className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" rows={2} value={v} onChange={(e) => setV(e.target.value)} onBlur={() => v !== value && onSave(v)} />
    </label>
  );
}

function Outcome({ onSave }: { onSave: (v: string) => void }) {
  const [v, setV] = useState("");
  return (
    <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (v.trim()) onSave(v.trim()); }}>
      <label className="sr-only" htmlFor="outcome">Observed outcome</label>
      <input id="outcome" className="min-w-0 flex-1 rounded-lg border px-2 py-1.5 text-sm" placeholder="Observed outcome (what actually happened)" value={v} onChange={(e) => setV(e.target.value)} />
      <button className="btn-green text-xs" type="submit">Record outcome</button>
    </form>
  );
}
