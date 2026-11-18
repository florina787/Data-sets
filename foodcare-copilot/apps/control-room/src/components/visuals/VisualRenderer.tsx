import { useEffect, useMemo, useState } from "react";
import { ProvenanceChip } from "../pulse/shared";

// Visual response contract 1.0 (backend/app/visuals.py). Only these kinds render; anything else is ignored.
export type Visual = { kind: string; title?: string; provenance?: any; [k: string]: any };

const TEAL = "#45C5B8", GOLD = "#D7B77A", INK = "#F3F0E9", MUTED = "#A3AEBC", LINE = "#2A3F57", RED = "#E26D6D", AMBER = "#E8B04E";
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const fmt = (v: number, unit?: string) => (unit === "CAD" || unit === "USD" ? `${unit} ${v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : v.toFixed(0)}` : `${Number.isInteger(v) ? v.toLocaleString() : v.toFixed(1)}${unit === "%" ? "%" : unit ? ` ${unit}` : ""}`);
const STATUS_COLOR: Record<string, string> = { good: "#3FBF8C", watch: AMBER, attention: RED, unknown: MUTED, done: "#3FBF8C",
  on_track: TEAL, at_risk: AMBER, delayed: RED, blocked: RED, upcoming: MUTED, overdue: RED };

function Frame({ v, children, data }: { v: Visual; children: React.ReactNode; data?: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <figure className="visual-card mt-3 rounded-2xl border border-surface-line p-4" data-visual={v.kind}>
      <figcaption className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-ink">{v.title}</span>
        <span className="flex items-center gap-2">
          <ProvenanceChip kind={v.provenance ?? null} />
          {data && <button className="text-[11px] text-teal hover:underline" aria-expanded={show} onClick={() => setShow((s) => !s)}>{show ? "Hide data" : "Show data"}</button>}
        </span>
      </figcaption>
      {children}
      {show && data && <div className="mt-3 overflow-x-auto text-xs">{data}</div>}
    </figure>
  );
}

function DataTable({ columns, rows }: { columns: string[]; rows: any[][] }) {
  return (
    <table className="table">
      <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c === null || c === undefined ? "—" : String(c)}</td>)}</tr>)}</tbody>
    </table>
  );
}

/** Glowing metric cards (reference: luminous stacked metric tiles). */
function Kpis({ v }: { v: Visual }) {
  return (
    <Frame v={v}>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {v.items.map((k: any) => (
          <li key={k.label} className="metric-tile relative overflow-hidden rounded-xl border p-3" style={{ borderColor: `${STATUS_COLOR[k.status] ?? MUTED}66` }}>
            <span aria-hidden className="absolute inset-y-0 left-0 w-1 rounded-l-xl" style={{ background: STATUS_COLOR[k.status] ?? MUTED, boxShadow: `0 0 14px ${STATUS_COLOR[k.status] ?? MUTED}` }} />
            <div className="pl-2 text-[11px] uppercase tracking-[0.1em] text-ink-muted">{k.label}</div>
            <div className="pl-2 pt-1 text-lg font-semibold leading-snug text-ink">{k.value}</div>
            {k.delta && <div className="pl-2 text-xs text-teal-soft">{k.delta}</div>}
          </li>
        ))}
      </ul>
    </Frame>
  );
}

/** Gradient bars with a soft glow (reference: premium dark analytics). */
function Bars({ v }: { v: Visual }) {
  const max = Math.max(1, ...v.items.map((i: any) => i.value));
  return (
    <Frame v={v} data={<DataTable columns={["Item", `Value (${v.unit})`, "Note"]} rows={v.items.map((i: any) => [i.label, i.value, i.note ?? ""])} />}>
      <ul className="space-y-2" role="img" aria-label={`${v.title}: ${v.items.map((i: any) => `${i.label} ${fmt(i.value, v.unit)}`).join("; ")}`}>
        {v.items.map((i: any) => {
          const hot = (v.highlight ?? []).includes(i.label);
          return (
            <li key={i.label} className="grid grid-cols-[minmax(90px,38%)_1fr_auto] items-center gap-3 text-xs">
              <span className="truncate text-ink-muted" title={i.label}>{i.label}</span>
              <span className="h-3 overflow-hidden rounded-full bg-midnight/80">
                <span className="block h-full rounded-full" style={{ width: `${Math.max(2, (100 * i.value) / max)}%`, background: hot ? `linear-gradient(90deg, ${AMBER}, ${GOLD})` : `linear-gradient(90deg, #2C9C91, ${TEAL})`, boxShadow: `0 0 12px ${hot ? GOLD : TEAL}88` }} />
              </span>
              <span className="font-mono text-ink" title={i.note}>{fmt(i.value, v.unit)}</span>
            </li>
          );
        })}
      </ul>
    </Frame>
  );
}

/** Area line with gradient fill (reference: glowing wave revenue chart). */
function Line({ v }: { v: Visual }) {
  const pts = v.points as { label: string; value: number }[];
  const W = 640, H = 180, pad = 24;
  const max = Math.max(...pts.map((p) => p.value)), min = Math.min(...pts.map((p) => p.value));
  const x = (i: number) => pad + (i * (W - 2 * pad)) / Math.max(1, pts.length - 1);
  const y = (val: number) => H - pad - ((val - min) / (max - min || 1)) * (H - 2 * pad);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
  return (
    <Frame v={v} data={<DataTable columns={["Period", `Value (${v.unit})`]} rows={pts.map((p) => [p.label, p.value])} />}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${v.title}: from ${fmt(pts[0]?.value ?? 0, v.unit)} to ${fmt(pts[pts.length - 1]?.value ?? 0, v.unit)}`}>
        <defs>
          <linearGradient id="line-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={TEAL} stopOpacity="0.45" /><stop offset="100%" stopColor={TEAL} stopOpacity="0" /></linearGradient>
          <filter id="line-glow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <path d={`${d} L${x(pts.length - 1)},${H - pad} L${x(0)},${H - pad} Z`} fill="url(#line-fill)" />
        <path d={d} fill="none" stroke={TEAL} strokeWidth="2.5" filter="url(#line-glow)" />
        {pts.map((p, i) => (i % Math.ceil(pts.length / 8) === 0 || i === pts.length - 1) && <text key={p.label} x={x(i)} y={H - 6} fill={MUTED} fontSize="10" textAnchor="middle">{p.label}</text>)}
        <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1]?.value ?? 0)} r="4" fill={GOLD} />
      </svg>
    </Frame>
  );
}

function Waterfall({ v }: { v: Visual }) {
  const max = Math.max(1, ...v.steps.map((s: any) => s.value));
  return (
    <Frame v={v} data={<DataTable columns={["Component", `Value (${v.unit})`]} rows={[...v.steps.map((s: any) => [s.label, s.value]), ...v.missing.map((m: string) => [m, "not measurable (no data)"])]} />}>
      <div className="flex items-end gap-3" style={{ height: 160 }} role="img" aria-label={`${v.title}: ${v.steps.map((s: any) => `${s.label} ${fmt(s.value, v.unit)}`).join("; ")}`}>
        {v.steps.map((s: any, i: number) => (
          <div key={s.label} className="flex h-full flex-1 flex-col justify-end text-center">
            <span className="mb-1 font-mono text-[11px] text-ink">{fmt(s.value, v.unit)}</span>
            <span className="rounded-t-lg" style={{ height: `${Math.max(3, (100 * s.value) / max)}%`, background: i === v.steps.length - 1 ? `linear-gradient(180deg, ${GOLD}, #B8955A)` : `linear-gradient(180deg, ${TEAL}, #1F5F5A)`, boxShadow: `0 0 18px ${i === v.steps.length - 1 ? GOLD : TEAL}55` }} />
            <span className="mt-1 text-[10px] leading-tight text-ink-muted">{s.label}</span>
          </div>
        ))}
        {v.missing.map((m: string) => (
          <div key={m} className="flex h-full flex-1 flex-col justify-end text-center">
            <span className="rounded-t-lg border border-dashed border-ink-faint" style={{ height: "30%" }} title="No data — shown as a gap, not zero" />
            <span className="mt-1 text-[10px] leading-tight text-ink-faint">{m} · no data</span>
          </div>
        ))}
      </div>
    </Frame>
  );
}

function Band({ v }: { v: Visual }) {
  const max = Math.max(1, ...v.bands.map((b: any) => b.p90));
  return (
    <Frame v={v} data={<DataTable columns={["Horizon", "P10", "Median", "P90"]} rows={v.bands.map((b: any) => [b.label, b.p10, b.p50, b.p90])} />}>
      <ul className="space-y-2">{v.bands.map((b: any) => (
        <li key={b.label} className="grid grid-cols-[70px_1fr_150px] items-center gap-3 text-xs">
          <span className="text-ink">{b.label}</span>
          <span className="relative h-4 rounded bg-midnight/80">
            <span className="absolute inset-y-0.5 rounded" style={{ left: `${(100 * b.p10) / max}%`, width: `${Math.max(1, (100 * (b.p90 - b.p10)) / max)}%`, background: `${TEAL}44`, boxShadow: `inset 0 0 0 1px ${TEAL}` }} />
            <span className="absolute inset-y-0 w-0.5" style={{ left: `${(100 * b.p50) / max}%`, background: GOLD }} />
          </span>
          <span className="font-mono text-ink-muted">{fmt(b.p50, v.unit)} <span className="text-ink-faint">({fmt(b.p10, v.unit)}–{fmt(b.p90, v.unit)})</span></span>
        </li>
      ))}</ul>
      <p className="mt-2 text-[11px] text-ink-faint">{v.method}</p>
    </Frame>
  );
}

const GROUP_COLOR: Record<string, string> = {
  input: GOLD, agent: TEAL, policy: GOLD, tools: TEAL, source: "#8FB3FF", evidence: TEAL, output: GOLD, threat: RED,
  vulnerability: AMBER, protected: "#B48CF0", service: TEAL, supplier: GOLD, factory: TEAL, distribution_centre: "#C7D2FE",
  market: GOLD, farm: "#A3E635", dependency: "#8FB3FF",
};

/** Luminous network graph (reference: dark policy/threat network with glowing nodes). Layered radial layout. */
function Graph({ v, step }: { v: Visual; step?: string[] }) {
  // Columns: by group when there are few groups; otherwise by dependency depth so labels never pile up.
  const columns = useMemo(() => {
    const g = new Map<string, any[]>();
    const byGroup = new Set(v.nodes.map((n: any) => n.group)).size <= 6;
    const level = new Map<string, number>();
    if (!byGroup) {
      const incoming = new Map<string, string[]>();
      for (const e of v.edges) incoming.set(e.target, [...(incoming.get(e.target) ?? []), e.source]);
      const depth = (id: string, seen: Set<string>): number => {
        if (level.has(id)) return level.get(id)!;
        if (seen.has(id)) return 0;
        seen.add(id);
        const d = Math.max(-1, ...(incoming.get(id) ?? []).map((s) => depth(s, seen))) + 1;
        level.set(id, d);
        return d;
      };
      v.nodes.forEach((n: any) => depth(n.id, new Set()));
    }
    for (const n of v.nodes) { const k = byGroup ? n.group : `L${level.get(n.id)}`; g.set(k, [...(g.get(k) ?? []), n]); }
    const cols = [...g.entries()].sort(([a], [b]) => (byGroup ? 0 : a.localeCompare(b, undefined, { numeric: true })));
    if (byGroup) return cols;
    return cols.flatMap(([k, ns]) => Array.from({ length: Math.ceil(ns.length / 10) }, (_, i) => [`${k}.${i}`, ns.slice(i * 10, i * 10 + 10)] as [string, any[]]));
  }, [v]);
  const W = 760, H = Math.max(300, 70 + Math.max(...columns.map(([, ns]) => ns.length)) * 46);
  const colW = (W - 180) / Math.max(1, columns.length - 1);
  const maxChars = Math.max(10, Math.min(26, Math.floor(colW / 5.6)));
  const pos = new Map<string, [number, number]>();
  columns.forEach(([, ns], ci) => ns.forEach((n, ri) => pos.set(n.id, [90 + ci * colW, 40 + ((ri + 0.5) * (H - 70)) / ns.length])));
  const [sel, setSel] = useState<any>(null);
  const lit = new Set(step ?? []);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${v.title}: ${v.nodes.length} nodes, ${v.edges.length} links. Select a node for details, or use Show data.`}>
        <defs>
          <radialGradient id="node-glow"><stop offset="0%" stopColor="#fff" stopOpacity="0.9" /><stop offset="100%" stopColor="#fff" stopOpacity="0" /></radialGradient>
          <filter id="graph-glow"><feGaussianBlur stdDeviation="2.4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        {v.edges.map((e: any, i: number) => {
          const a = pos.get(e.source), b = pos.get(e.target);
          if (!a || !b) return null;
          const on = lit.has(e.source) && lit.has(e.target);
          const mx = (a[0] + b[0]) / 2;
          return <path key={i} d={`M${a[0]},${a[1]} C${mx},${a[1]} ${mx},${b[1]} ${b[0]},${b[1]}`} fill="none" stroke={on ? GOLD : e.label === "inferred" ? `${MUTED}88` : `${TEAL}77`} strokeWidth={on ? 2.2 : 1.1} strokeDasharray={e.label === "inferred" ? "4 4" : undefined} filter="url(#graph-glow)" />;
        })}
        {v.nodes.map((n: any) => {
          const p = pos.get(n.id)!;
          const c = GROUP_COLOR[n.group] ?? TEAL;
          const on = lit.size === 0 || lit.has(n.id);
          return (
            <g key={n.id} transform={`translate(${p[0]},${p[1]})`} opacity={on ? 1 : 0.35} className="cursor-pointer" tabIndex={0} role="button"
              aria-label={`${n.label}${n.state ? `, ${n.state}` : ""}`} onClick={() => setSel(n)} onKeyDown={(e) => e.key === "Enter" && setSel(n)}>
              <circle r={lit.has(n.id) ? 18 : 13} fill={c} opacity="0.18" />
              <circle r={7} fill={c} stroke="#fff" strokeOpacity="0.5" filter="url(#graph-glow)" />
              <text y={22} fill={INK} fontSize="10" textAnchor="middle">{n.label.length > maxChars ? `${n.label.slice(0, maxChars - 1)}…` : n.label}</text>
              {n.state && <text y={33} fill={MUTED} fontSize="9" textAnchor="middle">{String(n.state).replace(/_/g, " ")}</text>}
            </g>
          );
        })}
      </svg>
      {sel && <p className="mt-2 rounded-lg border border-surface-line bg-midnight/60 px-3 py-2 text-xs text-ink-muted"><b className="text-ink">{sel.label}</b> · {sel.group.replace(/_/g, " ")}{sel.state ? ` · ${String(sel.state).replace(/_/g, " ")}` : ""}{sel.detail ? ` — ${sel.detail}` : ""}</p>}
    </div>
  );
}

function Flow({ v }: { v: Visual }) {
  return (
    <Frame v={v} data={<DataTable columns={["From", "To", "Link"]} rows={v.edges.map((e: any) => [v.nodes.find((n: any) => n.id === e.source)?.label ?? e.source, v.nodes.find((n: any) => n.id === e.target)?.label ?? e.target, e.label ?? ""])} />}>
      <Graph v={v} />
      {v.caption && <p className="mt-2 text-[11px] text-ink-faint">{v.caption}</p>}
    </Frame>
  );
}

/** Motion Story: play/pause/replay/speed; reduced motion shows every step statically. */
export function Motion({ v }: { v: Visual }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(!reduced());
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    if (!playing) return;
    const t = window.setTimeout(() => (i + 1 < v.steps.length ? setI(i + 1) : setPlaying(false)), 2200 / speed);
    return () => window.clearTimeout(t);
  }, [i, playing, speed, v.steps.length]);
  const lit = v.steps.slice(0, i + 1).flatMap((s: any) => s.nodes);
  const step = v.steps[i];
  return (
    <Frame v={v} data={<ol className="list-decimal space-y-1 pl-5">{v.steps.map((s: any) => <li key={s.title}><b>{s.title}:</b> {s.text}</li>)}</ol>}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs" role="group" aria-label="Playback">
        <button className="btn-ghost text-xs" onClick={() => { if (i + 1 >= v.steps.length) setI(0); setPlaying((p) => !p); }}>{playing ? "Pause" : "Play"}</button>
        <button className="btn-ghost text-xs" onClick={() => { setI(0); setPlaying(true); }}>Replay</button>
        <label className="flex items-center gap-1 text-ink-muted">Speed
          <select className="rounded border px-1 py-0.5" value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>{[0.5, 1, 2].map((s) => <option key={s} value={s}>{s}×</option>)}</select>
        </label>
        <span className="ml-auto text-ink-faint">Step {i + 1} of {v.steps.length}</span>
      </div>
      <p className="mb-2 rounded-lg border border-champagne/30 bg-champagne/5 px-3 py-2 text-sm text-ink" aria-live="polite"><b className="text-champagne">{step.title}.</b> {step.text}</p>
      <Graph v={v} step={lit} />
      <p className="mt-2 text-[11px] text-ink-faint">{v.disclaimer}</p>
    </Frame>
  );
}

function Table({ v }: { v: Visual }) {
  return <Frame v={v}><div className="overflow-x-auto"><DataTable columns={v.columns} rows={v.rows} /></div></Frame>;
}

function Timeline({ v }: { v: Visual }) {
  return (
    <Frame v={v}>
      <ol className="relative space-y-3 border-l border-surface-line pl-4">
        {v.events.map((e: any, i: number) => (
          <li key={i} className="text-xs">
            <span aria-hidden className="absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full" style={{ background: e.provenance === "operational_record" ? TEAL : GOLD, boxShadow: `0 0 8px ${TEAL}` }} />
            <span className="font-mono text-ink-faint">{e.date}</span> <span className="text-ink">{e.label}</span> <ProvenanceChip kind={e.provenance} />
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function Plan({ v }: { v: Visual }) {
  return (
    <Frame v={v}>
      <ol className="space-y-2">
        {v.steps.map((s: any, i: number) => (
          <li key={i} className="grid grid-cols-[24px_1fr] gap-2 text-sm">
            <span className="flex h-6 w-6 items-center justify-center rounded-full border border-champagne/60 text-xs text-champagne">{i + 1}</span>
            <span><span className="text-ink">{s.step}</span><br /><span className="text-xs text-ink-muted">Owner: {s.owner} · Needs: {s.approval} · Evidence: {s.evidence}</span></span>
          </li>
        ))}
      </ol>
      {v.assumptions?.length > 0 && <p className="mt-2 text-[11px] text-ink-faint">{v.assumptions.join(" ")}</p>}
    </Frame>
  );
}

/** Threat radar (reference: luminous network intelligence). */
function Radar({ v }: { v: Visual }) {
  const n = v.axes.length, R = 110, C = 140;
  const pt = (i: number, r: number) => [C + r * Math.sin((2 * Math.PI * i) / n), C - r * Math.cos((2 * Math.PI * i) / n)];
  const poly = v.axes.map((a: any, i: number) => pt(i, (R * a.value) / 100).join(",")).join(" ");
  return (
    <Frame v={v} data={<DataTable columns={["Axis", "Score (0–100)", "Detail"]} rows={v.axes.map((a: any) => [a.label, a.value, a.detail ?? ""])} />}>
      <svg viewBox="0 0 280 280" className="mx-auto w-full max-w-sm" role="img" aria-label={`${v.title}: ${v.axes.map((a: any) => `${a.label} ${a.value}`).join(", ")}`}>
        <defs><radialGradient id="radar-bg"><stop offset="0%" stopColor={TEAL} stopOpacity="0.16" /><stop offset="100%" stopColor={TEAL} stopOpacity="0" /></radialGradient></defs>
        <circle cx={C} cy={C} r={R} fill="url(#radar-bg)" />
        {[0.25, 0.5, 0.75, 1].map((f) => <circle key={f} cx={C} cy={C} r={R * f} fill="none" stroke={LINE} />)}
        {v.axes.map((a: any, i: number) => {
          const [x, y] = pt(i, R);
          const [lx, ly] = pt(i, R + 18);
          return <g key={a.label}><line x1={C} y1={C} x2={x} y2={y} stroke={LINE} /><text x={lx} y={ly} fill={MUTED} fontSize="10" textAnchor="middle">{a.label}</text></g>;
        })}
        <polygon points={poly} fill={`${RED}33`} stroke={RED} strokeWidth="2" style={{ filter: `drop-shadow(0 0 6px ${RED})` }} />
        {!reduced() && <circle cx={C} cy={C} r={R} fill="none" stroke={TEAL} strokeOpacity="0.4" className="radar-sweep" />}
      </svg>
      {v.caption && <p className="text-center text-[11px] text-ink-faint">{v.caption}</p>}
    </Frame>
  );
}

const HEAT = ["#14243A", "#1F5F5A", "#B38A3E", "#C0643F", "#E26D6D"];
function Heatmap({ v }: { v: Visual }) {
  return (
    <Frame v={v}>
      <div className="overflow-x-auto">
        <table className="text-xs" aria-label={v.title}>
          <thead><tr><th /><th className="sr-only">Row</th>{v.columns.map((c: string) => <th key={c} className="px-2 pb-1 text-left font-normal text-ink-muted">{c}</th>)}</tr></thead>
          <tbody>{v.rows.map((r: string, i: number) => (
            <tr key={r}><th className="pr-3 text-left font-mono font-normal text-ink">{r}</th><td className="sr-only" />{v.values[i].map((val: number, j: number) => (
              <td key={j} className="p-0.5"><span className="block h-7 min-w-[64px] rounded-md text-center leading-7 text-[10px] text-ink" style={{ background: HEAT[val], boxShadow: val >= 3 ? `0 0 10px ${HEAT[val]}` : undefined }}>{["none", "low", "medium", "high", "critical"][val]}</span></td>
            ))}</tr>
          ))}</tbody>
        </table>
      </div>
    </Frame>
  );
}

function Gantt({ v }: { v: Visual }) {
  const ds = v.rows.flatMap((r: any) => [r.start, r.end, ...r.milestones.map((m: any) => m.date)]).concat(v.today).map((d: string) => new Date(d).getTime());
  const lo = Math.min(...ds), hi = Math.max(...ds);
  const x = (d: string) => (100 * (new Date(d).getTime() - lo)) / (hi - lo || 1);
  return (
    <Frame v={v} data={<DataTable columns={["Initiative", "Department", "Start", "End", "Status"]} rows={v.rows.map((r: any) => [r.label, r.group, r.start, r.end, r.status])} />}>
      <div className="relative space-y-2">
        <span aria-hidden className="absolute inset-y-0 w-px bg-champagne/70" style={{ left: `calc(38% + ${x(v.today) * 0.62}%)` }} title={`Today ${v.today}`} />
        {v.rows.map((r: any) => (
          <div key={r.label} className="grid grid-cols-[38%_62%] items-center text-xs">
            <span className="truncate pr-2 text-ink" title={`${r.label} (${r.group})`}>{r.label} <span className="text-ink-faint">· {r.group}</span></span>
            <span className="relative h-5">
              <span className="absolute inset-y-1 rounded-full" style={{ left: `${x(r.start)}%`, width: `${Math.max(1.5, x(r.end) - x(r.start))}%`, background: `${STATUS_COLOR[r.status]}55`, boxShadow: `inset 0 0 0 1px ${STATUS_COLOR[r.status]}` }} />
              {r.milestones.map((m: any) => <span key={m.name} title={`${m.name} · ${m.date} · ${m.state}`} className="absolute top-0.5 h-4 w-1.5 rounded-sm" style={{ left: `${x(m.date)}%`, background: STATUS_COLOR[m.state] }} />)}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-ink-faint">Gold line = today ({v.today}). Bars coloured by status; markers are milestones (green done, red overdue, grey upcoming).</p>
    </Frame>
  );
}

const REGISTRY: Record<string, (p: { v: Visual }) => JSX.Element> = {
  kpis: Kpis, bar: Bars, line: Line, waterfall: Waterfall, forecast_band: Band, table: Table, flow: Flow,
  motion_story: Motion, timeline: Timeline, plan: Plan, radar: Radar, heatmap: Heatmap, gantt: Gantt,
};

export function VisualList({ visuals }: { visuals: Visual[] }) {
  return <>{visuals.map((v, i) => { const C = REGISTRY[v.kind]; return C ? <C key={i} v={v} /> : null; })}</>;
}
