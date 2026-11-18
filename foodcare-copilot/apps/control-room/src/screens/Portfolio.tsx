import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp } from "../context";
import { SignInPrompt, Skeleton } from "../components/pulse/shared";
import { VisualList } from "../components/visuals/VisualRenderer";
import { openCopilot } from "./Copilot";

const cad = (c: number) => `CAD ${(c / 100 / 1000).toFixed(0)}k`;
const STATUS: Record<string, string> = { on_track: "text-teal-soft", at_risk: "text-amber-700", delayed: "text-brick-700", blocked: "text-brick-700", done: "text-leaf-700" };

/** Enterprise Delivery & Team Intelligence: what every department is building. */
export default function Portfolio() {
  const { user } = useApp();
  const [p, setP] = useState<any>(null);
  const [dept, setDept] = useState<string>("");
  useEffect(() => { if (user) api("/api/portfolio").then(setP); }, [user?.username]);
  const items = useMemo(() => (p ? p.initiatives.filter((x: any) => !dept || x.dept === dept) : []), [p, dept]);
  if (!user) return <SignInPrompt what="the delivery portfolio" />;
  if (!p) return <Skeleton lines={8} />;
  const byId = Object.fromEntries(p.initiatives.map((x: any) => [x.id, x]));
  const gantt = { kind: "gantt", title: `${dept || "All departments"}: delivery timeline`, today: p.as_of, provenance: "synthetic",
    rows: items.slice(0, 14).map((x: any) => ({ label: x.name, group: x.dept, status: x.status,
      start: x.milestones.map((m: any) => m.planned).sort()[0], end: x.milestones.map((m: any) => m.actual ?? m.planned).sort().slice(-1)[0],
      milestones: x.milestones.map((m: any) => ({ name: m.name, date: m.actual ?? m.planned, state: m.state })) })) };
  const nodes: any[] = [], edges: any[] = [], seen = new Set<string>();
  const add = (n: any) => { if (!seen.has(n.id)) { seen.add(n.id); nodes.push(n); } };
  for (const x of items) {
    add({ id: x.id, label: x.name, group: x.dept, state: x.status });
    for (const d of x.depends_on) { add({ id: d, label: byId[d].name, group: byId[d].dept, state: byId[d].status }); edges.push({ source: d, target: x.id, label: "verified dependency" }); }
    for (const t of x.tech.slice(0, 3)) { add({ id: `t:${t.name}`, label: t.name, group: t.kind }); edges.push({ source: `t:${t.name}`, target: x.id, label: t.relation }); }
  }
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Operations · Team intelligence</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">What every team is building</h1>
          <p className="mt-1 text-ink-muted">{p.note}</p>
        </div>
        <button className="btn-primary" onClick={() => openCopilot("Jerry, summarize what every team is building and what needs my attention.")}><span aria-hidden>✦</span> Brief me</button>
      </header>
      <ul className="grid gap-3 sm:grid-cols-3 xl:grid-cols-9" aria-label="Departments">
        {Object.entries(p.departments).map(([d, v]: [string, any]) => (
          <li key={d}><button aria-pressed={dept === d} onClick={() => setDept(dept === d ? "" : d)} className={`metric-tile w-full rounded-xl border p-3 text-left ${dept === d ? "selected-glow border-teal" : "border-surface-line"}`}>
            <div className="text-[11px] uppercase tracking-[0.1em] text-ink-muted">{d}</div>
            <div className="mt-1 text-2xl font-semibold text-ink">{v.initiatives}</div>
            <div className={`text-[11px] ${v.delayed_or_blocked ? "text-brick-700" : "text-ink-faint"}`}>{v.delayed_or_blocked} delayed/blocked</div>
          </button></li>
        ))}
      </ul>
      <VisualList visuals={[gantt, { kind: "flow", title: "Cross-team dependencies and supporting technology", provenance: "synthetic", nodes: nodes.slice(0, 40), edges: edges.slice(0, 80), caption: "Dashed links are inferred (not recorded); solid links are verified." },
        { kind: "bar", title: "Budget used (% of budget)", unit: "%", provenance: "synthetic", highlight: items.filter((x: any) => x.budget_variance_pct > 0).map((x: any) => x.name),
          items: items.map((x: any) => ({ label: x.name, value: Math.round((1000 * x.spend_cents) / x.budget_cents) / 10, note: `${x.budget_variance_pct > 0 ? "+" : ""}${x.budget_variance_pct}% variance` })) }]} />
      <section className="panel">
        <h2 className="text-lg font-semibold text-ink">Decisions awaiting executive approval</h2>
        <ul className="mt-2 space-y-1 text-sm">{p.approvals.map((a: any) => <li key={a.decision} className="text-ink">• {a.decision} <span className="text-ink-faint">— due {a.due} · {a.needs}</span></li>)}</ul>
      </section>
      <section className="panel overflow-x-auto">
        <table className="table"><thead><tr><th>Initiative</th><th>Department</th><th>Owner</th><th>Status</th><th>Progress</th><th>Slip</th><th>Budget</th><th>Spend</th><th>Vendor contract</th><th>Next milestone</th></tr></thead>
          <tbody>{items.map((x: any) => <tr key={x.id}><td>{x.name}</td><td>{x.dept}</td><td>{x.owner}</td><td className={STATUS[x.status]}>{x.status.replace(/_/g, " ")}</td><td>{x.progress_pct}%</td><td>{x.schedule_slip_days} d</td><td>{cad(x.budget_cents)}</td><td>{cad(x.spend_cents)}</td><td>{x.vendor_contract ?? "—"}</td><td>{x.next_milestone?.name ?? "—"}</td></tr>)}</tbody></table>
      </section>
    </div>
  );
}
