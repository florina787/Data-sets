import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useApp } from "../context";
import { DeliveryDemoPanel, SystemPills } from "../components/Layout";
import { SignInPrompt, Skeleton, StatusDot } from "../components/pulse/shared";

/** Technology workspace: five plain questions first; diagnostics and technical pages one step away. */
export default function Technology() {
  const { user } = useApp();
  const [qs, setQs] = useState<any[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { if (user) api<{ questions: any[] }>("/api/technology").then((d) => setQs(d.questions)).catch(() => setQs([])); }, [user?.username]);
  if (!user) return <SignInPrompt what="technology health" />;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header>
        <div className="eyebrow">Technology</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Technology health</h1>
        <p className="mt-1 text-ink-muted">Five questions a CTO asks first. Open diagnostics only when you need them.</p>
      </header>
      {!qs ? <Skeleton lines={6} /> : (
        <ul className="grid gap-4 md:grid-cols-2" data-testid="tech-questions">
          {qs.map((q) => (
            <li key={q.key} className="panel">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-semibold text-ink">{q.question}</h2>
                <StatusDot status={q.status} />
              </div>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{q.answer}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {q.diagnostics && <button className="btn-ghost text-xs" aria-expanded={open === q.key} onClick={() => setOpen(open === q.key ? null : q.key)}>{open === q.key ? "Hide diagnostics" : "Show diagnostics"}</button>}
                <Link to={q.link} className="btn-ghost text-xs">Details →</Link>
              </div>
              {open === q.key && <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-midnight/70 p-3 text-xs text-ink-muted">{JSON.stringify(q.diagnostics, null, 2)}</pre>}
            </li>
          ))}
        </ul>
      )}
      <section className="panel space-y-3">
        <h2 className="text-lg font-semibold text-ink">Live system indicators</h2>
        <SystemPills />
      </section>
      <section className="panel space-y-3" aria-labelledby="demo-h">
        <h2 id="demo-h" className="text-lg font-semibold text-ink">Digital delivery demo</h2>
        <p className="text-sm text-ink-muted">The guided software-delivery story (brief → requirements → code → tests → approval → deployment → incident → repair) and the live demo storefront. Moved here from the global header in 3.0.</p>
        <DeliveryDemoPanel />
      </section>
      <nav aria-label="Technical pages" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[["/observability", "System Observability", "CPU, memory, model calls, token usage, agent traces"],
          ["/evaluation", "Model Evaluation Lab", "Model registry, datasets, evaluation reports"],
          ["/agents", "Agent Intelligence", "Knowledge, context and procedural graphs"],
          ["/delivery", "Digital delivery", "Runs, requirements, releases, incidents"]].map(([to, t, d]) => (
          <Link key={to} to={to} className="panel block hover:border-teal"><div className="font-semibold text-ink">{t}</div><div className="mt-1 text-xs text-ink-muted">{d}</div></Link>
        ))}
      </nav>
    </div>
  );
}
