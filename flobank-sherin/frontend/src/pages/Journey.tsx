import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FastForward, Pause, Play, RotateCcw, Volume2, VolumeX, Accessibility } from "lucide-react";
import { CostDriversChart, GraphA, GraphC } from "../components/charts";
import { AgentGraph } from "../components/AgentGraph";
import { ApprovalCard } from "../components/ApprovalCard";
import { Plot } from "../components/Plot";
import { Badge, Button, Card, DecisionBadge, Note, PageHeader, StatusBadge, Table } from "../components/ui";
import { SherinAvatar } from "../components/SherinAvatar";
import { CHARACTER_ASSET, SherinCharacter, type Pose } from "../sherin/Character";
import { Aborted, sherin, useSherin } from "../sherin/director";
import { canCelebrate, directiveFor, runPhase, syntheticEvents, type HarnessEvent } from "../sherin/machine";
import { api, useApi } from "../lib/api";
import { periodParams, useApp } from "../lib/store";
import { money, pctChange, SERIES } from "../lib/format";

// ------------------------------------------------------------------------------------------- scene definitions
interface SceneDef {
  id: number; key: string; title: string; subtitle: string;
  entry: "left"; path: number[]; destination: string; gesture: Pose; reveal: string; agentState: string; exit: "right";
}
export const SCENES: SceneDef[] = [
  { id: 1, key: "revenue", title: "Revenue Intelligence", subtitle: "Bank revenue and operating profit", entry: "left", path: [0.12, 0.3], destination: "#graph-a", gesture: "point", reveal: "Revenue vs expenditure chart", agentState: "No agent running: reading the ledger", exit: "right" },
  { id: 2, key: "expenditure", title: "Expenditure Intelligence", subtitle: "Cost drivers, infrastructure, tokens and AI budget", entry: "left", path: [0.1, 0.25], destination: "#scene-drivers", gesture: "point", reveal: "Cost-driver chart, AI budget gauge, token usage", agentState: "FinOps view of recorded cost rows", exit: "right" },
  { id: 3, key: "harness", title: "Agent Harness", subtitle: "Sherin follows the actual LangGraph execution path", entry: "left", path: [0.08], destination: "[data-testid='agent-graph']", gesture: "work", reveal: "Live agent execution graph", agentState: "Live run: plan → agents → validation → approval", exit: "right" },
  { id: 4, key: "human-vs-ai", title: "Human vs AI Economics", subtitle: "Verified work, human effort avoided, savings and ROI in USD, INR and CAD", entry: "left", path: [0.15, 0.4], destination: "#scene-roi", gesture: "point", reveal: "Human vs AI cost and tri-currency ROI", agentState: "Run paused, waiting for approval (Sherin keeps presenting)", exit: "right" },
  { id: 5, key: "guardian", title: "Investment Guardian", subtitle: "Exposure, liquidity, ESG and policy controls", entry: "left", path: [0.2, 0.45], destination: "#scene-controls", gesture: "think", reveal: "Guardian controls and exposure", agentState: "Guardian result recorded by the run", exit: "right" },
  { id: 6, key: "approval", title: "Manager Approval", subtitle: "The workflow pauses until an authorized decision is recorded", entry: "left", path: [0.35], destination: "#manager-desk", gesture: "waiting", reveal: "Approval request at the manager's desk", agentState: "Paused at approval_gate (LangGraph interrupt)", exit: "right" },
  { id: 7, key: "summary", title: "Executive Summary", subtitle: "Completed task, evidence, costs and financial outcome", entry: "left", path: [0.2], destination: "#scene-summary", gesture: "point", reveal: "Outcome, evidence and costs", agentState: "Finalised: task recorded with measured cost", exit: "right" },
];

const RUN_REQUEST = "Evaluate trade TP-1003 and check the portfolio risk";
const RUN_AS = { role: "PORTFOLIO_MANAGER", user: "pm.ananya" }; // demo requester, so a different person can approve
const SYNTHETIC_PLAN = [
  { step: 1, agent: "investment_judgment", tool: "guardian.evaluate", objective: "Run Sherin Guardian pre-trade controls" },
  { step: 2, agent: "risk_analytics", tool: "risk.var", objective: "Compute portfolio risk" },
  { step: 3, agent: "esg", tool: "esg.scores", objective: "Validate ESG exposure" },
];

type Mode = "live" | "synthetic";
type Phase = "ready" | "playing" | "paused" | "done";

// ------------------------------------------------------------------------------------------- page
export default function Journey() {
  const app = useApp();
  const ch = useSherin();
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("ready");
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [lines, setLines] = useState<{ scene: number; text: string; tone: string; synthetic?: boolean }[]>([]);
  const [mode, setMode] = useState<Mode>(app.role === "VIEWER" ? "synthetic" : "live");
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<HarnessEvent[]>([]);
  const [runError, setRunError] = useState<string | null>(null);
  const eventsRef = useRef<HarnessEvent[]>([]);
  const playingRef = useRef(false);
  const idxRef = useRef(0);
  idxRef.current = idx;

  useEffect(() => { sherin.setJourney(true); return () => { sherin.abort(); sherin.focus(null); sherin.setJourney(false); }; }, []);
  useEffect(() => { eventsRef.current = events; }, [events]);

  // live event stream (server-sent events from the LangGraph run)
  useEffect(() => {
    if (!runId || mode !== "live") return;
    const es = new EventSource(`/api/harness/runs/${runId}/stream`);
    es.addEventListener("harness", (m: MessageEvent) => {
      const e = JSON.parse(m.data) as HarnessEvent;
      setEvents((xs) => (xs.some((x) => x.seq === e.seq) ? xs : [...xs, e].sort((a, b) => a.seq - b.seq)));
    });
    es.addEventListener("end", () => es.close());
    es.onerror = () => { /* the browser reconnects automatically */ };
    return () => es.close();
  }, [runId, mode]);

  const say = useCallback((scene: number, text: string, tone: "info" | "success" | "warning" | "error" = "info", synthetic?: boolean) => {
    sherin.say(text, tone, { synthetic });
    setLines((l) => [...l, { scene, text, tone, synthetic }]);
  }, []);

  const startWorkflow = useCallback(async () => {
    if (runId || (mode === "synthetic" && eventsRef.current.length)) return;
    setRunError(null);
    if (mode === "synthetic") { setEvents(syntheticEvents(SYNTHETIC_PLAN)); return; }
    try {
      const r = await api<{ run_id: string }>("/harness/runs", { method: "POST", body: { request: RUN_REQUEST }, as: RUN_AS });
      setRunId(r.run_id);
    } catch (e: any) { setRunError(e.message); setMode("synthetic"); setEvents(syntheticEvents(SYNTHETIC_PLAN)); }
  }, [runId, mode]);

  const waitFor = async (pred: () => boolean, tok: number) => { while (!pred()) await sherin.sleep(250, tok); };

  // ------------------------------------------------------------------ choreography for one scene
  const playScene = useCallback(async (i: number, tok: number) => {
    const sc = SCENES[i];
    setIdx(i);
    setRevealed((r) => ({ ...r, [i]: false }));
    sherin.focus(null);
    // entry: short scene transition, then enter walking from the left edge
    await sherin.transitionTo(0.02, tok);
    await sherin.sleep(350, tok);
    for (const x of sc.path) await sherin.walkTo(x, tok);
    // graph reveal
    setRevealed((r) => ({ ...r, [i]: true }));
    await sherin.sleep(700, tok);
    const hook = HOOKS[sc.key];
    await hook({ tok, say: (t, tone, syn) => say(sc.id, t, tone, syn), events: () => eventsRef.current, waitFor, scene: sc });
    await sherin.sleep(1600, tok);
    // exit
    sherin.focus(null);
    sherin.say(null);
    await sherin.walkTo(0.97, tok);
  }, [say]);

  const runFrom = useCallback(async (start: number, holdMs = 0) => {
    const tok = sherin.token();
    playingRef.current = true;
    setPhase("playing");
    try {
      if (holdMs) await sherin.sleep(holdMs, tok); // let the viewer read a skipped scene's end state
      if (start <= 2) startWorkflow();
      for (let k = start; k < SCENES.length; k++) await playScene(k, tok);
      setPhase("done");
      playingRef.current = false;
    } catch (e) {
      if (!(e instanceof Aborted)) throw e;
    }
  }, [playScene, startWorkflow]);

  const showEnd = (i: number) => {
    setIdx(i);
    setRevealed((r) => ({ ...r, [i]: true }));
    setTimeout(() => { sherin.focus(SCENES[i].destination); sherin.walkTo(SCENES[i].destination, sherin.token(), -70).catch(() => {}); sherin.pose(SCENES[i].gesture); }, 60);
  };

  // ------------------------------------------------------------------ user controls
  const play = () => { sherin.abort(); setLines([]); setRevealed({}); runFrom(0); };
  const pause = () => { sherin.pause(); setPhase("paused"); };
  const resume = () => { sherin.resume(); setPhase("playing"); };
  const skip = () => { const cur = idxRef.current; sherin.abort(); showEnd(cur); if (playingRef.current && cur + 1 < SCENES.length) runFrom(cur + 1, 3000); else { setPhase(playingRef.current ? "done" : "ready"); } };
  const replay = () => { const cur = idxRef.current; sherin.abort(); if (playingRef.current || phase === "done") runFrom(cur); else { const tok = sherin.token(); playScene(cur, tok).catch(() => {}); } };
  const jump = (k: number) => { sherin.abort(); if (playingRef.current) runFrom(k); else showEnd(k); };

  // synthetic approval (demo only): records nothing in the database
  const syntheticDecide = (d: "approved" | "rejected") => setEvents((xs) => {
    const base = xs.filter((e) => !["APPROVAL_DECIDED", "TASK_COMPLETED"].includes(e.event));
    const tail = syntheticEvents(SYNTHETIC_PLAN, d).slice(-2).map((e, j) => ({ ...e, seq: base.length + j }));
    return [...base, ...tail];
  });

  const sc = SCENES[idx];
  const reduced = ch.reducedPref || sherin.systemReduced();
  const ph = runPhase(events);
  return (
    <div>
      <PageHeader title="Sherin's Guided Journey" subtitle="Sherin walks executives through FLO Bank's money, agents and approvals. Charts stay fully interactive; the narration below carries every message for screen readers and reduced motion." />
      <Card className="sticky top-[92px] z-10 mb-4 p-3">
        <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label="Journey controls">
          {phase === "ready" || phase === "done" ? <Button onClick={play}><Play className="h-4 w-4" />Play Journey</Button>
            : phase === "playing" ? <Button onClick={pause} variant="outline"><Pause className="h-4 w-4" />Pause</Button>
              : <Button onClick={resume}><Play className="h-4 w-4" />Resume</Button>}
          <Button variant="outline" onClick={skip}><FastForward className="h-4 w-4" />Skip Animation</Button>
          <Button variant="outline" onClick={replay}><RotateCcw className="h-4 w-4" />Replay Scene</Button>
          <label className="flex items-center gap-1 text-xs text-muted">Jump to
            <select aria-label="Jump to scene" value={idx} onChange={(e) => jump(Number(e.target.value))} className="rounded-full border border-line px-2 py-1 text-xs font-semibold text-flo-900">
              {SCENES.map((s, i) => <option key={s.id} value={i}>{s.id}. {s.title}</option>)}
            </select></label>
          <label className="flex items-center gap-1 text-xs text-muted">Speed
            <select aria-label="Animation speed" value={ch.speed} onChange={(e) => sherin.setSpeed(Number(e.target.value))} className="rounded-full border border-line px-2 py-1 text-xs font-semibold text-flo-900">
              {[0.5, 1, 1.5, 2, 3].map((v) => <option key={v} value={v}>{v}×</option>)}
            </select></label>
          <Button variant="ghost" onClick={() => sherin.setMuted(!ch.muted)} title={ch.muted ? "Unmute" : "Mute"}>{ch.muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}{ch.muted ? "Unmute" : "Mute"}</Button>
          <Button variant="ghost" onClick={() => sherin.setReduced(!ch.reducedPref)}><Accessibility className="h-4 w-4" />{reduced ? "Motion reduced" : "Reduce motion"}</Button>
          <span className="ml-auto flex flex-wrap items-center gap-1.5 text-xs">
            <label className="flex items-center gap-1 text-muted">Events
              <select aria-label="Event source" value={mode} disabled={!!runId || phase === "playing"} onChange={(e) => { setMode(e.target.value as Mode); setEvents([]); }} className="rounded-full border border-line px-2 py-1 text-xs font-semibold">
                <option value="live">Live LangGraph run</option><option value="synthetic">Synthetic demo events</option>
              </select></label>
            {mode === "synthetic" ? <Badge tone="gold">synthetic events</Badge> : runId ? <Badge tone="green">live · {runId}</Badge> : <Badge>live run starts on play</Badge>}
            <StatusBadge s={phase} />
          </span>
        </div>
        <ol className="mt-3 grid grid-cols-7 gap-1" aria-label="Scenes">
          {SCENES.map((s, i) => (
            <li key={s.id}><button type="button" onClick={() => jump(i)} aria-current={i === idx ? "step" : undefined} data-testid={`scene-pill-${s.id}`}
              className={`w-full rounded-xl px-2 py-1.5 text-left text-[11px] leading-tight transition ${i === idx ? "bg-flo-800 text-white" : i < idx ? "bg-flo-100 text-flo-800" : "bg-flo-50 text-muted hover:bg-flo-100"}`}>
              <span className="font-bold">{s.id}</span> {s.title}</button></li>))}
        </ol>
        {runError && <p className="mt-2 text-xs text-amber">Live run unavailable ({runError}); switched to clearly labelled synthetic events.</p>}
      </Card>

      <div className="grid gap-4 2xl:grid-cols-[1fr_340px]">
        <AnimatePresence mode="wait">
          <motion.section key={sc.key} data-testid={`scene-${sc.id}`} aria-labelledby={`scene-title-${sc.id}`}
            initial={reduced ? false : { opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={reduced ? undefined : { opacity: 0, x: -40 }} transition={{ duration: reduced ? 0 : 0.35 }}>
            <Card className="p-5">
              <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
                <div><p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-flo-700">Scene {sc.id} of 7</p>
                  <h2 id={`scene-title-${sc.id}`} className="font-display text-3xl font-semibold text-flo-900">{sc.title}</h2>
                  <p className="text-sm text-muted">{sc.subtitle}</p></div>
                <div className="text-right text-xs text-muted"><div><span className="font-semibold text-flo-900">Agent state:</span> {sc.key === "harness" || sc.key === "approval" || sc.key === "summary" ? <RunPhaseBadge phase={ph} synthetic={mode === "synthetic"} /> : sc.agentState}</div>
                  <div>Destination: <code>{sc.destination}</code> · gesture: {sc.gesture}</div></div>
              </header>
              <Reveal on={!!revealed[idx]} reduced={reduced}>
                <SceneBody k={sc.key} events={events} runId={runId} mode={mode} onSyntheticDecision={syntheticDecide} />
              </Reveal>
            </Card>
          </motion.section>
        </AnimatePresence>
        <Card className="p-4">
          <h3 className="font-display text-lg font-semibold text-flo-900">Narration</h3>
          <p className="text-xs text-muted">Everything Sherin says and does, as text.</p>
          <ol className="mt-2 max-h-[520px] space-y-1.5 overflow-y-auto text-sm scroll-thin" aria-live="polite" data-testid="narration">
            {lines.map((l, i) => <li key={i} className="rounded-lg bg-flo-50 px-2 py-1"><span className="text-[10px] font-bold text-flo-700">Scene {l.scene}</span>{l.synthetic && <Badge tone="gold">synthetic</Badge>} {l.text}</li>)}
            {lines.length === 0 && <li className="text-xs text-muted">Press Play Journey.</li>}
          </ol>
          <h3 className="mt-4 font-display text-lg font-semibold text-flo-900">Execution events</h3>
          <ol className="mt-1 max-h-60 space-y-0.5 overflow-y-auto text-[11px] scroll-thin" data-testid="event-log">
            {events.map((e) => <li key={e.seq}><code className="text-flo-800">{e.event}</code> {e.agent && <span className="text-muted">{e.agent}</span>} {e.synthetic && <Badge tone="gold">synthetic</Badge>}</li>)}
          </ol>
        </Card>
      </div>
      <CharacterSheet />
    </div>
  );
}

function RunPhaseBadge({ phase, synthetic }: { phase: string; synthetic: boolean }) {
  return <span className="inline-flex items-center gap-1"><StatusBadge s={phase === "awaiting_approval" ? "awaiting_approval" : phase === "completed" ? "completed" : phase === "failed" ? "failed" : phase === "idle" ? "idle" : "running"} />{synthetic && <Badge tone="gold">synthetic</Badge>}</span>;
}

function Reveal({ on, reduced, children }: { on: boolean; reduced: boolean; children: ReactNode }) {
  return (
    <motion.div initial={false} animate={{ opacity: on ? 1 : 0.18, scale: on || reduced ? 1 : 0.985, filter: on ? "blur(0px)" : "blur(2px)" }} transition={{ duration: reduced ? 0 : 0.6 }}
      style={{ pointerEvents: on ? "auto" : "none" }} data-revealed={on ? "true" : "false"} data-testid="scene-reveal">
      {children}
    </motion.div>
  );
}

// ------------------------------------------------------------------------------------------- scene hooks (choreography)
interface HookCtx { tok: number; say: (t: string, tone?: "info" | "success" | "warning" | "error", synthetic?: boolean) => void; events: () => HarnessEvent[]; waitFor: (p: () => boolean, tok: number) => Promise<void>; scene: SceneDef }

const fmt = (v: number, c = "USD") => money(v, c);
async function getKpis(cur = "USD") { return api<any>("/finance/kpis", { params: { period: "month", value: "2026-10", currency: cur, dc: "synthetic" } }); }

function agentSelector(id: string) { return `.react-flow__node[data-id="agent:${id}"]`; }
function nodeSelector(id: string) { return `.react-flow__node[data-id="${id}"]`; }

const HOOKS: Record<string, (c: HookCtx) => Promise<void>> = {
  async revenue({ tok, say, scene }) {
    const k = await getKpis(); sherin.check(tok);
    const by = Object.fromEntries(k.cards.map((c: any) => [c.key, c]));
    await sherin.presentAt(scene.destination, "", tok);
    say(`FLO Bank earned ${fmt(by.bank_revenue.value)} in ${k.period.label} (${pctChange(by.bank_revenue.mom_pct)} vs prior), with operating profit of ${fmt(by.operating_profit.value)}. Synthetic demo figures.`, "info", true);
  },
  async expenditure({ tok, say, scene }) {
    const d = await api<any>("/finance/cost-drivers", { params: { period: "month", value: "2026-10" } }); sherin.check(tok);
    const top = [...d.by_category].sort((a: any, b: any) => b.delta_per_day - a.delta_per_day)[0];
    sherin.pose("think");
    say(`AI spend moved from ${fmt(d.total_per_day.baseline)} to ${fmt(d.total_per_day.current)} per day.`);
    await sherin.sleep(1400, tok);
    await sherin.presentAt(scene.destination, "", tok);
    say(`The largest increase is ${top.label}: +${fmt(top.delta_per_day)} per day. Click its bar to inspect the cost records.`, "info");
  },
  async harness({ tok, say, events, waitFor }) {
    say("I'm following the live execution path. Every move below comes from a recorded LangGraph event.", "info", events()[0]?.synthetic);
    let cursor = 0;
    for (;;) {
      await waitFor(() => events().length > cursor, tok);
      const e = events()[cursor++];
      const d = directiveFor(e);
      if (d.target?.kind === "agent") await sherin.walkTo(agentSelector(d.target.id), tok, -30);
      else if (d.target?.kind === "node") await sherin.walkTo(nodeSelector(d.target.id), tok, -30);
      sherin.pose(d.target?.kind === "manager" ? "point" : d.pose);
      say(`${e.event}: ${d.say}`, d.tone, e.synthetic);
      await sherin.sleep(d.minMs, tok);
      if (e.event === "APPROVAL_REQUIRED" || e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED") break;
    }
  },
  async "human-vs-ai"({ tok, say, scene }) {
    const [u, i, c] = await Promise.all([getKpis("USD"), getKpis("INR"), getKpis("CAD")]); sherin.check(tok);
    const g = (k: any, key: string) => k.cards.find((x: any) => x.key === key);
    await sherin.walkTo("#graph-c", tok, -80); sherin.pose("point");
    say(`${g(u, "verified_work").value} verified tasks replaced ${Math.round(g(u, "verified_work").sub.human_hours_equivalent).toLocaleString()} hours of equivalent human effort.`);
    await sherin.sleep(1800, tok);
    await sherin.presentAt(scene.destination, "", tok);
    say(`Estimated savings ${fmt(g(u, "cost_avoidance").value)} · ${fmt(g(i, "cost_avoidance").value, "INR")} · ${fmt(g(c, "cost_avoidance").value, "CAD")}. ROI ${g(u, "roi").value}% in every currency.`, "info", true);
  },
  async guardian({ tok, say, scene }) {
    const r = await api<any>("/guardian/proposals/TP-1003/evaluate", { method: "POST", body: { advisory: [] } }); sherin.check(tok);
    await sherin.walkTo("#scene-exposure", tok, -60); sherin.pose("think");
    say("Checking sector and issuer exposure before and after the trade…");
    await sherin.sleep(1800, tok);
    await sherin.presentAt(scene.destination, "", tok, "info", "point");
    const liq = r.checks.find((c: any) => c.id === "liquidity"), esg = r.checks.find((c: any) => c.id === "esg_score");
    say(`Guardian: ${r.decision}. Liquidity ${liq.status} (${liq.detail}) ESG ${esg.status} (${esg.detail}) ${r.meaning}`, r.decision === "BLOCK" ? "error" : r.decision === "PASS" ? "info" : "warning");
  },
  async approval({ tok, say, events, waitFor }) {
    await waitFor(() => events().some((e) => e.event === "APPROVAL_REQUIRED" || e.event === "TASK_FAILED"), tok);
    await sherin.walkTo("#manager-desk", tok, -150);
    sherin.focus("#manager-desk");
    sherin.pose("waiting");
    const req = events().find((e) => e.event === "APPROVAL_REQUIRED");
    say(`I've brought approval request ${req?.approval_id ?? ""} to the manager. The workflow stays paused until an authorized decision is recorded.`, "info", req?.synthetic);
    await waitFor(() => events().some((e) => e.event === "APPROVAL_DECIDED" || e.event === "TASK_FAILED" || (e.event === "APPROVAL_REQUIRED" && e.approval_status === "blocked")), tok);
    const dec = [...events()].reverse().find((e) => e.event === "APPROVAL_DECIDED");
    const d = dec ? directiveFor(dec) : directiveFor(req!);
    sherin.pose(d.pose);
    say(d.say, d.tone, dec?.synthetic);
  },
  async summary({ tok, say, events, waitFor, scene }) {
    if (!events().some((e) => e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED")) {
      sherin.pose("waiting");
      say("Waiting for the workflow to finish. I won't report success before it does.");
    }
    await waitFor(() => events().some((e) => e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED"), tok);
    await sherin.presentAt(scene.destination, "", tok);
    const done = [...events()].reverse().find((e) => e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED")!;
    const d = directiveFor(done);
    sherin.pose(canCelebrate(events()) ? "success" : d.pose === "success" ? "warning" : d.pose);
    say(`${d.say} ${done.action_outcome ? `Action: ${done.action_outcome}.` : ""}`, canCelebrate(events()) ? "success" : d.tone, done.synthetic);
  },
};

// ------------------------------------------------------------------------------------------- scene bodies (real data, interactive)
function SceneBody({ k, events, runId, mode, onSyntheticDecision }: { k: string; events: HarnessEvent[]; runId: string | null; mode: Mode; onSyntheticDecision: (d: "approved" | "rejected") => void }) {
  switch (k) {
    case "revenue": return <RevenueScene />;
    case "expenditure": return <ExpenditureScene />;
    case "harness": return <HarnessScene events={events} runId={runId} />;
    case "human-vs-ai": return <HumanAiScene />;
    case "guardian": return <GuardianScene />;
    case "approval": return <ApprovalScene events={events} mode={mode} onSyntheticDecision={onSyntheticDecision} />;
    default: return <SummaryScene events={events} runId={runId} />;
  }
}

function BigNumbers({ items }: { items: [string, string, string?][] }) {
  return <div className="mb-3 grid gap-2 sm:grid-cols-3">{items.map(([l, v, sub]) => <div key={l} className="kpi-hero rounded-2xl p-4 text-white"><div className="text-[11px] uppercase tracking-wider text-white/80">{l}</div><div className="font-display text-3xl font-semibold tnum">{v}</div>{sub && <div className="text-xs text-flo-100">{sub}</div>}</div>)}</div>;
}

function useKpis(cur?: string) {
  const app = useApp();
  return useApi<any>("/finance/kpis", { ...periodParams({ ...app, periodKind: "month", month: "2026-10" }), ...(cur ? { currency: cur } : {}) });
}
const card = (k: any, key: string) => k?.cards?.find((c: any) => c.key === key);

function RevenueScene() {
  const { data } = useKpis(); const { currency } = useApp();
  return <div>{data && <BigNumbers items={[["Bank revenue", money(card(data, "bank_revenue").value, currency), `${pctChange(card(data, "bank_revenue").mom_pct)} MoM`], ["Operating expenditure", money(card(data, "bank_opex").value, currency)], ["Operating profit", money(card(data, "operating_profit").value, currency), `${pctChange(card(data, "operating_profit").mom_pct)} MoM`]]} />}<GraphA /></div>;
}

function ExpenditureScene() {
  const { data } = useKpis(); const { currency, dc } = useApp();
  const tok = useApi<any>("/finance/tokens", { period: "month", value: "2026-10", currency, dc, granularity: "month" });
  const ai = card(data, "ai_cost");
  return (
    <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
      <div className="rounded-2xl border border-line p-3"><CostDriversChart id="scene-drivers" height={380} /></div>
      <div className="space-y-3">
        {ai && <div className="rounded-2xl border border-line p-3"><div className="text-sm font-semibold text-flo-900">AI budget usage</div>
          <Plot ariaLabel="AI budget utilisation gauge" height={190} data={[{ type: "indicator", mode: "gauge+number", value: ai.budget_utilization_pct, number: { suffix: "%" },
            gauge: { axis: { range: [0, 120] }, bar: { color: ai.budget_utilization_pct > 100 ? SERIES.cost : SERIES.revenue }, steps: [{ range: [80, 100], color: "#FBF1E1" }, { range: [100, 120], color: "#F8E8E7" }] } }]}
            layout={{ margin: { l: 20, r: 20, t: 10, b: 0 }, showlegend: false }} />
          <p className="text-xs text-muted">{money(ai.value, currency)} of {money(ai.budget, currency)} budget · infrastructure, inference, review and implementation</p></div>}
        {tok.data && <div className="rounded-2xl border border-line p-3 text-sm"><div className="font-semibold text-flo-900">Token consumption</div>
          <div className="mt-1 grid grid-cols-2 gap-2">{Object.entries(tok.data.providers).map(([p, v]: any) => <div key={p} className="rounded-xl bg-flo-50 p-2"><div className="text-[10px] uppercase text-muted">{p === "local_qwen" ? "Local Qwen" : "Paid model"}</div><div className="font-display text-xl font-semibold">{(v.total / 1e6).toFixed(1)}M</div><div className="text-xs">{money(v.cost, currency)}</div></div>)}</div></div>}
      </div>
    </div>
  );
}

function HarnessScene({ events, runId }: { events: HarnessEvent[]; runId: string | null }) {
  const { currency } = useApp();
  const agents = useApi<any>("/harness/agents", { period: "month", value: "2026-10" });
  const run = useApi<any>(runId ? `/harness/runs/${runId}` : null, { n: events.length });
  const syntheticRun = useMemo(() => (runId ? null : { id: "synthetic", status: "running", plan: SYNTHETIC_PLAN, trace: events.map((e) => ({ node: e.event === "RUN_PLANNED" ? "plan_task" : e.event.startsWith("VALIDATION") ? "verify" : e.event.startsWith("APPROVAL") ? "approval_gate" : e.event === "TASK_COMPLETED" ? "finalize" : "execute_step" })), result: {} }), [runId, events]);
  return <div><AgentGraph agents={agents.data?.agents ?? []} run={run.data ?? syntheticRun} cur={currency} height={460} /><Note>Sherin moves to each agent as its AGENT_STARTED event arrives, works while TOOL_RUNNING, and walks to the verify node on VALIDATION_STARTED.</Note></div>;
}

function HumanAiScene() {
  const u = useKpis("USD"), i = useKpis("INR"), c = useKpis("CAD");
  const rows = [u.data, i.data, c.data].filter(Boolean).map((k: any) => ({ cur: k.fx.currency, savings: money(card(k, "cost_avoidance").value, k.fx.currency), net: money(k.net_benefit, k.fx.currency), roi: `${card(k, "roi").value}%`, rate: k.fx.currency === "USD" ? "base" : `${k.fx.rate} (${k.fx.source})` }));
  const v = card(u.data, "verified_work");
  return (
    <div className="space-y-3">
      {v && <BigNumbers items={[["Verified work", v.value.toLocaleString(), `of ${v.sub.total_tasks.toLocaleString()} tasks`], ["Human effort avoided", `${Math.round(v.sub.human_hours_equivalent).toLocaleString()} h`, "baseline hours of verified work"], ["AI ROI", `${card(u.data, "roi").value}%`, "net benefit / total AI cost"]]} />}
      <div id="scene-roi" className="rounded-2xl border border-line p-3"><Table dense columns={[{ key: "cur", label: "Currency" }, { key: "savings", label: "Estimated savings", align: "right" }, { key: "net", label: "Net AI benefit", align: "right" }, { key: "roi", label: "ROI", align: "right" }, { key: "rate", label: "FX rate (source)" }]} rows={rows} /></div>
      <GraphC />
    </div>
  );
}

function GuardianScene() {
  const [r, setR] = useState<any>(null);
  useEffect(() => { api("/guardian/proposals/TP-1003/evaluate", { method: "POST", body: { advisory: [] } }).then(setR).catch(() => {}); }, []);
  if (!r) return null;
  const rows = r.checks.filter((c: any) => ["liquidity", "esg_score", "sector_exclusion", "mandate_asset_class", "restricted_list", "concentration_issuer", "concentration_sector", "market_risk"].includes(c.id));
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <div id="scene-exposure" className="rounded-2xl border border-line p-3"><div className="text-sm font-semibold">TP-1003 · {r.portfolio} · sector exposure pre vs post (%)</div>
        <Plot ariaLabel="Sector exposure" height={360} data={[{ type: "bar", name: "Pre-trade", x: r.exposures.by_sector.map((e: any) => e.sector), y: r.exposures.by_sector.map((e: any) => e.pre_pct), marker: { color: SERIES.opex } }, { type: "bar", name: "Post-trade", x: r.exposures.by_sector.map((e: any) => e.sector), y: r.exposures.by_sector.map((e: any) => e.post_pct), marker: { color: SERIES.revenue } }]} layout={{ barmode: "group" }} /></div>
      <div id="scene-controls" className="rounded-2xl border border-line p-3">
        <div className="mb-1 flex items-center justify-between text-sm font-semibold">Policy controls <DecisionBadge d={r.decision} /></div>
        <Table dense columns={[{ key: "name", label: "Control" }, { key: "status", label: "Result", render: (c) => <DecisionBadge d={c.status} /> }, { key: "detail", label: "Evidence" }]} rows={rows} />
        <Note>{r.meaning} VaR (1-day 99%): {money(r.risk.var_99_1d_usd)}.</Note>
      </div>
    </div>
  );
}

function ManagerDesk() {
  return (
    <svg viewBox="0 0 260 170" className="h-44 w-auto" role="img" aria-label="The manager's desk">
      <rect x="0" y="150" width="260" height="6" rx="3" fill="#DCE8E2" />
      <rect x="150" y="60" width="44" height="66" rx="8" fill="#0B3D2E" />
      <circle cx="172" cy="42" r="15" fill="#C9A88E" /><path d="M157 38 q15 -18 30 0 q-6 -8 -15 -6 q-9 -2 -15 6z" fill="#4A3B33" />
      <path d="M150 74 l-18 26 l10 4 l14 -18z" fill="#0B3D2E" />
      <rect x="20" y="96" width="210" height="10" rx="3" fill="#8A6A4A" /><rect x="34" y="106" width="8" height="44" fill="#7A5D40" /><rect x="208" y="106" width="8" height="44" fill="#7A5D40" />
      <rect x="70" y="62" width="50" height="32" rx="3" fill="#13795B" /><rect x="92" y="94" width="6" height="4" fill="#5B6B65" />
      <rect x="40" y="86" width="34" height="10" rx="2" fill="#F7E9D3" stroke="#B8913A" /><text x="57" y="93.5" fontSize="5.6" textAnchor="middle" fill="#7A5D1E">SHERIN_MANAGER</text>
      <path d="M220 96 q-6 -24 4 -36 q6 14 -1 36z" fill="#2BB673" /><rect x="216" y="88" width="10" height="9" rx="2" fill="#B8913A" />
    </svg>
  );
}

function ApprovalScene({ events, mode, onSyntheticDecision }: { events: HarnessEvent[]; mode: Mode; onSyntheticDecision: (d: "approved" | "rejected") => void }) {
  const req = events.find((e) => e.event === "APPROVAL_REQUIRED");
  const ap = useApi<any>(req && !req.synthetic ? `/approvals/${req.approval_id}` : null, { n: events.length }, req && !events.some((e) => e.event === "APPROVAL_DECIDED") ? 2500 : undefined);
  const decided = events.find((e) => e.event === "APPROVAL_DECIDED");
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_1.1fr]">
      <div id="manager-desk" className="flex flex-col items-center justify-end rounded-2xl border border-line bg-gradient-to-b from-white to-flo-50 p-4"><ManagerDesk />
        <p className="mt-2 text-center text-sm text-muted">{decided ? <>Decision recorded: <strong className="text-flo-900">{decided.status?.replace(/_/g, " ")}</strong></> : req ? "Workflow paused at the approval gate." : "Waiting for the run to reach the approval gate…"}</p></div>
      <div>
        {!req && <Note>No approval has been requested yet. The run must finish its agent steps and pass validation first.</Note>}
        {req && !req.synthetic && ap.data && <ApprovalCard a={ap.data} onChange={() => ap.reload()} />}
        {req?.synthetic && (
          <div className="rounded-2xl border border-line p-4 text-sm"><Badge tone="gold">synthetic demo approval</Badge>
            <p className="mt-2">BUY Woodgrove Financial (PF-BAL), Guardian PASS. A PASS is not authorization to trade. Requires SHERIN_MANAGER.</p>
            <p className="text-xs text-muted">Demo mode: nothing is written to the approvals database.</p>
            {!decided && <div className="mt-2 flex gap-2"><Button onClick={() => onSyntheticDecision("approved")}>Record demo approval</Button><Button variant="danger" onClick={() => onSyntheticDecision("rejected")}>Record demo rejection</Button></div>}
          </div>
        )}
        {mode === "live" && <Note>Approvals enforce roles and segregation of duties. The run was requested by pm.ananya (portfolio manager), so a manager such as mgr.sherin can decide.</Note>}
      </div>
    </div>
  );
}

function SummaryScene({ events, runId }: { events: HarnessEvent[]; runId: string | null }) {
  const { data: k } = useKpis(); const { currency } = useApp();
  const run = useApi<any>(runId ? `/harness/runs/${runId}` : null, { n: events.length });
  const done = [...events].reverse().find((e) => e.event === "TASK_COMPLETED" || e.event === "TASK_FAILED");
  const res = run.data?.result;
  return (
    <div id="scene-summary" className="space-y-3">
      {k && <BigNumbers items={[["Net AI economic benefit", money(k.net_benefit, currency), k.period.label + " · synthetic"], ["Sherin AI cost", money(card(k, "ai_cost").value, currency)], ["AI ROI", `${card(k, "roi").value}%`]]} />}
      {!done ? <Note>The workflow has not finished. The outcome will appear here only after the TASK_COMPLETED event is recorded.</Note> : (
        <div className="rounded-2xl border border-line p-4 text-sm">
          <div className="flex flex-wrap items-center gap-2"><strong className="font-display text-lg text-flo-900">Run outcome</strong>{done.verified ? <Badge tone="green">verified</Badge> : <Badge tone="red">not verified</Badge>}{done.synthetic && <Badge tone="gold">synthetic events</Badge>}<Badge>{done.action_outcome ?? done.event}</Badge></div>
          {res?.sentence && <p className="mt-2">{res.sentence}</p>}
          {res && <Table dense columns={[{ key: "k", label: "Cost and evidence" }, { key: "v", label: "Value", align: "right" }]} rows={[
            { k: "Allocated cost (model + compute + review)", v: money(res.allocated_cost_usd) }, { k: "Human baseline", v: `${res.human_baseline_hours} h · ${money(res.human_baseline_usd)}` },
            { k: "Estimated saving (verified only)", v: money(res.estimated_saving_usd) }, { k: "Human review", v: `${res.human_review_minutes} min (${res.human_review_basis})` },
            { k: "Verification checks passed", v: `${(res.verification ?? []).filter((c: any) => c.verified).length}/${(res.verification ?? []).length}` }, { k: "Approval", v: res.approval_id ?? "—" }]} />}
          {done.synthetic && <Note>Synthetic demonstration events: no run, cost or approval was recorded.</Note>}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------- character sheet (for approval)
export const SHEET: { label: string; pose: Pose; facing: 1 | -1 }[] = [
  { label: "Idle", pose: "idle", facing: 1 }, { label: "Walking left", pose: "walk", facing: -1 }, { label: "Walking right", pose: "walk", facing: 1 },
  { label: "Turning", pose: "turn", facing: 1 }, { label: "Pointing", pose: "point", facing: 1 }, { label: "Thinking", pose: "think", facing: 1 },
  { label: "Working", pose: "work", facing: 1 }, { label: "Success", pose: "success", facing: 1 }, { label: "Warning", pose: "warning", facing: 1 },
  { label: "Waiting for approval", pose: "waiting", facing: 1 }, { label: "Error", pose: "error", facing: 1 },
];

function CharacterSheet() {
  return (
    <Card className="mt-4 p-5" id="character-sheet">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="font-display text-xl font-semibold text-flo-900">Character sheet — for approval</h2>
          <p className="text-sm text-muted">One rig, eleven states. Asset <code>{CHARACTER_ASSET.id}</code> v{CHARACTER_ASSET.version}: <Badge tone="amber">{CHARACTER_ASSET.status}</Badge></p></div>
        <div className="flex items-center gap-2 text-xs text-muted"><SherinAvatar size="lg" />Approved portrait (canonical face reference)</div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6 xl:grid-cols-11" data-testid="character-sheet">
        {SHEET.map((s) => <figure key={s.label} className="flex flex-col items-center rounded-xl bg-flo-50 p-2"><SherinCharacter pose={s.pose} facing={s.facing} height={120} /><figcaption className="mt-1 text-center text-[11px] font-semibold text-flo-900">{s.label}</figcaption></figure>)}
      </div>
      <Note>The approved portrait file is not in the repository yet, so the face is drawn to the brief (long black hair, orange-red outfit, soft Ghibli-style features). Before release, an illustrator should match this rig to the portrait, or replace it with a Rive or Spine file exported from the approved design. The rig's pose names are the animation contract, so a replacement drops in without code changes.</Note>
    </Card>
  );
}
