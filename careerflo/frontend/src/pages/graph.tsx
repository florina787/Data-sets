import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, BookOpenCheck, Compass, Network, Route, Sparkles, Workflow } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AgentCursor } from "@/components/art/AgentCursor";
import { TrialMeter, type Job } from "@/components/career";
import { Button, Card, Empty, ErrorNote, Pill } from "@/components/ui";
import { api } from "@/lib/api";
import { useMetered } from "@/lib/hooks";
import { cn } from "@/lib/utils";

type GNode = { id: string; label: string; type: string; source: string; state?: string };
type GEdge = { source: string; target: string; relation: string; detail?: string };

const KG_COLORS: Record<string, string> = {
  Person: "#101828", Skill: "#F5A35C", Employer: "#E8742B", Education: "#D9614A", Certification: "#F59E0B",
  Job: "#F97066", Company: "#C2552B", Recruiter: "#B9845A", Application: "#7357FF",
};

// ---------------------------------------------------------------- layer 1: knowledge graph (radial, warm)
function KnowledgeGraph({ nodes, edges }: { nodes: GNode[]; edges: GEdge[] }) {
  const W = 900, H = 380, cx = W / 2, cy = H / 2 + 6;
  const pos = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = { person: { x: cx, y: cy } };
    const rings: [string[], number, number][] = [
      [["Employer", "Education", "Certification", "Recruiter"], 95, 0.4],
      [["Job", "Company"], 160, 1.3],
      [["Skill"], 215, 0.15],
    ];
    for (const [types, r, offset] of rings) {
      const ns = nodes.filter((n) => types.includes(n.type));
      ns.forEach((n, i) => {
        const a = offset + (i / Math.max(1, ns.length)) * Math.PI * 2;
        const rr = r + (n.type === "Skill" ? (i % 3) * 16 : 0);
        p[n.id] = { x: cx + rr * Math.cos(a) * 1.75, y: cy + rr * Math.sin(a) * 0.78 };
      });
    }
    return p;
  }, [nodes, cx, cy]);
  const deg: Record<string, number> = {};
  edges.forEach((e) => { deg[e.source] = (deg[e.source] || 0) + 1; deg[e.target] = (deg[e.target] || 0) + 1; });
  // Greedy label placement: most important first, skip any label that would overlap one already placed.
  const priority = (n: GNode) => (n.type === "Person" ? 0 : n.type === "Employer" || n.type === "Education" ? 1 : n.type === "Job" ? 2 : n.type === "Skill" ? 3 - (deg[n.id] || 0) / 100 : 4);
  const labels: { id: string; x: number; y: number; w: number; text: string; bold: boolean }[] = [];
  for (const n of [...nodes].filter((n) => n.type !== "Recruiter" && n.type !== "Company").sort((a, b) => priority(a) - priority(b))) {
    const p = pos[n.id];
    if (!p || labels.length >= 22) continue;
    const text = n.label.length > 24 ? n.label.slice(0, 23) + "…" : n.label;
    const w = text.length * 6.3 + 18;
    const box = { x: p.x - w / 2, y: p.y - 30, w };
    const hit = labels.some((l) => box.x < l.x + l.w + 4 && box.x + w + 4 > l.x && Math.abs(box.y - l.y) < 24);
    if (!hit) labels.push({ id: n.id, ...box, text, bold: n.type === "Person" });
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Knowledge graph with ${nodes.length} facts`}>
      <defs>
        <radialGradient id="kgglow"><stop offset="0" stopColor="#FDBA74" stopOpacity=".45" /><stop offset="1" stopColor="#FDBA74" stopOpacity="0" /></radialGradient>
      </defs>
      <ellipse cx={cx} cy={cy} rx={W / 2.05} ry={H / 2.1} fill="url(#kgglow)" />
      {edges.map((e, i) => {
        const a = pos[e.source], b = pos[e.target];
        return a && b ? <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#F59E0B" strokeOpacity=".28" strokeWidth={1} /> : null;
      })}
      {nodes.map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const r = n.type === "Person" ? 14 : Math.min(11, 4 + (deg[n.id] || 0) * 0.9);
        return (
          <g key={n.id}>
            <title>{`${n.type}: ${n.label} (source: ${n.source})`}</title>
            <circle cx={p.x} cy={p.y} r={r} fill={KG_COLORS[n.type] ?? "#F5A35C"} stroke="white" strokeWidth={1.5} />
          </g>
        );
      })}
      {labels.map((l) => (
        <g key={"l" + l.id} transform={`translate(${l.x} ${l.y})`}>
          <rect width={l.w} height={20} rx={6} fill="white" stroke="#F5A35C" strokeOpacity=".7" />
          <text x={l.w / 2} y={14} textAnchor="middle" fontSize={11} fill="#101828" fontWeight={l.bold ? 700 : 500}>{l.text}</text>
        </g>
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------- funnel connector
function ScopeFunnel({ kept, of }: { kept: number; of: number }) {
  return (
    <div className="relative mx-auto -my-2 flex max-w-3xl items-center justify-center">
      <svg viewBox="0 0 600 90" className="h-20 w-full max-w-xl" aria-hidden>
        <defs><linearGradient id="fun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#FDBA74" stopOpacity=".55" /><stop offset="1" stopColor="#93C5FD" stopOpacity=".6" /></linearGradient></defs>
        <path d="M60 0 C 220 10, 250 60, 270 90 L 330 90 C 350 60, 380 10, 540 0 Z" fill="url(#fun)" />
        {Array.from({ length: 14 }).map((_, i) => <circle key={i} cx={240 + (i % 7) * 20} cy={12 + Math.floor(i / 7) * 34} r={3} fill={i % 3 ? "#F59E0B" : "#60A5FA"} opacity=".8" />)}
      </svg>
      <p className="muted absolute right-0 top-2 hidden max-w-[14rem] text-[11.5px] md:block">Don't retrieve everything. Scope the graph to what this decision needs — <b>{kept} of {of}</b> facts kept.</p>
    </div>
  );
}

// ---------------------------------------------------------------- layer 2: context graph (focused, blue)
const STATE_FILL: Record<string, string> = { matched: "#10B981", gap: "#F97066", nice_to_have: "#94A3B8" };

function ContextGraph({ ctx }: { ctx: any }) {
  const W = 900, H = 340, cx = W / 2, cy = H / 2;
  const nodes: GNode[] = ctx.nodes;
  const jobId = `job:${ctx.focus.job_id}`;
  const skills = nodes.filter((n) => n.type === "Skill");
  const others = nodes.filter((n) => !["Skill", "Job"].includes(n.type));
  const pos: Record<string, { x: number; y: number }> = { [jobId]: { x: cx, y: cy } };
  skills.forEach((n, i) => {
    const a = -Math.PI / 2 + (i / skills.length) * Math.PI * 2;
    pos[n.id] = { x: cx + 250 * Math.cos(a), y: cy + 120 * Math.sin(a) };
  });
  others.forEach((n, i) => {
    const a = Math.PI / 6 + (i / Math.max(1, others.length)) * Math.PI * 2;
    pos[n.id] = { x: cx + 130 * Math.cos(a), y: cy + 70 * Math.sin(a) };
  });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Context graph scoped to the target job">
      <defs><radialGradient id="ctxglow"><stop offset="0" stopColor="#93C5FD" stopOpacity=".5" /><stop offset="1" stopColor="#93C5FD" stopOpacity="0" /></radialGradient></defs>
      <ellipse cx={cx} cy={cy} rx={W / 2.1} ry={H / 2.05} fill="url(#ctxglow)" />
      {ctx.edges.map((e: GEdge, i: number) => {
        const a = pos[e.source], b = pos[e.target];
        return a && b ? <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#3B82F6" strokeOpacity=".3" strokeDasharray={e.relation === "PREFERS" ? "4 4" : undefined} /> : null;
      })}
      {nodes.filter((n) => n.id !== jobId).map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const text = n.label.length > 22 ? n.label.slice(0, 21) + "…" : n.label;
        const w = text.length * 6.4 + 26;
        const fill = n.type === "Skill" ? STATE_FILL[n.state ?? "matched"] : n.type === "Person" ? "#101828" : n.type === "Application" ? "#7357FF" : "#3B82F6";
        return (
          <g key={n.id} transform={`translate(${p.x - w / 2} ${p.y - 12})`}>
            <title>{`${n.type}: ${n.label}${n.state ? ` (${n.state.replace(/_/g, " ")})` : ""}`}</title>
            <rect width={w} height={24} rx={8} fill="white" stroke={fill} strokeWidth={1.4} />
            <circle cx={11} cy={12} r={4} fill={fill} />
            <text x={20} y={16} fontSize={11.5} fill="#101828">{text}</text>
          </g>
        );
      })}
      <g transform={`translate(${cx} ${cy})`}>
        <circle r={52} fill="white" stroke="#3B82F6" strokeWidth={2} />
        <text y={-6} textAnchor="middle" fontSize={11} fontWeight={700} fill="#101828">{ctx.focus.title.length > 18 ? ctx.focus.title.slice(0, 17) + "…" : ctx.focus.title}</text>
        <text y={11} textAnchor="middle" fontSize={10} fill="#64748b">{ctx.focus.company.length > 20 ? ctx.focus.company.slice(0, 19) + "…" : ctx.focus.company}</text>
        <text y={27} textAnchor="middle" fontSize={11} fontWeight={700} fill="#7357FF">{Math.round(ctx.match.score)}/100</text>
      </g>
    </svg>
  );
}

// ---------------------------------------------------------------- layer 3: procedural graph (flow)
const P: Record<string, [number, number]> = {
  upload_resume: [80, 50], discover: [240, 50], check_fit: [400, 50], close_gaps: [560, 50], tailor_resume: [720, 50], ats_check: [880, 50],
  upskill: [400, 170], you_decide: [560, 170], approve_submit: [720, 170], cover_letter: [880, 170],
  negotiate: [240, 290], offer: [400, 290], interview_prep: [560, 290], applied: [720, 290], follow_up: [880, 290],
};
const BW = 136, BH = 42;

function trim(ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax, dy = by - ay;
  const t = Math.min((BW / 2 + 6) / Math.abs(dx || 1e-6), (BH / 2 + 6) / Math.abs(dy || 1e-6));
  return { x1: ax + dx * Math.min(t, 0.5), y1: ay + dy * Math.min(t, 0.5), x2: bx - dx * Math.min(t, 0.5), y2: by - dy * Math.min(t, 0.5) };
}

function ProcedureGraph({ proc }: { proc: any }) {
  const byId = Object.fromEntries(proc.nodes.map((n: any) => [n.id, n]));
  const style = (s: string) => ({
    current: { fill: "#7357FF", text: "white", stroke: "#7357FF" }, done: { fill: "#ECFDF5", text: "#065F46", stroke: "#10B981" },
    next: { fill: "white", text: "#0369A1", stroke: "#38BDF8" }, todo: { fill: "white", text: "#64748b", stroke: "#CBD5E1" },
  } as Record<string, any>)[s];
  return (
    <svg viewBox="0 0 960 340" className="w-full" role="img" aria-label={`Procedural graph, current step ${proc.guidance.step}`}>
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#94A3B8" /></marker>
        <marker id="arrT" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#7357FF" /></marker>
      </defs>
      {proc.edges.map((e: any, i: number) => {
        const [ax, ay] = P[e.source], [bx, by] = P[e.target];
        const t = trim(ax, ay, bx, by);
        const fromCurrent = e.source === proc.current;
        const long = Math.abs(bx - ax) > 200 && ay === by;
        const d = long ? `M${ax} ${ay + BH / 2} Q ${(ax + bx) / 2} ${ay + 60} ${bx} ${by + BH / 2 + 4}` : `M${t.x1} ${t.y1} L${t.x2} ${t.y2}`;
        return (
          <g key={i}>
            <title>{`${byId[e.source].label} → ${byId[e.target].label}: ${e.condition}`}</title>
            <path d={d} fill="none" stroke={e.taken || fromCurrent ? "#7357FF" : "#CBD5E1"} strokeWidth={e.taken || fromCurrent ? 2 : 1.3}
              strokeDasharray={fromCurrent && !e.taken ? "5 4" : undefined} markerEnd={`url(#${e.taken || fromCurrent ? "arrT" : "arr"})`} />
            {fromCurrent && <text x={(t.x1 + t.x2) / 2 + 4} y={(t.y1 + t.y2) / 2 - 5} fontSize={10} fill="#7357FF">{e.condition}</text>}
          </g>
        );
      })}
      {proc.nodes.map((n: any) => {
        const [x, y] = P[n.id];
        const s = style(n.state);
        return (
          <g key={n.id} transform={`translate(${x - BW / 2} ${y - BH / 2})`}>
            <title>{`${n.label} — ${n.state}${n.kind === "human" ? " (needs you)" : ""}`}</title>
            <rect width={BW} height={BH} rx={12} fill={s.fill} stroke={s.stroke} strokeWidth={n.state === "current" ? 2 : 1.3} strokeDasharray={n.state === "next" ? "4 3" : undefined} />
            {n.kind === "human" && <g transform={`translate(${BW - 14} -7)`}><rect x={-22} width={36} height={14} rx={7} fill="#F59E0B" /><text x={-4} y={10} textAnchor="middle" fontSize={8.5} fontWeight={700} fill="white">YOU</text></g>}
            <text x={BW / 2} y={BH / 2 + 4} textAnchor="middle" fontSize={12} fontWeight={n.state === "current" ? 700 : 500} fill={s.text}>
              {n.state === "done" ? "✓ " : ""}{n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------- page
function Layer({ n, title, q, tone, icon, children, aside }: { n: number; title: string; q: string; tone: string; icon: React.ReactNode; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <motion.section initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: n * 0.05 }} className="card relative p-6">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={cn("grid h-9 w-9 place-items-center rounded-xl text-white", tone)}>{icon}</span>
          <div><p className="text-[15px] font-semibold">{title}</p><p className="muted text-[12.5px]">{q}</p></div>
        </div>
        {aside}
      </div>
      {children}
    </motion.section>
  );
}

export function CareerGraph() {
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<{ jobs: Job[] }>("/api/jobs/saved") });
  const [job, setJob] = useState("");
  const build = useMetered("/api/career-graph");
  const g = build.data;
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mx-auto mb-8 max-w-2xl pt-6 text-center">
        <p className="eyebrow">Career Graph</p>
        <h1 className="display mt-2">Knowledge. Context. Procedure.</h1>
        <p className="mt-3 text-[17px] font-medium text-amber-600">What's true → What matters now → What do I do next</p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <select aria-label="Focus job" className="h-10 max-w-xs rounded-full bg-white px-4 text-sm ring-1 ring-black/10 dark:bg-white/5" value={job} onChange={(e) => setJob(e.target.value)}>
            <option value="">Focus: my most active job</option>
            {saved.data?.jobs.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}
          </select>
          <Button variant="violet" loading={build.isPending} onClick={() => build.mutate(job ? { job_id: job } : {})}><Network className="h-4 w-4" />Build my career graph</Button>
        </div>
        <div className="mt-3 flex justify-center"><TrialMeter feature="career_graph" /></div>
      </div>
      <ErrorNote error={build.error} />
      {!g ? (
        <Empty art={<div className="relative"><Network className="h-16 w-16 text-amber-500" /><AgentCursor label="Procedural guidance" tone="violet" className="-right-36 -top-3" /></div>}
          title="Three graphs, one next step" body="Your verified facts become a knowledge graph, the job you're focused on becomes a small context graph, and a procedure graph tells you — with reasons — what to do next." />
      ) : (
        <div className="space-y-4">
          <Layer n={1} title="Knowledge Graph" q="What is true? Stable, verified facts — each with its source." tone="bg-orange-500" icon={<BookOpenCheck className="h-4 w-4" />}
            aside={<div className="flex max-w-md flex-wrap justify-end gap-1">{Object.entries(g.knowledge.counts).map(([t, c]) => <Pill key={t}><span className="h-2 w-2 rounded-full" style={{ background: KG_COLORS[t] }} />{t} {c as number}</Pill>)}</div>}>
            <KnowledgeGraph nodes={g.knowledge.nodes} edges={g.knowledge.edges} />
          </Layer>

          {g.context.focus ? <ScopeFunnel kept={g.context.scope.kept} of={g.context.scope.of} /> : null}

          <Layer n={2} title="Context Graph" q="What matters now? A small subgraph for this decision, with live state." tone="bg-blue-500" icon={<Compass className="h-4 w-4" />}
            aside={g.context.focus?.synthetic && <Pill tone="amber">synthetic demo job</Pill>}>
            {g.context.focus ? (
              <>
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {g.context.live_state.map((s: any) => <Pill key={s.key} tone={s.tone === "neutral" ? undefined : s.tone}>{s.label}</Pill>)}
                </div>
                <ContextGraph ctx={g.context} />
                <p className="muted mt-1 text-center text-[11.5px]"><span className="text-emerald-600">●</span> skill you have · <span className="text-red-500">●</span> required gap · <span className="text-slate-400">●</span> nice to have — {g.context.note}</p>
              </>
            ) : <Empty title="No focus job yet" body={g.context.message} action={<Link to="/app/jobs"><Button size="sm">Find jobs</Button></Link>} />}
          </Layer>

          <Layer n={3} title="Procedural Graph" q="What do I do next? (procedure, condition, procedure) triplets — guides, never dictates." tone="bg-emerald-500" icon={<Workflow className="h-4 w-4" />}>
            <div className="relative">
              <ProcedureGraph proc={g.procedure} />
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-5">
              <div className="rounded-2xl bg-violet/10 p-5 md:col-span-3">
                <p className="text-[11px] font-semibold uppercase tracking-[.14em] text-violet">Next step</p>
                <p className="mt-1 font-serif text-3xl">{g.procedure.guidance.step}</p>
                <p className="mt-2 text-[13.5px]">{g.procedure.guidance.why}</p>
                <Link to={g.procedure.guidance.link}><Button size="sm" variant="violet" className="mt-4">Go <ArrowRight className="h-3.5 w-3.5" /></Button></Link>
              </div>
              <div className="rounded-2xl bg-slate-50 p-5 text-[13px] md:col-span-2 dark:bg-white/5">
                <p className="font-semibold">Possible transitions</p>
                <ul className="mt-2 space-y-1.5">{g.procedure.guidance.options.map((o: any) => <li key={o.step} className="flex items-start gap-2"><Route className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-500" /><span><b>{o.step}</b> <span className="muted">if {o.condition}</span></span></li>)}</ul>
                <p className="muted mt-3 text-[11.5px]">{g.procedure.guidance.deviation}</p>
              </div>
            </div>
          </Layer>

          <Layer n={4} title="Trace & Learn" q="Success and failure traces from your own history update the guidance." tone="bg-ink" icon={<Sparkles className="h-4 w-4" />}
            aside={g.learn.contains_synthetic && <Pill tone="amber">includes synthetic demo records</Pill>}>
            <div className="grid gap-4 md:grid-cols-3">
              {g.learn.lessons.map((l: any) => (
                <div key={l.factor} className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5">
                  <p className="text-[13px] font-semibold">{l.factor}</p>
                  {[["with", l.with, l.n_with, "#10B981"], ["without", l.without, l.n_without, "#CBD5E1"]].map(([k, v, n, c]) => (
                    <div key={k as string} className="mt-2 text-[12px]">
                      <div className="flex justify-between"><span className="muted">{k as string} (n={n as number})</span><span className="tabular-nums">{v == null ? "—" : `${Math.round((v as number) * 100)}%`}</span></div>
                      <div className="mt-1 h-2 rounded-full bg-slate-200 dark:bg-white/10"><div className="h-2 rounded-full" style={{ width: `${Math.round(((v as number) ?? 0) * 100)}%`, background: c as string }} /></div>
                    </div>
                  ))}
                  <p className="muted mt-2 text-[11.5px]">{l.insight}</p>
                </div>
              ))}
              <div className="rounded-2xl bg-slate-50 p-4 text-[12.5px] dark:bg-white/5">
                <p className="text-[13px] font-semibold">Agent traces</p>
                <ul className="mt-2 space-y-1">
                  <li>{g.learn.traces.agent_runs} workflow runs · {g.learn.traces.completed} completed · {g.learn.traces.failed} failed</li>
                  <li>{g.learn.traces.approvals_approved} approvals granted · {g.learn.traces.approvals_rejected} declined</li>
                  <li className="muted">Response rates come from {g.learn.applications_considered} submitted applications.</li>
                </ul>
              </div>
            </div>
          </Layer>

          <div className="card p-5">
            <p className="mb-3 text-center text-[13px] font-semibold text-violet">The Semantic Spine</p>
            <div className="flex flex-col items-stretch gap-2 md:flex-row md:items-center">
              {g.spine.map((s: any, i: number) => (
                <div key={s.layer} className="flex flex-1 items-center gap-2">
                  <div className={cn("flex-1 rounded-2xl p-3 text-center ring-1",
                    ["ring-slate-300 bg-white", "ring-orange-300 bg-orange-50", "ring-blue-300 bg-blue-50", "ring-emerald-300 bg-emerald-50", "ring-violet/40 bg-violet/10"][i], "dark:bg-white/5")}>
                    <p className="text-[13px] font-semibold">{s.layer}</p>
                    <p className="muted text-[11px]">({s.role}) · {s.question}</p>
                    <p className="mt-1 text-[12px] font-medium">{s.value}</p>
                  </div>
                  {i < g.spine.length - 1 && <ArrowRight className="hidden h-4 w-4 shrink-0 text-slate-400 md:block" />}
                </div>
              ))}
            </div>
          </div>
          <Card className="p-4 text-center"><p className="muted text-[12px]">Every fact is computed from your own records — no model invents graph facts. Consequential steps (submitting, emailing, sharing, deleting) always wait for your approval.</p></Card>
        </div>
      )}
    </div>
  );
}
