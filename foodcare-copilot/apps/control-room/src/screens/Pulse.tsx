import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../context";
import { openInvestigation } from "../components/pulse/InvestigationPanel";
import {
  freshness, Health, Priority, ProvenanceChip, SEVERITY, SignInPrompt, Skeleton, sortForLens, StatusDot, useLens,
} from "../components/pulse/shared";
import { openCopilot } from "./Copilot";

const SupplyMap = lazy(() => import("../components/geo/SupplyMap"));

type Pulse = {
  state: { lens: string; lens_label: string; role: string; last_seen_at: string | null; note: string };
  generated_at: string; data_status: string;
  since: { since: string | null; first_visit: boolean; changes: { kind: string; text: string; link: string; provenance: any; count: number }[]; message: string | null };
  priorities: Priority[]; health: Health[]; briefing: { text: string; provenance: any }[];
};

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/** Enterprise Pulse: what changed, why it matters, what to do next. */
export default function PulsePage() {
  const { user } = useApp();
  const lens = useLens();
  const [data, setData] = useState<Pulse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tech, setTech] = useState<any[] | null>(null);
  const [showGlobe, setShowGlobe] = useState(false);

  const load = () => {
    setError(null);
    api<Pulse>("/api/pulse").then(setData).catch((e) => setError((e as Error).message));
    api<{ questions: any[] }>("/api/technology").then((t) => setTech(t.questions)).catch(() => setTech(null));
  };
  useEffect(() => { setData(null); if (user) load(); }, [user?.username]);

  if (!user) return <SignInPrompt what="your enterprise pulse" />;
  const prios = data ? sortForLens(data.priorities, lens) : [];
  const first = user.display_name.split(" ")[0];

  return (
    <div className="mx-auto max-w-7xl space-y-6" data-testid="pulse">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="eyebrow">Enterprise Pulse</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink md:text-4xl">{greeting()}, {first}.</h1>
          <p className="mt-1 text-lg text-ink-muted">Here's what changed across your enterprise.</p>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-ink-muted sm:grid-cols-4">
          <div><dt className="text-ink-faint">Workspace</dt><dd className="text-ink">{data?.state.lens_label ?? "…"}</dd></div>
          <div><dt className="text-ink-faint">Organization</dt><dd className="text-ink">Food Beverage Food Care (fictional)</dd></div>
          <div><dt className="text-ink-faint">Reporting period</dt><dd className="text-ink">Last 4 weeks</dd></div>
          <div><dt className="text-ink-faint">Last refresh</dt><dd className="text-ink">{data ? new Date(data.generated_at).toLocaleTimeString() : "…"} <button className="ml-1 text-teal hover:underline" onClick={load}>Refresh</button></dd></div>
        </dl>
      </header>
      {data && <p className="rounded-xl border border-champagne/30 bg-champagne/5 px-4 py-2 text-xs text-champagne-soft" role="note"><b>Data status:</b> {data.data_status} Every item is labelled: Verified · Operational record · Modelled · Synthetic.</p>}
      {error && <div className="panel border-risk/50 text-sm text-brick-700" role="alert">Couldn't load the pulse: {error}. <button className="text-teal underline" onClick={load}>Try again</button></div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="panel lg:col-span-2" aria-labelledby="brief-title">
          <div className="flex items-center justify-between gap-2">
            <h2 id="brief-title" className="flex items-center gap-2 text-lg font-semibold text-ink"><span aria-hidden className="text-champagne">✦</span> Jerry's executive briefing</h2>
            <button className="btn-ghost text-xs" onClick={() => openCopilot("What should I focus on before my board meeting?")}>Ask a follow-up</button>
          </div>
          {!data ? <div className="mt-4"><Skeleton lines={4} /></div> : (
            <ul className="mt-4 space-y-3" data-testid="briefing">
              {data.briefing.map((b) => (
                <li key={b.text} className="flex gap-3 text-[15px] leading-relaxed text-ink">
                  <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-champagne" />
                  <span>{b.text} <ProvenanceChip kind={b.provenance} /></span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 text-xs text-ink-faint">Built from records and labelled scenarios only. Jerry doesn't guess and never acts on its own.</p>
        </section>

        <section className="panel" aria-labelledby="since-title" data-testid="since-last-visit">
          <h2 id="since-title" className="text-lg font-semibold text-ink">Since your last visit</h2>
          {!data ? <div className="mt-4"><Skeleton /></div> : (
            <>
              <p className="mt-1 text-xs text-ink-muted">{data.since.since ? `Compared with ${new Date(data.since.since).toLocaleString()}` : "First visit"}</p>
              {data.since.changes.length === 0 ? <p className="mt-4 text-sm text-ink">{data.since.message}</p> : (
                <ul className="mt-3 space-y-2">{data.since.changes.map((c) => (
                  <li key={c.text}><Link to={c.link} className="block rounded-lg border border-surface-line bg-elevated/50 px-3 py-2 text-sm text-ink hover:border-teal">{c.text}</Link></li>
                ))}</ul>
              )}
            </>
          )}
        </section>
      </div>

      <section aria-labelledby="prio-title">
        <div className="mb-3 flex items-end justify-between">
          <h2 id="prio-title" className="text-xl font-semibold text-ink">Top priorities</h2>
          <Link to="/priorities" className="text-sm text-teal hover:underline">All priorities, decisions and investigations →</Link>
        </div>
        {!data ? <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="panel"><Skeleton lines={5} /></div>)}</div> : prios.length === 0 ? (
          <div className="panel text-sm text-ink">No open priorities. Nothing in the current records needs a decision.</div>
        ) : (
          <ol className="grid gap-4 md:grid-cols-3">
            {prios.slice(0, 3).map((p, i) => <PriorityCard key={p.id} p={p} rank={i + 1} />)}
          </ol>
        )}
      </section>

      <section aria-labelledby="health-title">
        <h2 id="health-title" className="mb-3 text-xl font-semibold text-ink">Enterprise health</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {!data ? [0, 1, 2, 3, 4].map((i) => <div key={i} className="panel"><Skeleton lines={3} /></div>) : data.health.map((h) => (
            <Link key={h.key} to={h.link} className="panel block transition-colors hover:border-teal" data-testid={`health-${h.key}`}>
              <div className="flex items-start justify-between gap-2"><span className="text-sm font-semibold text-ink">{h.label}</span><StatusDot status={h.status} /></div>
              <div className="mt-1 text-xs text-ink-faint">{h.question}</div>
              <div className="mt-3 text-base font-semibold leading-snug text-ink">{h.value}</div>
              <p className="mt-2 text-xs leading-relaxed text-ink-muted">{h.explanation}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-ink-faint"><ProvenanceChip kind={h.provenance} /> {freshness(h.as_of)}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="panel" aria-labelledby="tech-title">
        <div className="flex items-end justify-between">
          <h2 id="tech-title" className="text-xl font-semibold text-ink">Technology health</h2>
          <Link to="/technology" className="text-sm text-teal hover:underline">Open the Technology workspace →</Link>
        </div>
        {!tech ? <div className="mt-4"><Skeleton lines={5} /></div> : (
          <dl className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {tech.map((t) => (
              <div key={t.key} className="rounded-xl border border-surface-line bg-midnight/40 p-4">
                <dt className="flex items-center justify-between gap-2 text-sm font-semibold text-ink">{t.question}<StatusDot status={t.status} /></dt>
                <dd className="mt-2 text-sm leading-relaxed text-ink-muted">{t.answer}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="panel" aria-labelledby="globe-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="globe-title" className="text-xl font-semibold text-ink">Global network</h2>
            <p className="text-sm text-ink-muted">Optional exploration: the 161-country <b>synthetic</b> scenario with routes, incidents, risk ranges and OriginTrace.</p>
          </div>
          <div className="flex gap-2">
            {!showGlobe && <button className="btn-ghost" onClick={() => setShowGlobe(true)}>Explore here</button>}
            <Link to="/network" className="btn-ghost">Open Global Network</Link>
          </div>
        </div>
        {showGlobe && <div className="mt-4"><Suspense fallback={<Skeleton lines={6} />}><SupplyMap title="Global supply chain intelligence" defaultTab="financial" /></Suspense></div>}
      </section>
    </div>
  );
}

export function PriorityCard({ p, rank }: { p: Priority; rank?: number }) {
  return (
    <li className="panel flex flex-col gap-3" data-testid="priority">
      <div className="flex items-center justify-between gap-2">
        <span className={`chip ${SEVERITY[p.severity]}`}>{rank ? `#${rank} · ` : ""}{p.severity}</span>
        <ProvenanceChip kind={p.provenance} />
      </div>
      <h3 className="text-base font-semibold leading-snug text-ink">{p.title}</h3>
      <div className="space-y-2 text-sm">
        <p className="text-ink-muted"><span className="font-medium text-ink">Why it matters: </span>{p.why}</p>
        <p className="text-ink-muted"><span className="font-medium text-ink">Next step: </span>{p.next_step}</p>
        <p className="text-xs text-ink-faint">Affects {p.areas.join(", ")} · Owner: {p.owner} · {freshness(p.as_of)}</p>
      </div>
      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <button className="btn-primary" onClick={() => openInvestigation(p)}>Investigate</button>
        <button className="btn-ghost" onClick={() => openCopilot(p.jerry_question)}><span aria-hidden>✦</span> Ask Jerry</button>
      </div>
    </li>
  );
}
