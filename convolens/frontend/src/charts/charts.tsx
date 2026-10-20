import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import type { Breakdown, CrossTab } from "../lib/api";
import { fmtInt, fmtPct } from "../lib/format";
import { RESOLUTION_COLORS, SENTIMENT_COLORS, TOPIC_COLORS, colorFor } from "../lib/palette";
import { Swatch } from "../components/ui";

const axis = { fontSize: 11, fill: "#5F6B7A" };
const tooltipStyle = { fontSize: 12, borderRadius: 8, border: "1px solid #DCE3EB" };

/** 1. Horizontal bar: most common primary topics. Click a bar to filter. */
export function TopicBar({ data, onSelect, selected }: { data: Breakdown; onSelect?: (key: string) => void; selected?: string[] }) {
  const rows = data.items.map((i) => ({ ...i, pct: i.share }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 34)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 56, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="#EEF1F5" />
        <XAxis type="number" domain={[0, "auto"]} allowDecimals={false} tick={axis} label={{ value: "conversations", position: "insideBottomRight", offset: -2, fontSize: 11, fill: "#5F6B7A" }} />
        <YAxis type="category" dataKey="label" width={150} tick={axis} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: any, _n, p: any) => [`${fmtInt(v)} of ${fmtInt(data.denominator)} (${fmtPct(p.payload.share)})`, "Conversations"]} />
        <Bar dataKey="count" radius={[0, 3, 3, 0]} cursor={onSelect ? "pointer" : undefined} onClick={(d: any) => onSelect?.(d.key)} isAnimationActive={false}>
          {rows.map((r) => (
            <Cell key={r.key} fill={TOPIC_COLORS[r.key] ?? "#5F6B7A"} fillOpacity={selected?.length && !selected.includes(r.key) ? 0.35 : 1} />
          ))}
          <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: "#172B4D" }} formatter={(v: any) => fmtInt(v)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** 2. Stacked bar: resolution status by topic. */
export function ResolutionStacked({ data, onSelect }: { data: CrossTab; onSelect?: (topic: string, resolution: string) => void }) {
  const cols = data.columns;
  const rows = data.rows.map((r) => ({ key: r.key, label: r.label, total: r.total, ...Object.fromEntries(r.cells.map((c) => [c.key, c.count])) }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 34 + 40)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="#EEF1F5" />
        <XAxis type="number" domain={[0, "auto"]} allowDecimals={false} tick={axis} />
        <YAxis type="category" dataKey="label" width={150} tick={axis} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: any, name: any, p: any) => [`${fmtInt(v)} of ${fmtInt(p.payload.total)}`, cols.find((c) => c.key === name)?.label ?? name]} />
        <Legend formatter={(v) => <span style={{ fontSize: 11, color: "#172B4D" }}>{cols.find((c) => c.key === v)?.label ?? v}</span>} />
        {cols.map((c) => (
          <Bar key={c.key} dataKey={c.key} stackId="a" fill={RESOLUTION_COLORS[c.key]} isAnimationActive={false} cursor={onSelect ? "pointer" : undefined}
            onClick={(d: any) => onSelect?.(d.key, c.key)} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** 3. Heatmap: topic vs inferred ending sentiment. Shade = share of the row; every cell is labelled with its count. */
export function TopicSentimentHeatmap({ data, onSelect }: { data: CrossTab; onSelect?: (topic: string, sentiment: string) => void }) {
  const cols = data.columns;
  return (
    <div className="overflow-x-auto">
      <div role="grid" aria-label="Topic by inferred ending sentiment" className="grid min-w-[520px] gap-px text-xs" style={{ gridTemplateColumns: `160px repeat(${cols.length}, 1fr) 70px` }}>
        <div />
        {cols.map((c) => <div key={c.key} role="columnheader" className="flex items-center gap-1 px-2 py-1 font-medium text-muted"><Swatch color={SENTIMENT_COLORS[c.key]} pattern={c.key === "unknown"} />{c.label}</div>)}
        <div role="columnheader" className="px-2 py-1 text-right font-medium text-muted">Total</div>
        {data.rows.map((r) => (
          <div key={r.key} role="row" className="contents">
            <div role="rowheader" className="truncate px-2 py-2 text-ink" title={r.label}>{r.label}</div>
            {r.cells.map((c) => {
              const s = c.share_of_row ?? 0;
              const base = c.key === "unknown" ? "174,184,196" : c.key === "negative" ? "184,61,69" : c.key === "positive" ? "36,115,75" : "95,107,122";
              return (
                <button key={c.key} type="button" role="gridcell" onClick={() => onSelect?.(r.key, c.key)}
                  className="tnum rounded-sm px-2 py-2 text-center hover:outline hover:outline-1 hover:outline-ink"
                  style={{ background: `rgba(${base}, ${0.08 + s * 0.8})`, color: s > 0.5 ? "#fff" : "#172B4D" }}
                  title={`${r.label} · ${c.label}: ${c.count} of ${r.total} (${fmtPct(c.share_of_row)})`}>
                  {c.count} <span className="opacity-75">({fmtPct(c.share_of_row)})</span>
                </button>
              );
            })}
            <div className="tnum px-2 py-2 text-right text-muted">{r.total}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted">Cell shade = share of the topic row. Sentiment is inferred from customer text; it is not a satisfaction score.</p>
    </div>
  );
}

/** 4. Time series: sampled conversation starts per period. Straight segments, zero-based axis. */
export function VolumeSeries({ points }: { points: { bucket: string; total: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={points} margin={{ left: 0, right: 16, top: 8, bottom: 4 }}>
        <CartesianGrid stroke="#EEF1F5" />
        <XAxis dataKey="bucket" tick={axis} />
        <YAxis domain={[0, "auto"]} allowDecimals={false} tick={axis} label={{ value: "conversations", angle: -90, position: "insideLeft", fontSize: 11, fill: "#5F6B7A" }} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [fmtInt(v), "Sampled conversations started"]} />
        <Line type="linear" dataKey="total" stroke="#087F8C" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** 5. Scatter: opportunity frequency vs reviewer-estimated effort (only reviewer-estimated candidates are plotted). */
export function OpportunityScatter({ points }: { points: { title: string; effort: number; count: number; topic: string; score: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ScatterChart margin={{ left: 0, right: 24, top: 12, bottom: 16 }}>
        <CartesianGrid stroke="#EEF1F5" />
        <XAxis type="number" dataKey="effort" domain={[0.5, 5.5]} ticks={[1, 2, 3, 4, 5]} tick={axis} label={{ value: "Reviewer-estimated effort (1 small – 5 very large)", position: "insideBottom", offset: -8, fontSize: 11, fill: "#5F6B7A" }} />
        <YAxis type="number" dataKey="count" domain={[0, "auto"]} allowDecimals={false} tick={axis} label={{ value: "conversations", angle: -90, position: "insideLeft", fontSize: 11, fill: "#5F6B7A" }} />
        <ZAxis range={[90, 90]} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }}
          content={({ payload }) => {
            const p: any = payload?.[0]?.payload;
            return p ? <div className="rounded-md border border-line bg-white px-2 py-1 text-xs"><div className="font-medium">{p.title}</div><div>{p.count} conversations · effort {p.effort} · score {p.score}</div></div> : null;
          }} />
        <Scatter data={points} isAnimationActive={false}>
          {points.map((p, i) => <Cell key={i} fill={TOPIC_COLORS[p.topic] ?? "#5F6B7A"} />)}
          <LabelList dataKey="title" position="top" style={{ fontSize: 10, fill: "#172B4D" }} />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

const SENT_Y: Record<string, number> = { negative: -1, neutral: 0, positive: 1 };

/** 6. Sentiment journey: inferred sentiment per customer turn with the supporting message in the tooltip. */
export function SentimentJourney({ turns, onSelect }: { turns: { message_id: string; position: number; sentiment: string; text: string; evidence: string | null }[]; onSelect?: (id: string) => void }) {
  const data = turns.map((t) => ({ ...t, y: SENT_Y[t.sentiment] ?? null }));
  const unknown = turns.filter((t) => !(t.sentiment in SENT_Y));
  return (
    <div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ left: 0, right: 16, top: 8, bottom: 4 }} onClick={(e: any) => e?.activePayload?.[0] && onSelect?.(e.activePayload[0].payload.message_id)}>
          <CartesianGrid stroke="#EEF1F5" />
          <XAxis dataKey="position" tick={axis} label={{ value: "customer turn", position: "insideBottomRight", offset: -2, fontSize: 11, fill: "#5F6B7A" }} allowDecimals={false} />
          <YAxis domain={[-1, 1]} ticks={[-1, 0, 1]} tickFormatter={(v) => ({ "-1": "Negative", "0": "Neutral", "1": "Positive" } as any)[String(v)]} tick={axis} width={64} />
          <Tooltip contentStyle={tooltipStyle} content={({ payload }) => {
            const p: any = payload?.[0]?.payload;
            return p ? <div className="max-w-xs rounded-md border border-line bg-white px-2 py-1 text-xs"><div className="font-medium">Turn {p.position}: {p.sentiment}</div><div className="text-muted">“{p.text.slice(0, 160)}”</div></div> : null;
          }} />
          <Line type="linear" dataKey="y" stroke="#087F8C" strokeWidth={2} connectNulls={false} isAnimationActive={false}
            dot={(props: any) => <circle key={props.index} cx={props.cx} cy={props.cy} r={4} fill={colorFor(props.payload.sentiment)} stroke="#fff" />} />
        </LineChart>
      </ResponsiveContainer>
      {unknown.length > 0 && <p className="text-[11px] text-muted">Unknown sentiment (not plotted): turn{unknown.length > 1 ? "s" : ""} {unknown.map((u) => u.position).join(", ")}.</p>}
    </div>
  );
}

/** 7. Cohort comparison: resolved vs unresolved characteristics with explicit denominators. */
export function CohortComparison({ segments }: { segments: any[] }) {
  const metrics = [
    { key: "negative_start", label: "Negative at start" },
    { key: "escalation_requested", label: "Requested escalation" },
  ];
  const data = metrics.map((m) => ({
    label: m.label,
    ...Object.fromEntries(segments.map((s) => [s.label, s[m.key]?.denominator ? s[m.key].numerator / s[m.key].denominator : null])),
  }));
  const colors = ["#24734B", "#B83D45"];
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ left: 0, right: 16, top: 8, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#EEF1F5" />
        <XAxis dataKey="label" tick={axis} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => fmtPct(v)} tick={axis} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: any, name: any) => [fmtPct(v), name]} />
        <Legend formatter={(v) => <span style={{ fontSize: 11, color: "#172B4D" }}>{v}</span>} />
        {segments.map((s, i) => (
          <Bar key={s.label} dataKey={s.label} fill={colors[i % 2]} isAnimationActive={false}>
            <LabelList dataKey={s.label} position="top" formatter={(v: any) => fmtPct(v)} style={{ fontSize: 10, fill: "#172B4D" }} />
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
