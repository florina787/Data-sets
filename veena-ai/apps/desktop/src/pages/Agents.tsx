import { ArrowRight, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CatMark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, CardHeader, cn, Select } from "../components/ui";
import { useApp } from "../stores/app";

type Outcome = "resolved" | "flagged" | "escalated" | "cancelled" | "failed";
interface GraphData {
  nodes: { id: string; used?: boolean; count?: number; degree?: number; type?: string }[];
  edges: { a: string; b: string; weight: number }[];
}
interface Scorecard {
  days: number;
  turns: number;
  outcomes: Record<Outcome, number>;
  success_rate: number | null;
  ontology: Record<string, number>;
  knowledge: { support_rate: number | null; measured_turns: number; claims: number; unsupported_figures: number };
  context: { utilization: number | null; citation_rate: number | null; mean_nodes: number | null; latest: { graph: GraphData; sources: string[]; agent: string; at: string } | null };
  procedure: { adherence: number | null; graph: Record<string, string[]>; labels: Record<string, string>; transitions: { from: string; to: string; count: number }[] };
  agents: {
    agent: string;
    turns: number;
    success_rate: number | null;
    support_rate: number | null;
    utilization: number | null;
    citation_rate: number | null;
    adherence: number | null;
    p50_ms: number | null;
  }[];
  daily: { day: string; turns: number; success_rate: number | null; support_rate: number | null }[];
  recent: {
    id: number;
    agent: string;
    outcome: Outcome;
    adherent: boolean;
    path: string[];
    support_rate: number | null;
    unsupported: string[];
    total_ms: number | null;
    at: string;
  }[];
}
interface KG extends GraphData {
  ontology: Record<string, number>;
  entities: number;
  passages: number;
}

const AXIS = { stroke: "var(--color-caramel)", fontSize: 11, tickLine: false };
const TT = { contentStyle: { background: "var(--color-white)", border: "1px solid var(--color-cream)", borderRadius: 10, fontSize: 12, color: "var(--color-bark)" } };
const OUTCOME_LABEL: Record<Outcome, string> = { resolved: "Resolved", flagged: "Flagged", escalated: "Escalated", cancelled: "Stopped", failed: "Failed" };
const OUTCOME_SHADE: Record<Outcome, string> = { resolved: "bg-caramel", flagged: "bg-ginger", escalated: "bg-sand", cancelled: "bg-cream", failed: "bg-bark" };

const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const agentName = (a: string) => a.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase());

/** One step of the semantic spine: what the layer answers, and its measured number. */
function SpineCard({ title, kind, question, value, detail, last }: { title: string; kind: string; question: string; value: string; detail: string; last?: boolean }) {
  return (
    <div className="flex min-w-0 flex-1 items-stretch gap-2">
      <Card className="flex min-w-0 flex-1 flex-col p-4">
        <span className="text-[11px] font-medium tracking-wide text-caramel uppercase">{kind}</span>
        <span className="mt-0.5 text-sm font-semibold text-espresso">{title}</span>
        <span className="text-xs text-mocha">{question}</span>
        <span className="mt-3 text-2xl font-semibold text-bark tabular-nums">{value}</span>
        <span className="mt-0.5 text-[11px] leading-snug text-caramel">{detail}</span>
      </Card>
      {!last && <ArrowRight size={16} className="hidden shrink-0 self-center text-sand lg:block" aria-hidden />}
    </div>
  );
}

/** Circle layout of an entity graph. Highlighted nodes are the ones the answer used. */
function EntityGraph({ data, label, highlight }: { data: GraphData; label: string; highlight?: (id: string) => boolean }) {
  const W = 520;
  const H = 340;
  const nodes = data.nodes.slice(0, 28);
  const pos = useMemo(() => {
    const m = new Map<string, { x: number; y: number }>();
    nodes.forEach((n, i) => {
      // Two rings so labels have room: the most connected entities sit inside.
      const inner = i < Math.min(8, Math.ceil(nodes.length / 3));
      const ring = inner ? nodes.slice(0, Math.min(8, Math.ceil(nodes.length / 3))) : nodes.slice(Math.min(8, Math.ceil(nodes.length / 3)));
      const k = inner ? i : i - (nodes.length - ring.length);
      const r = inner ? 70 : 140;
      const a = (2 * Math.PI * k) / Math.max(1, ring.length) - Math.PI / 2 + (inner ? 0.3 : 0);
      m.set(n.id, { x: W / 2 + r * 1.35 * Math.cos(a), y: H / 2 + r * Math.sin(a) });
    });
    return m;
  }, [nodes]);
  const maxW = Math.max(1, ...data.edges.map((e) => e.weight));
  if (!nodes.length) return null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={label}>
      {data.edges.map((e) => {
        const a = pos.get(e.a);
        const b = pos.get(e.b);
        if (!a || !b) return null;
        return <line key={e.a + e.b} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--color-sand)" strokeOpacity={0.35 + (0.5 * e.weight) / maxW} strokeWidth={0.8 + (2 * e.weight) / maxW} />;
      })}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        const on = highlight ? highlight(n.id) : true;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={on ? 8 : 4.5} fill={on ? "var(--color-ginger)" : "var(--color-ivory)"} stroke={on ? "var(--color-mocha)" : "var(--color-sand)"} strokeWidth={on ? 2 : 1} />
            <text x={p.x} y={p.y - 11} textAnchor="middle" fontSize={10.5} fill={on ? "var(--color-bark)" : "var(--color-caramel)"} fontWeight={on ? 600 : 400}>
              {n.id.length > 22 ? n.id.slice(0, 21) + "…" : n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

const STEP_POS: Record<string, { x: number; y: number }> = {
  start: { x: 40, y: 120 },
  supervisor: { x: 140, y: 120 },
  screen_prep: { x: 270, y: 45 },
  retrieve: { x: 400, y: 120 },
  compose: { x: 530, y: 120 },
  generate: { x: 660, y: 120 },
  govern: { x: 790, y: 120 },
  resolved: { x: 920, y: 45 },
  flagged: { x: 920, y: 120 },
  escalated: { x: 920, y: 195 },
  cancelled: { x: 790, y: 215 },
  failed: { x: 530, y: 215 },
};

/** The orchestration as a procedural graph, with how often each step led to the next. */
function ProcedureGraph({ sc }: { sc: Scorecard }) {
  const counts = new Map(sc.procedure.transitions.map((t) => [`${t.from}>${t.to}`, t.count]));
  const allowed = Object.entries(sc.procedure.graph).flatMap(([a, bs]) => bs.map((b) => [a, b] as const));
  const failedEdges = sc.procedure.transitions.filter((t) => t.to === "failed").map((t) => [t.from, t.to] as const);
  const edges = [...allowed, ...failedEdges];
  const max = Math.max(1, ...sc.procedure.transitions.map((t) => t.count));
  const label = (s: string) => sc.procedure.labels[s] ?? (s === "start" ? "Request" : OUTCOME_LABEL[s as Outcome] ?? s);
  return (
    <svg viewBox="0 0 980 250" className="h-auto w-full" role="img" aria-label="Procedural graph of the agent pipeline">
      <defs>
        <marker id="veena-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--color-caramel)" />
        </marker>
      </defs>
      {edges.map(([a, b]) => {
        const p = STEP_POS[a];
        const q = STEP_POS[b];
        if (!p || !q) return null;
        const n = counts.get(`${a}>${b}`) ?? 0;
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const len = Math.hypot(dx, dy) || 1;
        const [x1, y1, x2, y2] = [p.x + (dx / len) * 46, p.y + (dy / len) * 20, q.x - (dx / len) * 48, q.y - (dy / len) * 22];
        return (
          <g key={a + b}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={n ? "var(--color-caramel)" : "var(--color-sand)"}
              strokeWidth={n ? 1.2 + (3 * n) / max : 1}
              strokeDasharray={n ? undefined : "4 4"}
              markerEnd="url(#veena-arrow)"
            />
            {n > 0 && (
              <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 5} textAnchor="middle" fontSize={10.5} fill="var(--color-mocha)" fontWeight={600}>
                {n}
              </text>
            )}
          </g>
        );
      })}
      {Object.entries(STEP_POS).map(([s, p]) => {
        const outcome = s in OUTCOME_LABEL;
        return (
          <g key={s}>
            <rect x={p.x - 46} y={p.y - 17} width={92} height={34} rx={outcome ? 17 : 9} fill={outcome ? "var(--color-ivory)" : "var(--color-white)"} stroke="var(--color-sand)" />
            <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize={12} fill="var(--color-bark)" fontWeight={outcome ? 500 : 600}>
              {label(s)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function KnowledgeGraphCard() {
  const { api, collections } = useApp();
  const [cid, setCid] = useState("");
  const [kg, setKg] = useState<KG | null>(null);
  useEffect(() => {
    if (!cid && collections[0]) setCid(collections[0].id);
  }, [cid, collections]);
  useEffect(() => {
    if (api && cid) void api.get<KG>(`/api/agents/knowledge-graph?collection_id=${cid}&limit=28`).then(setKg);
  }, [api, cid]);
  return (
    <Card>
      <CardHeader
        title="Knowledge graph"
        subtitle="What is true: entities in your documents, linked when they appear in the same passage"
        actions={
          collections.length > 0 && (
            <Select value={cid} onChange={(e) => setCid(e.target.value)} className="w-44" aria-label="Knowledge collection">
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )
        }
      />
      {!collections.length ? (
        <p className="px-5 py-5 text-sm text-caramel">Add documents in Knowledge to build a graph of what they say.</p>
      ) : kg && kg.nodes.length ? (
        <div className="px-3 pb-4">
          <EntityGraph data={kg} label="Knowledge graph of the selected collection" />
          <p className="px-2 text-xs text-caramel">
            {kg.entities} entities from {kg.passages} passages · showing the {kg.nodes.length} most frequent · ontology: {kg.ontology.name} names, {kg.ontology.acronym} acronyms,{" "}
            {kg.ontology.identifier} identifiers, {kg.ontology.figure} figures
          </p>
        </div>
      ) : (
        <p className="px-5 py-5 text-sm text-caramel">No entities found in this collection yet.</p>
      )}
    </Card>
  );
}

export function Agents() {
  const { api } = useApp();
  const [sc, setSc] = useState<Scorecard | null>(null);
  const [days, setDays] = useState(30);
  const load = useCallback(async () => {
    if (api) setSc(await api.get<Scorecard>(`/api/agents/scorecard?days=${days}`));
  }, [api, days]);
  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 8000);
    return () => clearInterval(t);
  }, [load]);

  if (!sc) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <CatMark size={56} mood="thinking" />
      </div>
    );
  }
  const ont = sc.ontology;
  const ontTotal = Object.values(ont).reduce((a, b) => a + b, 0);
  const outcomeTotal = Object.values(sc.outcomes).reduce((a, b) => a + b, 0);
  const trend = sc.daily.map((d) => ({
    day: d.day.slice(5),
    success: d.success_rate == null ? null : Math.round(d.success_rate * 100),
    support: d.support_rate == null ? null : Math.round(d.support_rate * 100),
    turns: d.turns,
  }));
  const latest = sc.context.latest;
  const usedIds = new Set(latest?.graph.nodes.filter((n) => n.used).map((n) => n.id));

  return (
    <div className="flex h-full flex-col">
      <TopBar
        title="Agents"
        subtitle="What's true → what matters now → what to do next, measured on every answer"
        actions={
          <div className="flex items-center gap-2">
            <Select value={String(days)} onChange={(e) => setDays(Number(e.target.value))} className="w-36" aria-label="Time range">
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </Select>
            <Button variant="ghost" size="sm" onClick={() => void load()} aria-label="Refresh agent scorecard">
              <RefreshCw size={15} />
            </Button>
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl space-y-5 px-6 py-6">
          {sc.turns === 0 && (
            <Card className="flex items-center gap-4 p-5">
              <CatMark size={44} />
              <p className="text-sm text-mocha">
                No agent turns in this period yet. Ask anything in Conversation, Screen or Meeting and every answer will be scored here: whether its names and figures
                are backed by what it was given, how much of that context it used, and whether it followed its procedure.
              </p>
            </Card>
          )}

          <section aria-label="Semantic spine">
            <h2 className="mb-2 text-sm font-semibold text-espresso">The semantic spine</h2>
            <div className="flex flex-col gap-3 lg:flex-row">
              <SpineCard kind="Ontology" title="Meaning" question="What things are" value={String(ontTotal)} detail={`entities in answers: ${ont.name} names · ${ont.acronym} acronyms · ${ont.identifier} identifiers · ${ont.figure} figures`} />
              <SpineCard
                kind="Knowledge graph"
                title="Facts"
                question="What's true"
                value={pct(sc.knowledge.support_rate)}
                detail={`of answer entities found in what the agent was given · ${sc.knowledge.unsupported_figures} unbacked figures`}
              />
              <SpineCard
                kind="Context graph"
                title="Context"
                question="What matters now"
                value={pct(sc.context.utilization)}
                detail={`of the scoped context used · avg ${sc.context.mean_nodes == null ? "–" : Math.round(sc.context.mean_nodes)} entities in scope · ${pct(sc.context.citation_rate)} of passages cited`}
              />
              <SpineCard kind="Procedural graph" title="Procedure" question="What to do next" value={pct(sc.procedure.adherence)} detail="of turns took exactly the steps their inputs called for" />
              <SpineCard kind="AI agent" title="Action" question="Acting, and writing it back" value={pct(sc.success_rate)} detail={`resolved without a governance flag · ${sc.turns} turns traced`} last />
            </div>
          </section>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Procedural graph" subtitle="Every allowed step; numbers show how many turns took each one. Dashed: allowed, not taken yet." />
              <div className="px-3 pb-3">
                <ProcedureGraph sc={sc} />
              </div>
            </Card>
            <Card>
              <CardHeader title="Outcomes" subtitle="Trace & learn: how each turn ended" />
              <div className="space-y-2.5 px-5 py-5">
                {(Object.keys(OUTCOME_LABEL) as Outcome[]).map((o) => (
                  <div key={o}>
                    <div className="flex justify-between text-xs">
                      <span className="text-mocha">{OUTCOME_LABEL[o]}</span>
                      <span className="font-semibold text-bark tabular-nums">{sc.outcomes[o]}</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-ivory">
                      <div className={cn("h-2 rounded-full", OUTCOME_SHADE[o])} style={{ width: `${outcomeTotal ? (100 * sc.outcomes[o]) / outcomeTotal : 0}%` }} />
                    </div>
                  </div>
                ))}
                <p className="pt-1 text-[11px] leading-snug text-caramel">
                  Escalated: nothing in the selected documents matched, so the agent handed the decision back to you. Stopped turns count neither way.
                </p>
              </div>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Context graph"
                subtitle={latest ? `What mattered for the latest ${agentName(latest.agent).toLowerCase()} answer · from ${latest.sources.join(", ")}` : "What mattered for the latest answer"}
              />
              {latest ? (
                <div className="px-3 pb-4">
                  <EntityGraph data={latest.graph} label="Context graph of the latest answer" highlight={(id) => usedIds.has(id)} />
                  <div className="flex items-center gap-4 px-2 text-xs text-caramel">
                    <span className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-ginger" /> used in the answer
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full border border-sand bg-ivory" /> in scope, not used
                    </span>
                  </div>
                </div>
              ) : (
                <p className="px-5 py-5 text-sm text-caramel">The next answer's context will be drawn here.</p>
              )}
            </Card>
            <KnowledgeGraphCard />
          </div>

          <div className="grid gap-5 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardHeader title="Per agent" subtitle="Each specialist agent's own scorecard" />
              {sc.agents.length ? (
                <div className="overflow-x-auto px-5 py-4">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-caramel">
                      <tr>
                        <th className="pb-2 font-medium">Agent</th>
                        <th className="pb-2 font-medium">Turns</th>
                        <th className="pb-2 font-medium">Resolved</th>
                        <th className="pb-2 font-medium">Facts backed</th>
                        <th className="pb-2 font-medium">Context used</th>
                        <th className="pb-2 font-medium">Followed procedure</th>
                        <th className="pb-2 font-medium">Median time</th>
                      </tr>
                    </thead>
                    <tbody className="text-mocha tabular-nums">
                      {sc.agents.map((a) => (
                        <tr key={a.agent} className="border-t border-cream">
                          <td className="py-2 font-semibold text-bark">{agentName(a.agent)}</td>
                          <td>{a.turns}</td>
                          <td>{pct(a.success_rate)}</td>
                          <td>{pct(a.support_rate)}</td>
                          <td>{pct(a.utilization)}</td>
                          <td>{pct(a.adherence)}</td>
                          <td>{a.p50_ms == null ? "–" : a.p50_ms >= 1000 ? `${(a.p50_ms / 1000).toFixed(1)} s` : `${Math.round(a.p50_ms)} ms`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="px-5 py-5 text-sm text-caramel">No agents have answered yet.</p>
              )}
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader title="Continuous improvement" subtitle="Daily share of resolved turns and backed facts" />
              {trend.length ? (
                <div className="h-56 px-2 py-4">
                  <ResponsiveContainer>
                    <LineChart data={trend} margin={{ left: -18, right: 12 }}>
                      <CartesianGrid stroke="var(--color-cream)" vertical={false} />
                      <XAxis dataKey="day" {...AXIS} />
                      <YAxis domain={[0, 100]} unit="%" {...AXIS} />
                      <Tooltip {...TT} formatter={(v) => `${v}%`} />
                      <Legend wrapperStyle={{ fontSize: 11, color: "var(--color-mocha)" }} />
                      <Line type="monotone" dataKey="success" name="Resolved" stroke="var(--color-caramel)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
                      <Line type="monotone" dataKey="support" name="Facts backed" stroke="var(--color-sand)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="px-5 py-5 text-sm text-caramel">The trend appears after the first traced turn.</p>
              )}
            </Card>
          </div>

          <Card>
            <CardHeader title="Recent traces" subtitle="Success and failure traces, newest first. Unbacked entities are the names and figures the agent was not given." />
            {sc.recent.length ? (
              <ul className="divide-y divide-cream px-5 py-2">
                {sc.recent.map((t) => (
                  <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm">
                    <Badge tone={t.outcome === "resolved" ? "strong" : "outline"}>{OUTCOME_LABEL[t.outcome]}</Badge>
                    <span className="font-semibold text-bark">{agentName(t.agent)}</span>
                    <span className="text-xs text-caramel">{t.path.map((s) => sc.procedure.labels[s] ?? s).join(" → ")}</span>
                    {!t.adherent && <Badge tone="outline">off procedure</Badge>}
                    <span className="ml-auto text-xs text-mocha tabular-nums">
                      facts backed {pct(t.support_rate)} · {new Date(t.at.endsWith("Z") || t.at.includes("+") ? t.at : t.at + "Z").toLocaleString(undefined, { hour12: false, dateStyle: "short", timeStyle: "short" })}
                    </span>
                    {t.unsupported.length > 0 && <span className="w-full text-xs text-caramel">Unbacked: {t.unsupported.join(", ")}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-5 py-5 text-sm text-caramel">No traces yet.</p>
            )}
          </Card>

          <p className="pb-4 text-xs leading-relaxed text-caramel">
            How this is measured: every number comes from rules applied to each answer's real inputs and output; no AI grades another AI here. "Facts backed" means the
            answer's names, acronyms, identifiers and figures appear in the question, history, screen, transcript or documents the agent was given. It catches invented
            names and numbers; it cannot tell whether a backed entity was used correctly.
          </p>
        </div>
      </div>
    </div>
  );
}
