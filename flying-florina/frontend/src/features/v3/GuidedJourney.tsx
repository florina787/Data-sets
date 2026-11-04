import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { FastForward, Pause, Play, RotateCcw, Wind } from "lucide-react";
import { Chart } from "@/components/Chart";
import { DependencyGraph } from "@/components/DependencyGraph";
import { Badge, ErrorBox, Skeleton } from "@/components/ui";
import { get, post } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { pct, usd } from "./common";

/* ---------------------------------------------------------------------------------------------
 * Guided Journey: the Flying Florina emblem flies from scene to scene (supply chain first) and
 * hovers over the evidence it is talking about. Every number it says is read from the same APIs
 * the full pages use, so narration can never drift from the charts. All data is synthetic.
 * ------------------------------------------------------------------------------------------- */

type Supplier = { id: string; name: string; region: string; on_time_rate: number; late_probability_open_orders: number; deliveries: number };
type Overview = {
  suppliers: Supplier[];
  concentration: { category: string; suppliers: number; single_source: boolean }[];
  graph: { nodes: { id: string; label: string; kind: string }[]; edges: { source: string; target: string; share: number }[] };
  late_delivery_eval: { precision: number; recall: number; f1: number };
};
type Impact = {
  supplier: { name: string }; delay_days: number; horizon_days: number;
  affected_categories: { category: string; share: number }[];
  scenarios: { scenario: string; deferred_maintenance_hours: number; cost_usd: number }[];
};
type CompRow = { category: string; p10: number; p50: number; p90: number; stockout_sites: number; max_stockout_prob: number; cost_p50_usd: number };
type Comp = { horizon_days: number; rows: CompRow[] };
type Heat = { x: string[]; y: string[]; cells: number[][]; unit: string };
type Unit = { id: string; serial: string; facility_id: string; category_id: string; last_health: number; rul_p50: number | null; rul_p10: number | null; status: string };
type VisEval = { method: string; is_ai: boolean; precision: number; recall: number; n: number; fp: number; by_object: Record<string, { n: number; flagged_drone_like: number }> };
type ResRes = { backlog_p50: number[]; peak_backlog_hours: number; recovery_weeks_after_disruption?: number | null; cost_p50_usd: number };
type Sim = { label: string; weeks: number[]; results: { baseline: ResRes; disruption: ResRes; recovery: ResRes } };
type CT = { runs: { id: string; workflow: string; query: string; status: string }[]; selected?: { nodes: { step: string; agent: string; status: string }[]; tools: { tool: string; status: string }[]; plan?: { outcome?: string } } };

const SCENARIO_LABEL: Record<string, string> = { baseline: "No delay", delay: "Delay, do nothing", alternate: "Alternate supplier", transfer: "Move warehouse stock" };
const MITIGATION = { overtime_capacity: 0.15, delay_reduction: 0.5, demand_deferral: 0.1 };

function useJourneyData() {
  const supply = useQuery({ queryKey: ["gj-supply"], queryFn: () => get<Overview>("/api/supply/overview"), staleTime: 300_000 });
  const impact = useQuery({ queryKey: ["gj-impact"], queryFn: () => post<Impact>("/api/supply/delay-impact", { supplier_id: "S1", delay_days: 14, horizon_days: 60 }), staleTime: 300_000 });
  const comp = useQuery({ queryKey: ["gj-comp"], queryFn: () => get<Comp>("/api/forecast/components?horizon=30"), staleTime: 300_000 });
  const heat = useQuery({ queryKey: ["gj-heat"], queryFn: () => get<Heat>("/api/forecast/heatmap?horizon=30"), staleTime: 300_000 });
  const units = useQuery({ queryKey: ["gj-units"], queryFn: () => get<Unit[]>("/api/twin/units"), staleTime: 300_000 });
  const vis = useQuery({ queryKey: ["gj-vis"], queryFn: () => get<VisEval>("/api/visual/evaluation"), staleTime: 300_000 });
  const res = useQuery({
    queryKey: ["gj-res"], staleTime: 300_000,
    queryFn: async () => {
      const sc = await get<{ scenarios: { id: string; defaults: Record<string, string | number> }[] }>("/api/resilience/scenarios");
      const def = sc.data.scenarios.find((s) => s.id === "facility_outage");
      return post<Sim>("/api/resilience/simulate", { scenario: "facility_outage", params: def?.defaults ?? {}, mitigation: MITIGATION });
    },
  });
  const ct = useQuery({ queryKey: ["gj-ct"], queryFn: () => get<CT>("/api/harness/control-tower"), staleTime: 60_000 });
  return { supply, impact, comp, heat, units, vis, res, ct };
}
type Data = ReturnType<typeof useJourneyData>;

type SceneDef = {
  id: string; title: string; subtitle: string; source: string;
  ready: (d: Data) => boolean;
  error: (d: Data) => unknown;
  intro: string;
  stops: (d: Data) => string[];
  body: (d: Data) => ReactNode;
};

const Stop = ({ n, children, className = "" }: { n: number; children: ReactNode; className?: string }) => (
  <div data-stop={n} className={`gj-stop rounded-2xl ${className}`}>{children}</div>
);
const Big = ({ k, v, hint }: { k: string; v: ReactNode; hint?: string }) => (
  <div className="gj-big rounded-2xl p-4">
    <p className="label">{k}</p>
    <p className="font-serif mt-1 text-3xl leading-none">{v}</p>
    {hint && <p className="muted mt-1.5 text-xs">{hint}</p>}
  </div>
);

const SCENES: SceneDef[] = [
  {
    id: "supply", title: "Supply Chain", subtitle: "Which suppliers are likely to deliver late?", source: "GET /api/supply/overview",
    ready: (d) => !!d.supply.data, error: (d) => d.supply.error,
    intro: "Let's start where shortages begin: the suppliers.",
    stops: (d) => {
      const o = d.supply.data!.data; const s = [...o.suppliers].sort((a, b) => b.late_probability_open_orders - a.late_probability_open_orders);
      return [
        `${s[0].name} is the riskiest: ${s[0].late_probability_open_orders >= 0.995 ? "over 99%" : pct(s[0].late_probability_open_orders)} chance its open orders arrive late.`,
        `The late-delivery model was tested on held-out orders: precision ${pct(o.late_delivery_eval.precision)}, recall ${pct(o.late_delivery_eval.recall)}.`,
      ];
    },
    body: (d) => {
      const o = d.supply.data!.data; const s = [...o.suppliers].sort((a, b) => b.late_probability_open_orders - a.late_probability_open_orders);
      return (
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Stop n={0} className="p-1"><Chart title="late probability by supplier" height={300} spec={{ kind: "bar", x: s.map((x) => x.name.split(" ")[0]), series: [{ name: "late probability (open orders)", data: s.map((x) => +x.late_probability_open_orders.toFixed(3)) }] }} /></Stop>
          <Stop n={1} className="grid content-start gap-3">
            <Big k="Precision" v={pct(o.late_delivery_eval.precision)} hint="of orders flagged late, share that were late" />
            <Big k="Recall" v={pct(o.late_delivery_eval.recall)} hint="of late orders, share the model caught" />
            <Big k="Suppliers" v={o.suppliers.length} hint="fictional, synthetic delivery history" />
          </Stop>
        </div>
      );
    },
  },
  {
    id: "delay", title: "Supplier Delay", subtitle: "What if Veltrion Hydraulics is 14 days late?", source: "POST /api/supply/delay-impact",
    ready: (d) => !!d.impact.data, error: (d) => d.impact.error,
    intro: "Now a what-if: our hydraulics supplier slips by two weeks.",
    stops: (d) => {
      const i = d.impact.data!.data; const by = Object.fromEntries(i.scenarios.map((s) => [s.scenario, s]));
      const opts = i.scenarios.filter((s) => s.scenario !== "baseline" && s.scenario !== "delay").sort((a, b) => a.deferred_maintenance_hours - b.deferred_maintenance_hours);
      const best = opts[0];
      return [
        `${i.affected_categories.length} part families depend on this supplier, from ${i.affected_categories.map((c) => c.category.toLowerCase()).slice(0, 2).join(" to ")}.`,
        `Doing nothing defers ${Math.round(by.delay.deferred_maintenance_hours)} maintenance hours. ${SCENARIO_LABEL[best.scenario]} cuts that to ${Math.round(best.deferred_maintenance_hours)}.`,
      ];
    },
    body: (d) => {
      const i = d.impact.data!.data;
      return (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <Stop n={0} className="space-y-2 p-1">
            {i.affected_categories.map((c) => (
              <div key={c.category} className="gj-big flex items-center justify-between rounded-xl px-4 py-2.5 text-sm">
                <span>{c.category}</span><Badge tone={c.share >= 0.8 ? "red" : "amber"}>{pct(c.share)} of supply</Badge>
              </div>
            ))}
          </Stop>
          <Stop n={1} className="p-1"><Chart title="deferred hours by option" height={290} spec={{ kind: "bar", x: i.scenarios.map((s) => SCENARIO_LABEL[s.scenario] ?? s.scenario), series: [{ name: "deferred maintenance hours", data: i.scenarios.map((s) => s.deferred_maintenance_hours) }] }} /></Stop>
        </div>
      );
    },
  },
  {
    id: "inventory", title: "Inventory Forecast", subtitle: "How many parts will we need in the next 30 days?", source: "GET /api/forecast/components",
    ready: (d) => !!d.comp.data, error: (d) => d.comp.error,
    intro: "Next, demand: how many removals the models expect over 30 days.",
    stops: (d) => {
      const r = d.comp.data!.data.rows; const top = [...r].sort((a, b) => b.p50 - a.p50)[0];
      const p50 = r.reduce((a, x) => a + x.p50, 0); const short = r.reduce((a, x) => a + x.stockout_sites, 0);
      return [
        `${top.category} lead demand: ${Math.round(top.p50)} expected, somewhere between ${Math.round(top.p10)} and ${Math.round(top.p90)}.`,
        `Across all hubs: about ${Math.round(p50)} removals and ${short} site-level shortage risks. Ranges, not promises.`,
      ];
    },
    body: (d) => {
      const r = [...d.comp.data!.data.rows].sort((a, b) => b.p50 - a.p50).slice(0, 10);
      const all = d.comp.data!.data.rows;
      return (
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Stop n={0} className="p-1"><Chart title="demand ranges" height={300} spec={{ kind: "bar", x: r.map((x) => x.category.replace(/ (units|assemblies|sensors)$/, "")), series: [
            { name: "P10", data: r.map((x) => x.p10) }, { name: "P50", data: r.map((x) => x.p50) }, { name: "P90", data: r.map((x) => x.p90) }] }} /></Stop>
          <Stop n={1} className="grid content-start gap-3">
            <Big k="Removals P50, 30 days" v={Math.round(all.reduce((a, x) => a + x.p50, 0))} hint="sum over every component family" />
            <Big k="Shortage risks" v={all.reduce((a, x) => a + x.stockout_sites, 0)} hint="site × family with ≥20% stockout chance" />
            <Big k="Parts cost P50" v={usd(all.reduce((a, x) => a + x.cost_p50_usd, 0))} hint="synthetic unit prices" />
          </Stop>
        </div>
      );
    },
  },
  {
    id: "deps", title: "Dependency Map", subtitle: "Which supplier feeds which component?", source: "GET /api/supply/overview (graph)",
    ready: (d) => !!d.supply.data, error: (d) => d.supply.error,
    intro: "Let me fly over the dependency map: suppliers on one side, parts on the other.",
    stops: (d) => {
      const c = d.supply.data!.data.concentration; const single = c.filter((x) => x.single_source);
      return [
        `Each line links a supplier to a part family and is labelled with its share of supply.`,
        `${single.length} of ${c.length} part families have a single source, ${single[0]?.category.toLowerCase() ?? "none"} among them. That is where a delay hurts most.`,
      ];
    },
    body: (d) => {
      const o = d.supply.data!.data;
      const nodes: GraphNode[] = o.graph.nodes.map((n) => ({ id: n.id, label: n.label, type: n.kind === "supplier" ? "system" : "entity" }));
      const edges: GraphEdge[] = o.graph.edges.map((e, i) => ({ id: `e${i}`, source: e.source, target: e.target, label: pct(e.share), kind: "supplies" }));
      const single = o.concentration.filter((x) => x.single_source);
      return (
        <div className="space-y-4">
          <Stop n={0} className="overflow-hidden"><DependencyGraph nodes={nodes} edges={edges} height={360} /></Stop>
          <Stop n={1} className="p-1">
            <p className="label mb-2">Single-source families</p>
            <div className="flex flex-wrap gap-2">{single.map((s) => <span key={s.category} className="gj-big rounded-full px-3.5 py-1.5 text-sm">{s.category}</span>)}</div>
          </Stop>
        </div>
      );
    },
  },
  {
    id: "heat", title: "Heatmap", subtitle: "Labour hours needed: every hub × every component", source: "GET /api/forecast/heatmap",
    ready: (d) => !!d.heat.data, error: (d) => d.heat.error,
    intro: "Here is where the work lands: the maintenance heatmap.",
    stops: (d) => {
      const h = d.heat.data!.data; const max = h.cells.reduce((m, c) => (c[2] > m[2] ? c : m), h.cells[0]);
      const byHub = h.x.map((_, xi) => h.cells.filter((c) => c[0] === xi).reduce((a, c) => a + c[2], 0));
      const hub = byHub.indexOf(Math.max(...byHub));
      return [
        `The hottest cell is ${h.x[max[0]]} × ${h.y[max[1]].toLowerCase()}: about ${Math.round(max[2])} labour hours in 30 days.`,
        `${h.x[hub]} carries the most work overall, ${Math.round(byHub[hub])} hours. Plan the hangar crews there first.`,
      ];
    },
    body: (d) => {
      const h = d.heat.data!.data;
      const byHub = h.x.map((name, xi) => ({ name, hours: h.cells.filter((c) => c[0] === xi).reduce((a, c) => a + c[2], 0) }));
      return (
        <div className="grid gap-4 lg:grid-cols-[1.9fr_1fr]">
          <Stop n={0} className="p-1"><Chart title="heatmap" height={420} spec={{ kind: "heatmap", x: h.x, y: h.y, cells: h.cells, series: [] }} /></Stop>
          <Stop n={1} className="space-y-2 p-1">
            <p className="label">Labour hours by hub, 30 days</p>
            {[...byHub].sort((a, b) => b.hours - a.hours).map((b) => (
              <div key={b.name} className="gj-big flex items-center justify-between rounded-xl px-4 py-2 text-sm"><span>{b.name}</span><span className="font-serif text-lg">{Math.round(b.hours)} h</span></div>
            ))}
          </Stop>
        </div>
      );
    },
  },
  {
    id: "twin", title: "Digital Twin", subtitle: "Which installed parts are wearing out?", source: "GET /api/twin/units",
    ready: (d) => !!d.units.data, error: (d) => d.units.error,
    intro: "Now down to individual aircraft parts: the digital twin.",
    stops: (d) => {
      const u = d.units.data!.data.filter((x) => x.status === "installed"); const worst = [...u].sort((a, b) => a.last_health - b.last_health)[0];
      const soon = u.filter((x) => (x.rul_p50 ?? 999) < 26).length;
      return [
        `Unit ${worst.serial} (${worst.category_id.replace(/_/g, " ")}) is the weakest: health ${worst.last_health.toFixed(2)}.`,
        `${soon} of ${u.length} installed units may reach end of life within 26 weeks. Advisory only: a licensed engineer decides.`,
      ];
    },
    body: (d) => {
      const u = d.units.data!.data.filter((x) => x.status === "installed"); const worst = [...u].sort((a, b) => a.last_health - b.last_health).slice(0, 6);
      return (
        <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <Stop n={0} className="space-y-2 p-1">
            {worst.map((w) => (
              <div key={w.id} className="gj-big rounded-xl px-4 py-2.5 text-sm">
                <div className="flex items-center justify-between gap-2"><span className="font-medium">{w.serial} · {w.category_id.replace(/_/g, " ")}</span><span className="muted text-xs">{w.facility_id} · RUL P50 {w.rul_p50 == null ? "—" : `${Math.round(w.rul_p50)} wk`}</span></div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--panel-2)]"><div className="h-full rounded-full" style={{ width: `${Math.max(4, w.last_health * 100)}%`, background: w.last_health < 0.35 ? "#EF4444" : w.last_health < 0.6 ? "#F59E0B" : "#10B981" }} /></div>
              </div>
            ))}
          </Stop>
          <Stop n={1} className="grid content-start gap-3">
            <Big k="Installed units" v={u.length} hint="synthetic serials" />
            <Big k="End of life ≤ 26 weeks" v={u.filter((x) => (x.rul_p50 ?? 999) < 26).length} hint="Weibull survival + health trend, P50" />
          </Stop>
        </div>
      );
    },
  },
  {
    id: "airspace", title: "Airspace Safety", subtitle: "Civilian drone detection that shows its mistakes", source: "GET /api/visual/evaluation",
    ready: (d) => !!d.vis.data, error: (d) => d.vis.error,
    intro: "Over to the airspace lab, and an honest look at what it can and cannot see.",
    stops: (d) => {
      const v = d.vis.data!.data; const ac = v.by_object.aircraft;
      return [
        `${v.is_ai ? "An AI model" : "No vision AI is installed, so this is a labelled classical baseline"}: precision ${pct(v.precision)}, recall ${pct(v.recall)} on ${v.n} synthetic frames.`,
        ac ? `Its known mistake: it flagged ${ac.flagged_drone_like} of ${ac.n} aircraft frames as drone-like. We show that rather than hide it.` : `False positives: ${v.fp}. Every error is listed, not hidden.`,
      ];
    },
    body: (d) => {
      const v = d.vis.data!.data; const objs = Object.entries(v.by_object);
      return (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <Stop n={0} className="grid content-start gap-3">
            <Big k="Method" v={v.is_ai ? "AI model" : "Classical baseline"} hint={v.is_ai ? "" : "not AI · labelled as such"} />
            <div className="grid grid-cols-2 gap-3"><Big k="Precision" v={pct(v.precision)} /><Big k="Recall" v={pct(v.recall)} /></div>
          </Stop>
          <Stop n={1} className="p-1"><Chart title="flags by object" height={280} spec={{ kind: "bar", x: objs.map(([k]) => k.replace("_", " ")), series: [
            { name: "frames", data: objs.map(([, o]) => o.n) }, { name: "flagged drone-like", data: objs.map(([, o]) => o.flagged_drone_like) }] }} /></Stop>
        </div>
      );
    },
  },
  {
    id: "resilience", title: "Resilience", subtitle: "A hangar loses capacity for three weeks: what happens?", source: "POST /api/resilience/simulate",
    ready: (d) => !!d.res.data, error: (d) => d.res.error,
    intro: "What if a hangar goes down? Let's simulate it.",
    stops: (d) => {
      const r = d.res.data!.data.results;
      const rw = r.disruption.recovery_weeks_after_disruption, mw = r.recovery.recovery_weeks_after_disruption;
      return [
        `The backlog peaks at ${Math.round(r.disruption.peak_backlog_hours)} hours without help, ${Math.round(r.recovery.peak_backlog_hours)} with overtime and deferrals.`,
        rw != null && mw != null ? `With mitigation we recover ${Math.max(0, rw - mw)} week${rw - mw === 1 ? "" : "s"} sooner, across 200 simulated futures.` : `Mitigation changes the cost from ${usd(r.disruption.cost_p50_usd)} to ${usd(r.recovery.cost_p50_usd)} (P50).`,
      ];
    },
    body: (d) => {
      const s = d.res.data!.data; const r = s.results;
      return (
        <div className="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
          <Stop n={0} className="p-1"><Chart title="backlog" height={300} spec={{ kind: "line", x: s.weeks.map((w) => `wk ${w}`), series: [
            { name: "with mitigation", data: r.recovery.backlog_p50 }, { name: "disruption", data: r.disruption.backlog_p50 }, { name: "normal", data: r.baseline.backlog_p50 }], yLabel: "hours" }} /></Stop>
          <Stop n={1} className="grid content-start gap-3">
            <Big k="Peak backlog" v={`${Math.round(r.disruption.peak_backlog_hours)} h`} hint="disruption, P50" />
            <Big k="With mitigation" v={`${Math.round(r.recovery.peak_backlog_hours)} h`} hint="overtime 15% · deferral 10%" />
          </Stop>
        </div>
      );
    },
  },
  {
    id: "agents", title: "Agents & Approvals", subtitle: "Who did what, and who decides", source: "GET /api/harness/control-tower",
    ready: (d) => !!d.ct.data || !!d.ct.error, error: () => null,
    intro: "Last stop: the control tower, where every agent step is recorded.",
    stops: (d) => {
      const c = d.ct.data?.data; const runs = c?.runs ?? [];
      return [
        runs.length ? `${runs.length} recorded run${runs.length === 1 ? "" : "s"}. The latest asked: “${runs[0].query}”` : "No runs recorded yet. Ask a question in chat and it will appear here, step by step.",
        "Models compute the numbers, the local Qwen model explains them, and a person approves every consequential action. Thanks for flying!",
      ];
    },
    body: (d) => {
      const c = d.ct.data?.data; const nodes = c?.selected?.nodes ?? [];
      return (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <Stop n={0} className="space-y-2 p-1">
            {nodes.length ? nodes.slice(0, 7).map((n, i) => (
              <div key={i} className="gj-big flex items-center justify-between rounded-xl px-4 py-2 text-sm"><span>{n.step} · <span className="muted">{n.agent}</span></span><Badge tone={n.status === "completed" ? "teal" : "amber"}>{n.status}</Badge></div>
            )) : <div className="gj-big rounded-xl p-6 text-sm muted">No recorded runs yet.</div>}
          </Stop>
          <Stop n={1} className="grid content-start gap-3">
            <Big k="Recorded runs" v={c?.runs.length ?? 0} hint="from the audit trail, not invented" />
            <Big k="Decisions" v="Human" hint="AI recommends · people approve" />
          </Stop>
        </div>
      );
    },
  },
];

type Line = { scene: number; text: string };

export function GuidedJourney() {
  const data = useJourneyData();
  const [scene, setScene] = useState(0);
  const [stop, setStop] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [speed, setSpeed] = useState(1.5);
  const [reduce, setReduce] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  const [log, setLog] = useState<Line[]>([]);
  const [bubble, setBubble] = useState<{ text: string; left: boolean } | null>(null);
  const [state, setState] = useState("Waiting for Play");

  const stageRef = useRef<HTMLDivElement>(null);
  const guideRef = useRef<HTMLDivElement>(null);
  const trailRef = useRef<SVGPathElement>(null);
  const pos = useRef({ x: 40, y: 120 });
  const logRef = useRef<HTMLOListElement>(null);

  const def = SCENES[scene];
  const ready = def.ready(data);
  // Narration is derived from query data; key it by content so re-renders don't restart a flight.
  const linesNow = ready ? def.stops(data) : [];
  const linesKey = linesNow.join("\u0001");
  const lines = useMemo(() => (linesKey ? linesKey.split("\u0001") : []), [linesKey]);
  const revealed = started && (!playing || stop >= 0);

  const tiltRef = useRef<HTMLSpanElement>(null);
  const place = useCallback((x: number, y: number, tilt = 0) => {
    pos.current = { x, y };
    if (guideRef.current) guideRef.current.style.transform = `translate(${x - 34}px, ${y - 34}px)`;
    if (tiltRef.current) tiltRef.current.style.transform = `rotate(${tilt}deg)`; // tilt the emblem only, never the speech bubble
  }, []);
  // Start parked at the bottom-left of the stage, like a pilot waiting on the apron.
  useEffect(() => { const h = stageRef.current?.clientHeight ?? 600; place(56, Math.max(160, h - 70)); }, [place]);

  /** Fly along a curved path to the element, drawing a dashed contrail. Resolves when it arrives (or is cancelled). */
  const flyTo = useCallback((sel: string, alive: () => boolean) => new Promise<void>((resolve) => {
    const stage = stageRef.current; const el = stage?.querySelector<HTMLElement>(sel);
    if (!stage || !el) return resolve();
    const sr = stage.getBoundingClientRect(); const er = el.getBoundingClientRect();
    if (er.top < 80 || er.bottom > window.innerHeight - 40) el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    const tx = Math.min(er.right - sr.left - 30, er.left - sr.left + er.width * 0.82);
    const ty = er.top - sr.top + Math.min(44, er.height * 0.3);
    const { x: fx, y: fy } = pos.current;
    const dist = Math.hypot(tx - fx, ty - fy);
    const cx = (fx + tx) / 2, cy = Math.min(fy, ty) - Math.min(160, dist * 0.35);
    const trail = trailRef.current;
    if (reduce || dist < 4) { place(tx, ty); trail?.setAttribute("d", ""); return resolve(); }
    trail?.setAttribute("d", `M${fx},${fy} Q${cx},${cy} ${tx},${ty}`);
    if (trail) { const L = trail.getTotalLength(); trail.style.strokeDasharray = `6 7`; trail.style.opacity = "0.8"; trail.dataset.len = String(L); }
    const dur = Math.max(700, Math.min(1800, dist * 2.2)) / speed; const t0 = performance.now();
    const frame = (now: number) => {
      if (!alive()) return resolve();
      const t = Math.min(1, (now - t0) / dur); const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const x = (1 - e) * (1 - e) * fx + 2 * (1 - e) * e * cx + e * e * tx;
      const y = (1 - e) * (1 - e) * fy + 2 * (1 - e) * e * cy + e * e * ty;
      const dx = 2 * (1 - e) * (cx - fx) + 2 * e * (tx - cx);
      place(x, y, Math.max(-24, Math.min(24, dx * 0.04)));
      if (t < 1) requestAnimationFrame(frame);
      else { place(tx, ty); if (trail) trail.style.opacity = "0"; resolve(); }
    };
    requestAnimationFrame(frame);
  }), [place, reduce, speed]);

  // The journey driver: one effect step per (scene, stop). Cleanup cancels flights and timers.
  useEffect(() => {
    if (!playing || !ready) { if (playing && !ready) setState("Loading scene data…"); return; }
    let live = true; const alive = () => live; let timer = 0;
    const wait = (ms: number) => new Promise<void>((r) => { timer = window.setTimeout(r, reduce ? Math.min(ms, 1800) : ms); });
    const say = (text: string) => {
      const stage = stageRef.current; const left = !!stage && pos.current.x > stage.clientWidth * 0.55;
      setBubble({ text, left }); setLog((l) => [...l, { scene, text }]);
    };
    (async () => {
      if (stop === -1) {
        setState(`Flying to ${def.title}`);
        setBubble(null);
        await flyTo("[data-stop=title]", alive); if (!live) return;
        say(def.intro); setState("Hovering · introducing the scene");
        await wait(2200 / speed); if (live) setStop(0);
      } else if (stop < lines.length) {
        setState(`Flying to evidence ${stop + 1} of ${lines.length}`);
        await flyTo(`[data-stop="${stop}"]`, alive); if (!live) return;
        say(lines[stop]); setState(`Hovering · evidence ${stop + 1} of ${lines.length}`);
        await wait((2600 + lines[stop].length * 22) / speed); if (live) setStop(stop + 1);
      } else if (scene < SCENES.length - 1) {
        setScene(scene + 1); setStop(-1);
      } else {
        setPlaying(false); setState("Journey complete"); setBubble({ text: "Journey complete. Jump to any scene, or explore the full pages.", left: false });
      }
    })();
    return () => { live = false; window.clearTimeout(timer); };
  }, [playing, ready, scene, stop, lines, def, flyTo, reduce, speed]);

  useEffect(() => { logRef.current?.lastElementChild?.scrollIntoView({ block: "nearest" }); }, [log]);

  const playPause = () => { if (!started) { setStarted(true); setLog([]); } setPlaying((p) => !p); };
  const jump = (i: number) => { setScene(i); setStop(-1); setBubble(null); setStarted(true); };
  const replay = () => { setLog((l) => l.filter((x) => x.scene !== scene)); setStop(-1); setStarted(true); setPlaying(true); };
  const skip = () => {
    if (!ready) return;
    setStarted(true);
    setLog((l) => [...l.filter((x) => x.scene !== scene), { scene, text: def.intro }, ...lines.map((text) => ({ scene, text }))]);
    setBubble(null); setStop(lines.length);
  };

  const err = def.error(data);
  return (
    <div className="space-y-4" data-testid="guided-journey">
      <header className="flex items-start gap-4">
        <img src="/brand/ff-emblem.svg" alt="" className="h-16 w-16 shrink-0 drop-shadow-[0_6px_12px_rgba(14,34,64,0.3)]" />
        <div>
          <h1 className="text-2xl font-semibold sm:text-3xl">Flying Florina Guided Journey</h1>
          <p className="muted mt-1 max-w-3xl text-sm">The Flying Florina emblem flies from the supply chain to every part of the platform and hovers over the evidence it explains. Charts stay interactive; the narration panel repeats every message as text for screen readers and reduced motion.</p>
        </div>
      </header>

      <section className="panel space-y-3 p-4" aria-label="Journey controls">
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" onClick={playPause} data-testid="gj-play">{playing ? <><Pause className="h-4 w-4" />Pause</> : <><Play className="h-4 w-4" />{started ? "Resume" : "Play Journey"}</>}</button>
          <button className="btn btn-ghost" onClick={skip} disabled={!ready}><FastForward className="h-4 w-4" />Skip Animation</button>
          <button className="btn btn-ghost" onClick={replay}><RotateCcw className="h-4 w-4" />Replay Scene</button>
          <label className="muted ml-1 flex items-center gap-2 text-sm">Jump to
            <select className="input !py-1.5" value={scene} onChange={(e) => jump(+e.target.value)}>
              {SCENES.map((s, i) => <option key={s.id} value={i}>{i + 1}. {s.title}</option>)}
            </select>
          </label>
          <label className="muted flex items-center gap-2 text-sm">Speed
            <select className="input !py-1.5" value={speed} onChange={(e) => setSpeed(+e.target.value)}>
              {[1, 1.5, 2].map((s) => <option key={s} value={s}>{s}×</option>)}
            </select>
          </label>
          <button className="btn btn-ghost" aria-pressed={reduce} onClick={() => setReduce((r) => !r)}><Wind className="h-4 w-4" />{reduce ? "Motion reduced" : "Reduce motion"}</button>
          <span className="ml-auto flex items-center gap-2">
            <Badge tone="gold">SYNTHETIC DATA</Badge>
            <Badge tone={playing ? "teal" : "gray"}>{playing ? "PLAYING" : started ? (state === "Journey complete" ? "COMPLETE" : "PAUSED") : "READY"}</Badge>
          </span>
        </div>
        <div className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-9" role="tablist" aria-label="Scenes">
          {SCENES.map((s, i) => (
            <button key={s.id} role="tab" aria-selected={i === scene} onClick={() => jump(i)}
              className={`gj-chip rounded-xl px-2.5 py-1.5 text-left text-xs ${i === scene ? "gj-chip-on" : i < scene ? "gj-chip-done" : ""}`}>
              <span className="font-semibold">{i + 1}</span> {s.title}
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div ref={stageRef} className="relative">
          <section className="panel p-5 sm:p-6" data-testid="gj-scene">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div data-stop="title" className="pr-24">
                <p className="gj-kicker">SCENE {scene + 1} OF {SCENES.length}</p>
                <h2 className="font-serif mt-1 text-3xl sm:text-4xl">{def.title}</h2>
                <p className="muted mt-1 text-sm">{def.subtitle}</p>
              </div>
              <div className="text-right text-xs">
                <p><span className="font-semibold">Guide state:</span> <span className="muted">{state}</span></p>
                <p className="muted mt-0.5">Data: <code className="font-mono">{def.source}</code></p>
              </div>
            </div>
            <div className={`gj-body mt-5 ${revealed ? "gj-on" : ""}`} aria-busy={!ready}>
              {err ? <ErrorBox error={err} /> : ready ? def.body(data) : <Skeleton className="h-72" />}
            </div>
          </section>

          <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-visible" aria-hidden>
            <path ref={trailRef} className="gj-trail" fill="none" />
          </svg>
          <div ref={guideRef} className={`gj-guide pointer-events-none absolute left-0 top-0 ${playing ? "gj-flying" : ""}`} aria-hidden data-testid="gj-guide">
            <span ref={tiltRef} className="block h-[68px] w-[68px]"><img src="/brand/ff-emblem.svg" alt="" className="gj-hover h-[68px] w-[68px]" /></span>
            {bubble && <div className={`gj-bubble ${bubble.left ? "gj-bubble-left" : ""}`}>{bubble.text}</div>}
          </div>
        </div>

        <aside className="panel flex max-h-[720px] flex-col p-5" aria-label="Narration">
          <h2 className="font-serif text-2xl">Narration</h2>
          <p className="muted text-xs">Everything the guide says, as text.</p>
          <ol ref={logRef} className="mt-3 flex-1 space-y-2 overflow-auto pr-1" aria-live="polite" data-testid="gj-narration">
            {log.length === 0 && <li className="muted text-sm">Press Play Journey.</li>}
            {log.map((l, i) => (
              <li key={i} className="gj-line rounded-xl px-3 py-2 text-sm leading-snug">
                <span className="gj-kicker mr-1.5 !text-[10px]">Scene {l.scene + 1}</span>{l.text}
              </li>
            ))}
          </ol>
          <p className="muted mt-3 text-[11px]">Numbers come from the forecasting, simulation and evaluation APIs on fictional, synthetic data. Not affiliated with IFS.</p>
        </aside>
      </div>
    </div>
  );
}
