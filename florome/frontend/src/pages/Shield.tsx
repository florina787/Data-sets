import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { FlaskConical, Play, ShieldCheck, Wand2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Chart, type ChartOption } from "../components/Chart";
import { useRole } from "../components/Layout";
import { ErrorBox, Loading, cx } from "../components/ui";
import { api, post, type BenchRow, type CodeGraph, type ContainmentEvent, type ShieldHyp, type ShieldRepo, type ShieldSummary } from "../lib/api";
import { useAsync } from "../lib/useAsync";

const GOLD = "#E8C26A";
const LIME = "#C6F36B";
const STATUS: Record<string, string> = {
  confirmed: "bg-[#ff6b5b]/15 text-[#ff8b7e] border-[#ff6b5b]/40", disproven: "bg-white/5 text-white/50 border-white/15 line-through",
  inconclusive: "bg-[#E8C26A]/10 text-[#E8C26A] border-[#E8C26A]/30", probable: "bg-[#7C84F2]/15 text-[#A3AAFB] border-[#7C84F2]/40",
  open: "bg-white/5 text-white/70 border-white/15",
};
const SEV: Record<string, string> = { critical: "text-[#ff6b5b]", high: "text-[#ffa36b]", medium: "text-[#E8C26A]", low: "text-white/60", none: "text-white/30" };

function Pill({ value }: { value: string }) {
  return <span className={cx("rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider", STATUS[value] ?? STATUS.open)}>{value}</span>;
}

function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cx("rounded-2xl border border-white/10 bg-white/[0.035] p-5 backdrop-blur", className)}>{children}</section>;
}

function H({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <header className="mb-4">
      <div className="font-mono text-[11px] uppercase tracking-[0.2em]" style={{ color: GOLD }}>{eyebrow}</div>
      <h2 className="mt-1 font-display text-2xl font-semibold text-white">{title}</h2>
      {sub && <p className="mt-1 max-w-3xl text-sm text-white/55">{sub}</p>}
    </header>
  );
}

export default function Shield() {
  const role = useRole();
  const summary = useAsync(() => api<ShieldSummary>("/shield/summary"));
  const repos = useAsync(() => api<{ authorized_targets: { name: string; path: string }[]; repositories: ShieldRepo[] }>("/shield/repositories"));
  const hyps = useAsync(() => api<ShieldHyp[]>("/shield/hypotheses"));
  const bench = useAsync(() => api<BenchRow[]>("/shield/evaluation"));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const repo = repos.data?.repositories[0];

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      await Promise.all([summary.reload(), repos.reload(), hyps.reload(), bench.reload()]);
    }
  };
  const runAll = () => act("research", () => post("/shield/evaluation/run"));

  return (
    <div className="min-h-screen bg-[#07080a] text-white">
      <Hero onRun={runAll} busy={busy === "research"} role={role} />
      <div className="mx-auto max-w-[1400px] space-y-8 px-6 pb-16">
        {error && <ErrorBox error={error} />}
        <div className="flex flex-wrap items-center gap-3 text-xs text-white/50">
          <span className="rounded-md bg-[#E8C26A]/10 px-2 py-1 font-semibold uppercase tracking-wider text-[#E8C26A]">Benchmark data</span>
          Target: LedgerLite, a deliberately vulnerable training app with 5 real weaknesses and 4 safe look-alikes. All data is synthetic.
          <span className="ml-auto">Acting as <b className="text-white">demo {role}</b>. Running research needs the admin role.</span>
        </div>
        {summary.loading && <Loading label="Reading Shield state" />}
        {summary.data && <MetricsOrb s={summary.data} />}
        <ResearchLab hyps={hyps.data ?? []} repo={repo} busy={busy} act={act}
          onRefresh={() => void Promise.all([hyps.reload(), summary.reload()])} />
        {repo && <CodeGraphView repoId={repo.id} />}
        <Containment onDone={() => void summary.reload()} />
        <Evaluation rows={bench.data ?? []} />
        {summary.data && <ControlHealth s={summary.data} />}
      </div>
    </div>
  );
}

function Hero({ onRun, busy, role }: { onRun: () => void; busy: boolean; role: string }) {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_40%,rgba(232,194,106,0.18),transparent_55%),radial-gradient(ellipse_at_20%_80%,rgba(198,243,107,0.10),transparent_50%)]" />
      <div className="grid-dark absolute inset-0 opacity-40" />
      <div className="relative mx-auto max-w-[1400px] px-6 pb-10 pt-12">
        <div className="flex items-start justify-between font-mono text-[11px] text-white/45">
          <span>FLOROME SHIELD · 1.0 research preview</span>
          <span className="hidden md:block">Trust us to be your guardian in an ever-changing digital landscape? No: verify everything.</span>
        </div>
        <h1 className="mt-6 font-display text-[clamp(3.5rem,13vw,11rem)] font-black uppercase leading-[0.82] tracking-tight"
          style={{ backgroundImage: `linear-gradient(180deg,#fff 10%,${GOLD} 95%)`, WebkitBackgroundClip: "text", color: "transparent" }}>
          Cyber Dome
        </h1>
        <div className="mt-6 grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
          <p className="max-w-xl text-sm leading-relaxed text-white/65">
            Shield reads code, guesses where it could break, then <b className="text-white">proves</b> each guess by safely attacking a disposable
            copy in a sealed lab. Guesses that can't be reproduced are thrown out. Real problems get a tested fix and go to a human for review.
          </p>
          <button onClick={onRun} disabled={busy || role !== "admin"}
            className="inline-flex items-center gap-3 rounded-none border-2 border-white bg-white px-6 py-3 font-display text-sm font-bold uppercase tracking-wider text-black [clip-path:polygon(0_0,100%_0,100%_70%,92%_100%,0_100%)] disabled:opacity-40">
            <FlaskConical className="h-4 w-4" />{busy ? "Researching… (about 30 s)" : "Run full research"}
          </button>
        </div>
      </div>
    </section>
  );
}

function MetricsOrb({ s }: { s: ShieldSummary }) {
  const disproven = s.hypotheses.by_status.disproven ?? 0;
  const cards = [
    { n: s.findings.confirmed, label: "Confirmed vulnerabilities", sub: "reproduced twice in the lab", tone: "gold" },
    { n: disproven, label: "False alarms rejected", sub: "disproven by execution", tone: "teal" },
    { n: (s.patches.verified ?? 0) + (s.patches.approved_for_review ?? 0), label: "Fixes that passed retest", sub: "exploit blocked, features intact", tone: "teal" },
    { n: s.containment.contained, label: "Rogue agent sessions stopped", sub: `${s.containment.sessions} sessions supervised`, tone: "teal" },
    { n: s.policy.denied, label: "Actions denied by policy", sub: `${s.policy.decisions} decisions recorded`, tone: "teal" },
  ];
  return (
    <Panel className="relative overflow-hidden !bg-[#0b0f12] p-0">
      <div className="grid items-center gap-2 md:grid-cols-[320px_1fr]">
        <div className="relative h-[380px]">
          <svg viewBox="0 0 320 380" className="h-full w-full" aria-hidden="true">
            <defs>
              <radialGradient id="orb" cx="40%" cy="35%">
                <stop offset="0" stopColor="#f5eaff" />
                <stop offset="0.45" stopColor="#a58cf0" />
                <stop offset="1" stopColor="#3b2a7a" />
              </radialGradient>
            </defs>
            {Array.from({ length: 90 }).map((_, i) => {
              const a = (i / 90) * Math.PI * 2;
              const r = 70 + ((i * 37) % 13);
              return <line key={i} x1={150 + Math.cos(a) * 58} y1={190 + Math.sin(a) * 58} x2={150 + Math.cos(a) * r} y2={190 + Math.sin(a) * r} stroke="#7ad7c9" strokeOpacity="0.5" strokeWidth="1" />;
            })}
            {cards.map((_, i) => (
              <path key={i} d={`M 210 190 C 270 190, 270 ${40 + i * 72}, 320 ${40 + i * 72}`} fill="none" stroke={i === 0 ? GOLD : "#7ad7c9"} strokeOpacity={i === 0 ? 0.9 : 0.35} />
            ))}
            <circle cx="150" cy="190" r="52" fill="url(#orb)" />
            <text x="150" y="290" textAnchor="middle" fill="#fff" fontSize="13" fontWeight="600">LedgerLite</text>
            <text x="150" y="308" textAnchor="middle" fill="#ffffff80" fontSize="11">{s.hypotheses.total} hypotheses tested</text>
          </svg>
        </div>
        <div className="space-y-2 p-5">
          {cards.map((c) => (
            <div key={c.label} className={cx("flex items-center gap-5 rounded-xl border px-5 py-3 backdrop-blur",
              c.tone === "gold" ? "border-[#E8C26A]/70 bg-[#E8C26A]/10 shadow-[0_0_40px_-10px_rgba(232,194,106,0.6)]" : "border-[#7ad7c9]/20 bg-[#7ad7c9]/[0.05]")}>
              <span className="w-16 font-display text-4xl font-semibold tabular-nums">{c.n}</span>
              <div><div className="text-sm text-white/85">{c.label}</div><div className="text-xs text-white/45">{c.sub}</div></div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ResearchLab({ hyps, repo, busy, act, onRefresh }: { hyps: ShieldHyp[]; repo?: ShieldRepo; busy: string | null;
  act: (label: string, fn: () => Promise<unknown>) => Promise<void>; onRefresh: () => void }) {
  const [params, setParams] = useSearchParams();
  const sel = params.get("hypothesis");
  const setSel = (id: string) => setParams((p) => { p.set("hypothesis", id); return p; }, { replace: true });  // shared with the assistant
  const detail = useAsync(() => (sel ? api<ShieldHyp>(`/shield/hypotheses/${sel}`) : Promise.resolve(null)), [sel]);
  const d = detail.data;
  const sorted = useMemo(() => [...hyps].sort((a, b) => ["confirmed", "probable", "inconclusive", "open", "disproven"].indexOf(a.status) -
    ["confirmed", "probable", "inconclusive", "open", "disproven"].indexOf(b.status)), [hyps]);
  const reload = async () => { await detail.reload(); onRefresh(); };

  return (
    <div>
      <H eyebrow="Vulnerability research lab" title="Every guess, and how it was settled"
        sub="Each row is a hypothesis: a specific place in the code where a security assumption might break. Click one to see the code, the evidence for and against, and the lab runs that settled it." />
      {!hyps.length && <Panel><p className="text-sm text-white/60">No research yet. Switch to <b>demo admin</b> and press <b>Run full research</b> above.</p></Panel>}
      {hyps.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[1fr_520px]">
          <Panel className="p-0">
            <table className="w-full text-left text-sm">
              <thead className="font-mono text-[10px] uppercase tracking-wider text-white/40"><tr><th className="p-3">Where</th><th>Weakness class</th><th>Verdict</th><th>Severity</th></tr></thead>
              <tbody>
                {sorted.map((h) => (
                  <tr key={h.id} onClick={() => setSel(h.id)} className={cx("cursor-pointer border-t border-white/5 hover:bg-white/[0.04]", sel === h.id && "bg-[#E8C26A]/10")}>
                    <td className="p-3"><div className="font-mono text-[13px]">{h.function}</div><div className="text-[11px] text-white/40">{h.file}:{h.line}</div></td>
                    <td className="text-white/75">{h.vuln_class.replace(/_/g, " ")}</td>
                    <td><Pill value={h.status} /></td>
                    <td className={cx("font-semibold uppercase", SEV[h.severity ?? "none"])}>{h.severity ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel>
            {!sel && <p className="text-sm text-white/55">Select a hypothesis.</p>}
            {detail.loading && sel && <Loading />}
            {d && (
              <div className="space-y-4 text-sm">
                <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-base">{d.function}</span><Pill value={d.status} />
                  {d.severity && <span className={cx("text-xs font-bold uppercase", SEV[d.severity])}>{d.severity}</span>}</div>
                <p className="text-white/70"><b className="text-white">Assumption tested:</b> {d.assumption}</p>
                <p className="rounded-lg bg-white/[0.04] p-3 text-white/80"><b>Verdict basis:</b> {d.status_basis}{d.severity_basis && <><br /><b>Severity basis:</b> {d.severity_basis}</>}</p>
                {d.source && (
                  <pre className="overflow-x-auto rounded-lg bg-black/60 p-3 font-mono text-[11.5px] leading-5">
                    {d.source.lines.map((ln, i) => {
                      const n = d.source!.start_line + i;
                      return <div key={n} className={n === d.source!.highlight ? "bg-[#E8C26A]/20 text-white" : "text-white/55"}><span className="mr-3 inline-block w-7 text-right text-white/30">{n}</span>{ln}</div>;
                    })}
                  </pre>
                )}
                <div className="grid gap-3 md:grid-cols-2">
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider text-[#ff8b7e]">Evidence for</div>
                    <ul className="space-y-1 text-xs text-white/70">{d.supporting.map((e, i) => <li key={i}>• <span className="font-mono text-white/40">{e.type}</span> {e.detail}</li>)}</ul></div>
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider text-[#7ad7c9]">Evidence against</div>
                    <ul className="space-y-1 text-xs text-white/70">{d.contradicting.map((e, i) => <li key={i}>• {e.detail.replace(/_/g, " ")}</li>)}{!d.contradicting.length && <li className="text-white/40">none found</li>}</ul></div>
                </div>
                {!!d.verification_runs?.length && (
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: LIME }}>Lab runs (sealed, no network)</div>
                    <ul className="space-y-1 font-mono text-[11px]">{d.verification_runs.map((r) => (
                      <li key={r.id} className="flex justify-between gap-3"><span>{r.purpose === "verify" ? "verify" : "retest after fix"} #{r.attempt}: {r.transcript.probe?.evidence}</span>
                        <span className={r.outcome === "reproduced" ? "text-[#ff8b7e]" : "text-[#7ad7c9]"}>{r.outcome} · {r.seconds}s</span></li>))}</ul></div>
                )}
                <div className="flex flex-wrap gap-2">
                  <button disabled={!!busy || !d.verification_method} onClick={() => act("verify", () => post(`/shield/hypotheses/${d.id}/verify`)).then(reload)}
                    className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-3 py-1.5 text-xs disabled:opacity-40"><Play className="h-3.5 w-3.5" />Re-verify in lab</button>
                  <button disabled={!!busy || d.status !== "confirmed"} onClick={() => act("patch", () => post(`/shield/hypotheses/${d.id}/patch`)).then(reload)}
                    className="inline-flex items-center gap-2 rounded-lg bg-[#E8C26A] px-3 py-1.5 text-xs font-semibold text-black disabled:opacity-40"><Wand2 className="h-3.5 w-3.5" />Generate & retest fix</button>
                </div>
                {d.patches?.slice(-1).map((pt) => (
                  <div key={pt.id} className="space-y-2">
                    <div className="flex items-center gap-2 text-xs"><ShieldCheck className="h-4 w-4" style={{ color: LIME }} />
                      Fix {pt.status.replace(/_/g, " ")}: exploit blocked in {pt.regression.exploit_blocked_runs}/2 retests, features {pt.regression.functional_ok ? "still work" : "BROKE"}.
                      {pt.status === "verified" && (
                        <button className="ml-auto rounded bg-white/10 px-2 py-1" onClick={() => act("review", () => post(`/shield/patches/${pt.id}/review`, { decision: "approve", patch_hash: pt.patch_hash })).then(reload)}>
                          Approve for review</button>)}
                    </div>
                    <pre className="max-h-64 overflow-auto rounded-lg bg-black/60 p-3 font-mono text-[11px] leading-5">
                      {pt.diff.split("\n").map((l, i) => <div key={i} className={l.startsWith("+") ? "text-[#C6F36B]" : l.startsWith("-") ? "text-[#ff8b7e]" : "text-white/45"}>{l}</div>)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      )}
      {repo?.latest_snapshot && <p className="mt-2 font-mono text-[11px] text-white/35">snapshot {repo.latest_snapshot.id} · commit {repo.latest_snapshot.commit?.slice(0, 10)} · tree {repo.latest_snapshot.tree_hash.slice(0, 12)} · {repo.latest_snapshot.stats.symbols} symbols, {repo.latest_snapshot.stats.relationships} relationships</p>}
    </div>
  );
}

type GData = { label: string; sub: string; kind: string; tone: string };
function GNode({ data }: NodeProps<Node<GData>>) {
  const tone: Record<string, string> = { open: "border-[#E8C26A] shadow-[0_0_24px_-4px_rgba(232,194,106,0.7)]", auth: "border-[#7ad7c9]", sink: "border-[#ff6b5b]", provider: "border-[#C6F36B]" };
  return (
    <div className={cx("flex items-center gap-2 rounded-full border-2 bg-[#0d1114] px-3 py-1.5 text-[11px] text-white", tone[data.tone])}>
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <span className="h-2 w-2 rounded-full" style={{ background: data.tone === "sink" ? "#ff6b5b" : data.tone === "open" ? GOLD : data.tone === "provider" ? LIME : "#7ad7c9" }} />
      <div><div className="font-mono">{data.label}</div><div className="text-[9px] text-white/45">{data.sub}</div></div>
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}
const gTypes = { g: GNode };

function CodeGraphView({ repoId }: { repoId: string }) {
  const g = useAsync(() => api<CodeGraph>(`/shield/repositories/${repoId}/graph`), [repoId]);
  const flow = useMemo(() => {
    if (!g.data) return null;
    const keep = g.data.edges.filter((e) => ["authenticated_by", "data_flow"].includes(e.kind));
    const ids = new Set(keep.flatMap((e) => [e.source, e.target]));
    g.data.nodes.filter((n) => n.kind === "route").forEach((n) => ids.add(n.id));
    const nodes = g.data.nodes.filter((n) => ids.has(n.id));
    const col = (n: (typeof nodes)[0]) => (n.kind === "sink" ? 2 : n.auth_provider ? 0 : 1);
    const count = [0, 0, 0];
    const rf: Node<GData>[] = nodes.map((n) => {
      const c = col(n);
      const y = count[c]++ * 64;
      const tone = n.kind === "sink" ? "sink" : n.auth_provider ? "provider" : n.trust_boundary === "unauthenticated_input" ? "open" : "auth";
      const sub = n.route ? `${n.route.method} ${n.route.path}` : n.kind === "sink" ? "dangerous operation" : n.auth_provider ? "login check" : n.kind;
      return { id: n.id, type: "g", position: { x: c * 330, y: c === 0 ? 200 + y : y }, data: { label: n.kind === "sink" ? n.name.split(":").slice(1).join(":") : n.name, sub, kind: n.kind, tone } };
    });
    const edges: Edge[] = keep.map((e) => ({
      id: e.id, source: e.source, target: e.target, label: e.kind === "data_flow" ? `request data → (${((e.attrs.params as string[]) ?? []).join(",")})` : "requires login",
      style: { stroke: e.kind === "data_flow" ? ((e.attrs.guards as string[])?.length ? "#7ad7c9" : "#ff6b5b") : LIME, strokeWidth: 1.4, strokeDasharray: e.kind === "authenticated_by" ? "4 4" : undefined },
      labelStyle: { fill: "#ffffffb0", fontSize: 9 }, labelBgStyle: { fill: "#0d1114" },
    }));
    return { nodes: rf, edges };
  }, [g.data]);
  return (
    <div>
      <H eyebrow="Code intelligence graph" title="Who can reach what"
        sub="Built by parsing the source (tree-sitter), not by guessing. Gold = web endpoints anyone can call; teal = endpoints that need a login; red = dangerous operations. A red line means request data reaches a dangerous operation with no safety check on the way; a teal line means a check was found." />
      <Panel className="h-[560px] p-0">
        {g.loading && <Loading />}
        {flow && (
          <ReactFlow nodes={flow.nodes} edges={flow.edges} nodeTypes={gTypes} fitView minZoom={0.3} colorMode="dark">
            <Background gap={28} color="#ffffff14" />
            <Controls showInteractive={false} />
          </ReactFlow>
        )}
      </Panel>
    </div>
  );
}

function Containment({ onDone }: { onDone: () => void }) {
  const role = useRole();
  const scenarios = useAsync(() => api<{ id: string; description: string; expected: string }[]>("/shield/containment/scenarios"));
  const events = useAsync(() => api<ContainmentEvent[]>("/shield/containment/events"));
  const [busy, setBusy] = useState<string | null>(null);
  const run = async (id: string) => {
    setBusy(id);
    try {
      await post("/shield/containment/run", { scenario: id });
    } finally {
      setBusy(null);
      await events.reload();
      onDone();
    }
  };
  const last = (id: string) => events.data?.find((e) => e.scenario === id);
  return (
    <div>
      <H eyebrow="Agent containment" title="What happens when an AI agent misbehaves"
        sub="Each tile is a small AI-agent program that tries something it shouldn't. A supervisor that doesn't depend on the AI watches every file, network and process call, and kills the session on the first violation." />
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#081310] p-5">
        <div className="pointer-events-none absolute inset-0 opacity-60 [background-image:radial-gradient(ellipse_at_30%_40%,rgba(64,180,140,0.35),transparent_45%),radial-gradient(ellipse_at_75%_60%,rgba(198,243,107,0.18),transparent_40%),radial-gradient(rgba(255,255,255,0.07)_1px,transparent_1px)] [background-size:auto,auto,14px_14px]" />
        <div className="relative grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {scenarios.data?.map((s) => {
            const e = last(s.id);
            return (
              <div key={s.id} className="rounded-xl border border-white/10 bg-black/50 p-4 backdrop-blur">
                <div className="flex items-center justify-between"><span className="font-mono text-xs" style={{ color: LIME }}>{s.id}</span>
                  {e && <span className={cx("rounded px-1.5 py-0.5 text-[10px] font-bold uppercase", e.outcome === "contained" ? "bg-[#ff6b5b]/20 text-[#ff8b7e]" : "bg-[#C6F36B]/20 text-[#C6F36B]")}>{e.outcome}</span>}</div>
                <p className="mt-2 text-xs text-white/65">{s.description}</p>
                {e && <p className="mt-2 font-mono text-[10px] text-white/45">{e.violation ? `${e.violation} → ${e.actions_taken.join(", ")}` : "finished normally"} · {Math.round(e.forensics.seconds * 1000)} ms</p>}
                <button disabled={!!busy || role !== "admin"} onClick={() => void run(s.id)} className="mt-3 rounded-md bg-white/10 px-3 py-1 text-xs disabled:opacity-40">{busy === s.id ? "Running…" : "Run in sandbox"}</button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function Evaluation({ rows }: { rows: BenchRow[] }) {
  const latest = ["scanner_only", "graph_unverified", "hybrid_verified"].map((p) => rows.find((r) => r.pipeline === p)).filter(Boolean) as BenchRow[];
  const llm = rows.find((r) => r.pipeline === "llm_only");
  const label: Record<string, string> = { scanner_only: "Scanners only", graph_unverified: "Code graph, no lab", hybrid_verified: "Florome Shield (graph + lab)" };
  const option: ChartOption | null = latest.length ? {
    grid: { left: 40, right: 10, top: 30, bottom: 30 }, legend: { textStyle: { color: "#ffffffaa" }, top: 0 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: latest.map((r) => label[r.pipeline]), axisLabel: { color: "#ffffffaa" } },
    yAxis: { type: "value", max: 5, axisLabel: { color: "#ffffff66" }, splitLine: { lineStyle: { color: "#ffffff10" } } },
    series: [
      { name: "Real problems found", type: "bar", data: latest.map((r) => r.metrics.tp), itemStyle: { color: LIME, borderRadius: [6, 6, 0, 0] } },
      { name: "False alarms", type: "bar", data: latest.map((r) => r.metrics.fp), itemStyle: { color: "#ff6b5b", borderRadius: [6, 6, 0, 0] } },
      { name: "Missed", type: "bar", data: latest.map((r) => r.metrics.fn), itemStyle: { color: "#ffffff40", borderRadius: [6, 6, 0, 0] } },
    ],
  } : null;
  return (
    <div>
      <H eyebrow="Research evaluation" title="Does proving beat guessing?"
        sub="Three approaches scored on the same 9 labelled spots in LedgerLite (5 real problems, 4 safe look-alikes). Small sample, written by us: a regression check, not a claim about the real world." />
      {!latest.length && <Panel><p className="text-sm text-white/55">No evaluation yet. Run full research above.</p></Panel>}
      {latest.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          <Panel className="!bg-[#0b0d0a]">{option && <Chart option={option} height={300} label="Real problems found, false alarms and misses per approach" />}</Panel>
          <div className="grid gap-3">
            {latest.map((r) => (
              <Panel key={r.id} className={r.pipeline === "hybrid_verified" ? "border-[#C6F36B]/40 bg-[#C6F36B]/[0.06]" : ""}>
                <div className="text-xs text-white/55">{label[r.pipeline]}</div>
                <div className="mt-1 flex items-end gap-4">
                  <span className="font-display text-4xl font-semibold" style={{ color: r.pipeline === "hybrid_verified" ? LIME : "#fff" }}>{r.metrics.precision === null ? "–" : Math.round(r.metrics.precision * 100)}%</span>
                  <span className="pb-1 text-xs text-white/55">precision · {Math.round((r.metrics.recall ?? 0) * 100)}% recall · {r.metrics.fp} false alarms</span>
                </div>
              </Panel>
            ))}
            {llm && <Panel><div className="text-xs text-white/55">AI model only</div><div className="mt-1 text-sm text-white/70">{llm.note}</div></Panel>}
          </div>
        </div>
      )}
    </div>
  );
}

function ControlHealth({ s }: { s: ShieldSummary }) {
  const items: [string, boolean, string][] = [
    ["Opengrep pattern engine", s.controls.opengrep, "installed"], ["Trivy dependency scanner", s.controls.trivy, "installed"],
    ["OPA second policy engine", s.controls.opa, `mode: ${s.controls.opa_mode}`], ["Network-sealed lab (namespace)", s.controls.network_namespace, "available"],
    ["Emergency stop", !s.controls.emergency_stop, s.controls.emergency_stop ? "ACTIVE: research blocked" : "ready"],
  ];
  return (
    <Panel>
      <div className="font-mono text-[11px] uppercase tracking-[0.2em]" style={{ color: GOLD }}>Security control health</div>
      <div className="mt-3 grid gap-2 md:grid-cols-5">
        {items.map(([name, ok, note]) => (
          <div key={name} className="rounded-lg border border-white/10 p-3 text-xs"><div className="flex items-center gap-2"><span className={cx("h-2 w-2 rounded-full", ok ? "bg-[#C6F36B]" : "bg-[#ff6b5b]")} />{name}</div>
            <div className="mt-1 text-white/45">{note}</div></div>
        ))}
      </div>
    </Panel>
  );
}
