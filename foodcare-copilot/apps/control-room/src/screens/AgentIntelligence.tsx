import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";

// Agent Intelligence: knowledge graph (what is true) -> context graph (what matters now) ->
// procedural graph (what to do next) -> agent activity (reason -> act -> trace & learn).
// Every node, edge and bar comes from the graph APIs over stored records.

type GNode = { id: string; type: string; label: string; detail?: string; degree?: number; count?: number };
type GEdge = { source: string; target: string; relation: string; detail?: string };

const KG_COLOUR: Record<string, string> = {
  product: "#f59e0b", warehouse: "#e9b95b", campaign: "#fb923c", inspection: "#f97316", supplier: "#fbbf24",
  policy: "#fcd34d", model: "#fdba74", dataset: "#facc15",
};
const CTX_COLOUR: Record<string, string> = { question: "#f8fafc", intent: "#60a5fa", entity: "#38bdf8", tool: "#818cf8", source: "#7dd3fc" };
const PROC_COLOUR: Record<string, string> = { vision: "#38bdf8", rules: "#60a5fa", outcome: "#10b981", human: "#e9b95b", decision: "#ef4444", learning: "#a78bfa" };

/** Knowledge graph: entity types in sectors around the centre; nodes in the latest context are ringed. */
function KnowledgeGraph({ nodes, edges, scope }: { nodes: GNode[]; edges: GEdge[]; scope: Set<string> }) {
  const [hover, setHover] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const W = 1000, H = 500, cx = W / 2, cy = H / 2 + 6;
  const types = [...new Set(nodes.map((n) => n.type))];
  const { pos, centres } = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = {};
    const c: Record<string, { x: number; y: number; r: number }> = {};
    types.forEach((t, ti) => {
      const group = nodes.filter((n) => n.type === t);
      const a = (ti / types.length) * Math.PI * 2 - Math.PI / 2;
      const gx = cx + Math.cos(a) * 340, gy = cy + Math.sin(a) * 165;
      const r = group.length <= 1 ? 0 : Math.min(62, 16 + group.length * 7);
      c[t] = { x: gx, y: gy, r };
      group.forEach((n, i) => {
        const b = (i / Math.max(1, group.length)) * Math.PI * 2 - Math.PI / 2;
        p[n.id] = { x: gx + Math.cos(b) * r * 1.35, y: gy + Math.sin(b) * r * 0.8 };
      });
    });
    return { pos: p, centres: c };
  }, [nodes]);
  const visible = nodes.filter((n) => !hidden.has(n.type));
  const vis = new Set(visible.map((n) => n.id));
  const linked = hover ? new Set(edges.filter((e) => e.source === hover || e.target === hover).flatMap((e) => [e.source, e.target])) : null;
  const hn = hover ? nodes.find((n) => n.id === hover) : null;
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1.5" role="group" aria-label="Entity types">
        {types.map((t) => (
          <button key={t} onClick={() => setHidden((h) => { const n = new Set(h); n.has(t) ? n.delete(t) : n.add(t); return n; })}
            aria-pressed={!hidden.has(t)} className={`pill ${hidden.has(t) ? "opacity-40" : ""}`}>
            <span className="h-2 w-2 rounded-full" style={{ background: KG_COLOUR[t] ?? "#f59e0b" }} aria-hidden />{t} · {nodes.filter((n) => n.type === t).length}
          </button>
        ))}
        <span className="pill"><span className="h-2 w-2 rounded-full ring-2 ring-ice-400" aria-hidden />in the latest context ({scope.size})</span>
      </div>
      <div className="relative overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[720px]" role="img" aria-label={`Knowledge graph with ${nodes.length} entities and ${edges.length} relations`}>
          <defs>
            <radialGradient id="kg-glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stopColor="#f59e0b" stopOpacity="0.18" /><stop offset="1" stopColor="#f59e0b" stopOpacity="0" /></radialGradient>
          </defs>
          <ellipse cx={cx} cy={cy} rx={W * 0.47} ry={H * 0.48} fill="url(#kg-glow)" />
          {types.filter((t) => !hidden.has(t)).map((t) => (
            <g key={t}>
              <ellipse cx={centres[t].x} cy={centres[t].y} rx={centres[t].r * 1.35 + 34} ry={centres[t].r * 0.8 + 28} fill={KG_COLOUR[t] ?? "#f59e0b"} opacity="0.06" />
              <text x={centres[t].x} y={centres[t].y - centres[t].r * 0.8 - 34} textAnchor="middle" fontSize="12" fontWeight="600" fill={KG_COLOUR[t] ?? "#f59e0b"} style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>{t}</text>
            </g>
          ))}
          {edges.filter((e) => vis.has(e.source) && vis.has(e.target)).map((e, i) => {
            const a = pos[e.source], b = pos[e.target];
            const on = linked ? linked.has(e.source) && linked.has(e.target) && (e.source === hover || e.target === hover) : scope.has(e.source) && scope.has(e.target);
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={on ? "#7dd3fc" : "#f59e0b"} strokeOpacity={on ? 0.9 : linked ? 0.06 : 0.22} strokeWidth={on ? 1.8 : 1} />;
          })}
          {visible.map((n) => {
            const p = pos[n.id];
            const r = 5 + Math.min(7, (n.degree ?? 0) * 0.9);
            const dim = linked && !linked.has(n.id);
            return (
              <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} opacity={dim ? 0.25 : 1} style={{ cursor: "pointer" }}>
                {scope.has(n.id) && <circle cx={p.x} cy={p.y} r={r + 5} fill="none" stroke="#38bdf8" strokeWidth="2" />}
                <circle cx={p.x} cy={p.y} r={r} fill={KG_COLOUR[n.type] ?? "#f59e0b"} stroke="#071426" strokeWidth="1.5" />
                <text x={p.x} y={p.y + r + 12} textAnchor="middle" fontSize="10" fill={scope.has(n.id) || hover === n.id ? "#f8fafc" : "#cbd5e1"}>{n.label.length > 18 ? `${n.label.slice(0, 17)}…` : n.label}</text>
              </g>
            );
          })}
        </svg>
      </div>
      {!hn && <p className="mt-1 text-xs text-navy-600">Hover a node to see what it is and how it connects.</p>}
      {hn && <p className="mt-1 text-xs text-navy-700" role="status"><b>{hn.label}</b> ({hn.type}){hn.detail ? `: ${hn.detail}` : ""}. {edges.filter((e) => e.source === hn.id || e.target === hn.id).map((e) => `${e.relation} ${(nodes.find((x) => x.id === (e.source === hn.id ? e.target : e.source))?.label) ?? ""}`).slice(0, 4).join("; ")}</p>}
    </div>
  );
}

/** Context graph: question -> intents/entities -> tools -> sources, as layered columns. */
function ContextGraph({ nodes, edges }: { nodes: GNode[]; edges: GEdge[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const cols = [["question"], ["intent", "entity"], ["tool"], ["source"]];
  const W = 1000, colX = [110, 370, 630, 870];
  const pos: Record<string, { x: number; y: number }> = {};
  let H = 120;
  cols.forEach((types, ci) => {
    const group = nodes.filter((n) => types.includes(n.type));
    H = Math.max(H, group.length * 46 + 40);
    group.forEach((n, i) => { pos[n.id] = { x: colX[ci], y: 30 + i * 46 + 23 }; });
  });
  cols.forEach((types) => {  // centre each column vertically
    const group = nodes.filter((n) => types.includes(n.type));
    const off = (H - (group.length * 46 + 20)) / 2;
    group.forEach((n) => { pos[n.id].y += off - 10; });
  });
  const headers = ["Question", "Understood as", "Tools called", "Evidence returned"];
  return (
    <svg viewBox={`0 0 ${W} ${H + 20}`} className="w-full min-w-[720px]" role="img" aria-label="Context graph of the selected answer">
      <defs>
        <radialGradient id="ctx-glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stopColor="#3b82f6" stopOpacity="0.18" /><stop offset="1" stopColor="#3b82f6" stopOpacity="0" /></radialGradient>
      </defs>
      <ellipse cx={W / 2} cy={H / 2} rx={W * 0.5} ry={H * 0.55} fill="url(#ctx-glow)" />
      {headers.map((h, i) => <text key={h} x={colX[i]} y={14} textAnchor="middle" fontSize="11" fill="#94a3b8" style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</text>)}
      {edges.map((e, i) => {
        const a = pos[e.source], b = pos[e.target];
        if (!a || !b) return null;
        const on = hover && (e.source === hover || e.target === hover);
        const mx = (a.x + b.x) / 2;
        return (
          <g key={i}>
            <path d={`M${a.x + 70} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x - 70} ${b.y}`} fill="none" stroke={on ? "#7dd3fc" : "#3b82f6"} strokeOpacity={on ? 0.95 : 0.4} strokeWidth={on ? 2 : 1.2} strokeDasharray={e.relation === "returns" ? "4 4" : undefined} />
          </g>
        );
      })}
      {nodes.map((n) => {
        const p = pos[n.id];
        if (!p) return null;
        const w = n.type === "question" ? 200 : 140;
        const label = n.label.length > (n.type === "question" ? 34 : 22) ? `${n.label.slice(0, n.type === "question" ? 33 : 21)}…` : n.label;
        return (
          <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
            <title>{`${n.type}: ${n.label}${n.detail ? ` (${n.detail})` : ""}`}</title>
            <rect x={p.x - w / 2} y={p.y - 16} width={w} height="32" rx="10" fill="#0c1e35" stroke={CTX_COLOUR[n.type] ?? "#60a5fa"} strokeWidth={hover === n.id ? 2 : 1.2} />
            <circle cx={p.x - w / 2 + 12} cy={p.y} r="4" fill={CTX_COLOUR[n.type] ?? "#60a5fa"} />
            <text x={p.x - w / 2 + 22} y={p.y + 4} fontSize="11" fill="#f1f5f9">{label}</text>
          </g>
        );
      })}
    </svg>
  );
}

const PROC_POS: Record<string, [number, number]> = {
  inspect: [90, 70], detect: [280, 70], grade: [470, 70], accept: [745, 30], review: [745, 115], reject: [745, 200],
  reimage: [745, 285], approval: [975, 200], correct: [975, 115], learn: [975, 30],
};

/** Procedural graph: the quality procedure with live counts; steps used by the latest answer glow. */
function ProceduralGraph({ nodes, edges, active }: { nodes: GNode[]; edges: GEdge[]; active: Set<string> }) {
  return (
    <svg viewBox="0 0 1060 320" className="w-full min-w-[760px]" role="img" aria-label="Procedural graph of potato quality decisions with live counts">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#10b981" /></marker>
      </defs>
      {edges.map((e, i) => {
        const [x1, y1] = PROC_POS[e.source], [x2, y2] = PROC_POS[e.target];
        const sx = x1 + 78, ex = x2 - 80;
        const mx = (sx + ex) / 2;
        const back = x2 <= x1;
        const d = back ? `M${x1} ${y1 - 20} C ${x1} ${y1 - 60}, ${x2} ${y2 + 60}, ${x2} ${y2 + 20}` : `M${sx} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${ex} ${y2}`;
        return (
          <g key={i}>
            <path d={d} fill="none" stroke="#10b981" strokeOpacity="0.55" strokeWidth="1.4" markerEnd="url(#arrow)"><title>{e.relation}</title></path>
            {!back && ex - sx >= 120 && <text x={ex - 8} y={y2 - 7} textAnchor="end" fontSize="9.5" fill="#94a3b8">{e.relation}</text>}
          </g>
        );
      })}
      {nodes.map((n) => {
        const [x, y] = PROC_POS[n.id];
        const c = PROC_COLOUR[n.type] ?? "#10b981";
        const on = active.has(n.id);
        return (
          <g key={n.id}>
            <title>{`${n.label}: ${n.count}`}</title>
            {on && <rect x={x - 84} y={y - 24} width="168" height="48" rx="14" fill="none" stroke="#38bdf8" strokeWidth="2" strokeDasharray="5 4" />}
            <rect x={x - 78} y={y - 18} width="156" height="36" rx="11" fill="#0c1e35" stroke={c} strokeWidth="1.4" />
            <text x={x - 66} y={y + 4} fontSize="11" fill="#e2e8f0">{n.label.length > 19 ? `${n.label.slice(0, 18)}…` : n.label}</text>
            <rect x={x + 40} y={y - 10} width="32" height="20" rx="6" fill={c} opacity="0.2" />
            <text x={x + 56} y={y + 4} textAnchor="middle" fontSize="11" fontWeight="600" fill={c}>{n.count}</text>
          </g>
        );
      })}
    </svg>
  );
}

/** Agent activity: swimlanes per agent over time, and the tool waterfall of one run. */
function Activity({ data }: { data: any }) {
  const runs: any[] = data.runs ?? [];
  const [sel, setSel] = useState<string | null>(null);
  if (!runs.length) return <Empty>No agent runs yet. Ask Jerry a question or inspect an image.</Empty>;
  const agents = [...new Set(runs.map((r) => r.agent))];
  const times = runs.map((r) => new Date(r.started_at).getTime());
  const t0 = Math.min(...times), t1 = Math.max(...times) + 1;
  const W = 640, laneH = 40, left = 150;
  const run = runs.find((r) => r.id === sel) ?? runs[0];
  const rStart = new Date(run.started_at).getTime();
  const total = Math.max(run.duration_ms ?? 1, ...run.tool_calls.map((t: any) => new Date(t.started_at).getTime() - rStart + (t.duration_ms ?? 0)), 1);
  return (
    <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
      <div>
        <div className="label mb-1">Swimlanes · {runs.length} most recent runs</div>
        <svg viewBox={`0 0 ${W} ${agents.length * laneH + 30}`} className="w-full" role="img" aria-label="Agent runs over time, one lane per agent">
          {agents.map((a, i) => (
            <g key={a}>
              <rect x="0" y={i * laneH + 4} width={W} height={laneH - 8} rx="10" fill="#0c1e35" />
              <text x="12" y={i * laneH + laneH / 2 + 4} fontSize="11" fill="#cbd5e1" fontFamily="ui-monospace, monospace">{a}</text>
            </g>
          ))}
          {runs.map((r) => {
            const lane = agents.indexOf(r.agent);
            const x = left + ((new Date(r.started_at).getTime() - t0) / (t1 - t0)) * (W - left - 30);
            const w = Math.max(6, Math.min(60, (r.duration_ms ?? 0) / 25));
            const c = r.status === "error" ? "#ef4444" : r.status === "declined" ? "#f59e0b" : r.agent.startsWith("vision") ? "#38bdf8" : "#2563eb";
            return (
              <rect key={r.id} x={x} y={lane * laneH + 12} width={w} height={laneH - 24} rx="5" fill={c} opacity={run.id === r.id ? 1 : 0.7}
                stroke={run.id === r.id ? "#f8fafc" : "none"} strokeWidth="1.5" style={{ cursor: "pointer" }} onClick={() => setSel(r.id)}>
                <title>{`${r.agent} · ${r.status} · ${r.duration_ms} ms · ${r.input_summary ?? ""}`}</title>
              </rect>
            );
          })}
          <text x={left} y={agents.length * laneH + 22} fontSize="10" fill="#94a3b8">{new Date(t0).toLocaleString()}</text>
          <text x={W - 30} y={agents.length * laneH + 22} fontSize="10" fill="#94a3b8" textAnchor="end">{new Date(t1).toLocaleString()}</text>
        </svg>
        <p className="text-[11px] text-navy-600">Bar width grows with run duration. Click a bar to see its steps.</p>
        <table className="table mt-3">
          <thead><tr><th>Agent</th><th>Runs</th><th>Avg ms</th><th>Max ms</th><th>Errors</th></tr></thead>
          <tbody>{data.agents.map((a: any) => <tr key={a.agent}><td className="font-mono text-xs">{a.agent}</td><td>{a.runs}</td><td>{Math.round(a.avg_ms)}</td><td>{Math.round(a.max_ms)}</td><td>{a.errors}</td></tr>)}</tbody>
        </table>
      </div>
      <div>
        <div className="label mb-1">Run waterfall</div>
        <div className="rounded-xl border border-surface-line bg-surface-card/60 p-3">
          <div className="text-sm font-semibold text-navy-900">{run.agent} · {run.duration_ms} ms</div>
          <div className="mb-2 truncate text-xs text-navy-600">{run.input_summary}</div>
          <ul className="space-y-1.5">{run.tool_calls.map((t: any) => {
            const off = Math.max(0, new Date(t.started_at).getTime() - rStart);
            return (
              <li key={t.id} className="text-xs">
                <div className="flex justify-between"><span className="font-mono text-navy-800">{t.status === "ok" ? "✓" : "✗"} {t.tool}</span><span className="font-mono text-navy-600">{t.duration_ms} ms</span></div>
                <div className="relative mt-0.5 h-2 rounded-full bg-surface-line">
                  <span className="absolute h-2 rounded-full bg-ice-400" style={{ left: `${(off / total) * 100}%`, width: `${Math.max(1.5, ((t.duration_ms ?? 0) / total) * 100)}%` }} />
                </div>
              </li>
            );
          })}</ul>
        </div>
        <div className="label mb-1 mt-4">Most-used tools</div>
        <ul className="space-y-1">{data.tools.map((t: any) => {
          const max = Math.max(...data.tools.map((x: any) => x.calls));
          return (
            <li key={t.tool} className="grid grid-cols-[150px_1fr_auto] items-center gap-2 text-xs">
              <span className="truncate font-mono text-navy-800">{t.tool}</span>
              <span className="h-2 rounded-full bg-surface-line"><span className="block h-2 rounded-full bg-royal-500" style={{ width: `${(t.calls / max) * 100}%` }} /></span>
              <span className="font-mono text-navy-600">{t.calls} · {Math.round(t.avg_ms)} ms</span>
            </li>
          );
        })}</ul>
      </div>
    </div>
  );
}

function Layer({ tone, step, title, question, children, aside }: { tone: string; step: string; title: string; question: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="card relative overflow-hidden" aria-label={title}>
      <div className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full blur-3xl" style={{ background: tone, opacity: 0.12 }} aria-hidden />
      <div className="relative mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="label" style={{ color: tone }}>{step}</div>
          <h2 className="text-lg font-semibold text-navy-900">{title} <span className="font-normal text-navy-600">· {question}</span></h2>
        </div>
        {aside}
      </div>
      <div className="relative overflow-x-auto">{children}</div>
    </section>
  );
}

export default function AgentIntelligence() {
  const [runId, setRunId] = useState<string>("");
  const kg = usePoll<{ nodes: GNode[]; edges: GEdge[] }>("/api/graphs/knowledge", 30000);
  const ctx = usePoll<any>(`/api/graphs/context${runId ? `?run=${runId}` : ""}`, 15000);
  const proc = usePoll<{ nodes: GNode[]; edges: GEdge[] }>("/api/graphs/procedure", 15000);
  const act = usePoll<any>("/api/agents/activity?limit=60", 10000);
  const scope = new Set<string>(ctx.data?.scope?.knowledge_nodes ?? []);
  const steps = new Set<string>(ctx.data?.scope?.procedure_steps ?? []);
  const spine = [
    { name: "Ontology", what: "What things are", value: `${new Set((kg.data?.nodes ?? []).map((n) => n.type)).size} entity types`, tone: "#94a3b8" },
    { name: "Knowledge graph", what: "What is true", value: `${kg.data?.nodes.length ?? "–"} entities · ${kg.data?.edges.length ?? "–"} relations`, tone: "#f59e0b" },
    { name: "Context graph", what: "What matters now", value: ctx.data?.run ? `${ctx.data.nodes.length} nodes in scope` : "no answer yet", tone: "#38bdf8" },
    { name: "Procedural graph", what: "What to do next", value: `${proc.data?.nodes.length ?? "–"} steps, approval-gated`, tone: "#10b981" },
    { name: "AI agents", what: "Reason → act → learn", value: `${act.data?.runs?.length ?? 0} recent runs`, tone: "#2563eb" },
  ];
  const error = kg.error || ctx.error || proc.error || act.error;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Agent Intelligence</h1>
          <p className="text-sm text-navy-600"><span className="text-gold-300">What is true</span> → <span className="text-ice-300">what matters now</span> → <span className="text-leaf-600">what to do next</span>. Built live from stored records and Jerry's recorded runs.</p>
        </div>
        <AskButton question="Is there enough apple stock for the Ontario weekend campaign?" label="Ask Jerry and watch the graphs" />
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5" aria-label="Semantic spine">
        {spine.map((s, i) => (
          <li key={s.name} className="relative rounded-2xl border border-surface-line bg-surface-card/70 p-3">
            <div className="flex items-center gap-2"><span className="grid h-6 w-6 place-items-center rounded-full text-[11px] font-semibold text-surface-base" style={{ background: s.tone }}>{i + 1}</span><span className="text-sm font-semibold text-navy-900">{s.name}</span></div>
            <div className="mt-1 text-xs text-navy-600">{s.what}</div>
            <div className="mt-1 font-mono text-xs text-navy-800">{s.value}</div>
          </li>
        ))}
      </ol>
      <Layer tone="#f59e0b" step="1 · Knowledge graph" title="Enterprise memory" question="what is true?"
        aside={<span className="text-[11px] text-navy-600">Hover a node for its relations; toggle types above the graph.</span>}>
        {!kg.data ? <Empty>Loading…</Empty> : kg.data.nodes.length === 0 ? <Empty>No entities yet.</Empty> : <KnowledgeGraph nodes={kg.data.nodes} edges={kg.data.edges} scope={scope} />}
      </Layer>
      <Layer tone="#38bdf8" step="2 · Context graph" title="The slice Jerry used" question="what matters now?"
        aside={ctx.data?.runs?.length ? (
          <label className="pill">Answer
            <select className="max-w-[280px] bg-transparent text-navy-900" value={runId || ctx.data?.run?.id} onChange={(e) => setRunId(e.target.value)}>
              {ctx.data.runs.map((r: any) => <option key={r.id} value={r.id}>{(r.question ?? "").slice(0, 60)}</option>)}
            </select></label>) : undefined}>
        {!ctx.data ? <Empty>Loading…</Empty> : !ctx.data.run ? <Empty>Ask Jerry a question to see the context graph of the answer.</Empty> : (
          <>
            <ContextGraph nodes={ctx.data.nodes} edges={ctx.data.edges} />
            <p className="mt-1 text-xs text-navy-600">Run {ctx.data.run.id} · {ctx.data.run.mode === "live" ? "written by the local model" : "deterministic answer"} · {ctx.data.run.duration_ms} ms · used {scope.size} knowledge-graph node(s), ringed in blue above{steps.size ? `; procedure steps ${[...steps].join(", ")}` : ""}.</p>
          </>
        )}
      </Layer>
      <Layer tone="#10b981" step="3 · Procedural graph" title="Potato quality procedure" question="what do I do next?"
        aside={<Link to="/quality-intel" className="text-xs text-ice-300 underline-offset-2 hover:underline">Open Quality Intelligence</Link>}>
        {!proc.data ? <Empty>Loading…</Empty> : <ProceduralGraph nodes={proc.data.nodes} edges={proc.data.edges} active={steps} />}
        <p className="text-[11px] text-navy-600">Counts are live. A Not Good grade never rejects stock by itself: it always routes to human approval, and corrections feed Trace &amp; learn.</p>
      </Layer>
      <Layer tone="#2563eb" step="4 · AI agents" title="Agent activity" question="reason → act → trace & learn">
        {!act.data ? <Empty>Loading…</Empty> : <Activity data={act.data} />}
      </Layer>
    </div>
  );
}
