/* Renders a validated server ChartSpec. No chart data is computed here beyond layout. */
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, LabelList, Legend, Line, LineChart, Pie, PieChart, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { formatValue, humanize, pct, score } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChartSpec } from "@/types/api";

export const COLORS: Record<string, string> = {
  indigo: "#6366F1", cyan: "#22D3EE", violet: "#A78BFA", negative: "#F87171", positive: "#34D399", neutral: "#94A3B8",
  mixed: "#FBBF24", warning: "#F59E0B", muted: "#475569",
};
const tooltipStyle = { background: "#17233C", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12, fontSize: 12, color: "#F8FAFC" };
const grid = "rgba(148,163,184,0.08)";

function fmt(spec: ChartSpec) {
  return (v: any) => (typeof v !== "number" ? String(v) : spec.value_format === "percent" ? pct(v) : spec.value_format === "score" ? score(v)
    : spec.value_format === "number" ? v.toFixed(2) : v.toLocaleString());
}

function useDrill(spec: ChartSpec) {
  const { openConversation, openSubset } = useEvidence();
  if (!spec.drilldown) return undefined;
  const d = spec.drilldown;
  const window = spec.filters?.window?.start ? { type: "range", start: spec.filters.window.start, end: spec.filters.window.end } : null;
  return (row: Record<string, any>) => {
    const v = row?.[d.field];
    if (v === undefined || v === null) return;
    if (d.kind === "conversation") openConversation(String(v));
    else if (d.kind === "message") openConversation(String(v).split("-T")[0], [String(v)]);
    else if (d.kind === "topic") openSubset({ title: `${row.name ?? v} · conversations`, topics: [String(v)], window });
    else if (d.kind === "product") openSubset({ title: `${v} · conversations`, products: [String(v)], window });
    else if (d.kind === "month") openSubset({ title: `${v} · conversations`, window: { type: "month", month: String(v) } });
  };
}

function Kpis({ spec }: { spec: ChartSpec }) {
  return (
    <div className="grid gap-2.5" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${spec.data.length > 4 ? 150 : 190}px, 1fr))` }}>
      {spec.data.map((m) => (
        <div key={m.id} className="rounded-xl border border-line bg-gradient-to-b from-white/[0.04] to-transparent p-3.5">
          <p className="label line-clamp-2 min-h-[2.4em]" title={m.label}>{m.label}</p>
          <p className={cn("num mt-1 font-semibold tracking-tight text-ink", typeof m.value === "string" ? "text-base leading-snug" : "text-xl")} title={String(m.value)}>{formatValue(m.value, m.unit)}</p>
          {m.denominator ? <p className="num mt-0.5 text-[11px] text-faint">{Number(m.numerator).toLocaleString()} / {Number(m.denominator).toLocaleString()}</p> : null}
        </div>
      ))}
    </div>
  );
}

function Heatmap({ spec, onDrill }: { spec: ChartSpec; onDrill?: (r: any) => void }) {
  const cols = spec.data.length ? Object.keys(spec.data[0].cells) : [];
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1 text-xs" aria-label={spec.title}>
        <thead><tr><th className="text-left font-medium text-faint">Conversation</th>{cols.map((c) => <th key={c} className="px-1 text-center font-medium text-faint">{c}</th>)}</tr></thead>
        <tbody>
          {spec.data.map((r) => (
            <tr key={r.row}>
              <td className="whitespace-nowrap pr-2"><button className="focus-ring rounded font-mono text-cyan hover:underline" onClick={() => onDrill?.(r)}>{r.row}</button></td>
              {cols.map((c) => {
                const v = r.cells[c] as number | null;
                return (
                  <td key={c} className="h-8 min-w-[72px] rounded-md text-center num" title={`${c}: ${v === null ? "n/a" : v.toFixed(2)}`}
                    style={{ background: v === null ? "rgba(148,163,184,0.05)" : `rgba(248,113,113,${0.08 + 0.72 * v})`, color: v !== null && v > 0.55 ? "#fff" : "#CBD5E1" }}>
                    {v === null ? "n/a" : v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeline({ spec }: { spec: ChartSpec }) {
  const { openConversation } = useEvidence();
  const tps = new Set(spec.evidence_ids);
  return (
    <ol className="relative ml-2 space-y-2 border-l border-line pl-4">
      {spec.data.map((m) => (
        <li key={m.message_id} className="relative">
          <span className={cn("absolute -left-[21px] top-2 h-2.5 w-2.5 rounded-full ring-4 ring-surface",
            m.speaker_role === "agent" ? "bg-cyan" : m.sentiment === "negative" ? "bg-neg" : m.sentiment === "positive" ? "bg-pos" : "bg-neu")} />
          <button onClick={() => openConversation(m.message_id.split("-T")[0], [m.message_id])}
            className={cn("focus-ring w-full rounded-xl border px-3 py-2 text-left text-sm hover:bg-white/[0.03]", tps.has(m.message_id) ? "border-violet/50 bg-violet/[0.06]" : "border-line")}>
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-faint">
              <span className="font-mono">T{String(m.turn_index).padStart(2, "0")}</span><span>{m.speaker_role}</span><span>{humanize(m.act)}</span>
              {m.speaker_role === "customer" && <span className="num normal-case">{score(m.sentiment_score)}</span>}
              {tps.has(m.message_id) && <span className="rounded bg-violet/20 px-1.5 text-violet">turning point</span>}
            </div>
            <p className="mt-0.5 text-ink">{m.text}</p>
          </button>
        </li>
      ))}
    </ol>
  );
}

export function DataTable({ rows, onRow, max = 50 }: { rows: Record<string, any>[]; onRow?: (r: any) => void; max?: number }) {
  if (!rows.length) return <p className="text-xs text-muted">No rows.</p>;
  const cols = Object.keys(rows[0]).filter((c) => !["cells", "color", "excerpts", "message_ids", "evidence"].includes(c)).slice(0, 10);
  return (
    <div className="max-h-80 overflow-auto rounded-xl border border-line">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-elevated"><tr>{cols.map((c) => <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium text-muted">{humanize(c)}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">
          {rows.slice(0, max).map((r, i) => (
            <tr key={i} onClick={() => onRow?.(r)} className={cn(onRow && "cursor-pointer hover:bg-white/[0.03]")}>
              {cols.map((c) => {
                const v = r[c];
                const out = typeof v === "number" ? (/rate|share|ci_|relevance|misfit/.test(c) && v <= 1 ? pct(v) : Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3))
                  : typeof v === "boolean" ? (v ? "yes" : "no") : v === null || v === undefined ? "—" : String(v);
                return <td key={c} className="num max-w-[280px] truncate whitespace-nowrap px-3 py-1.5 text-ink/90" title={String(v ?? "")}>{out}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChartBody({ spec, height = 280 }: { spec: ChartSpec; height?: number }) {
  const drill = useDrill(spec);
  const f = fmt(spec);
  const click = drill ? (d: any) => drill(d?.payload ?? d) : undefined;
  const xf = spec.x_field ?? "name";
  switch (spec.chart_type) {
    case "kpi":
      return <Kpis spec={spec} />;
    case "heatmap":
      return <Heatmap spec={spec} onDrill={drill} />;
    case "timeline":
      return <Timeline spec={spec} />;
    case "table":
      return <DataTable rows={spec.data} onRow={drill} />;
    case "horizontal_bar": {
      const h = Math.max(height, spec.data.length * 38 + 40);
      return (
        <ResponsiveContainer width="100%" height={h}>
          <BarChart data={spec.data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }} barGap={2}>
            <CartesianGrid stroke={grid} horizontal={false} />
            <XAxis type="number" tickFormatter={f} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey={xf} width={170} tickLine={false} axisLine={false} tick={{ fill: "#CBD5E1", fontSize: 12 }} />
            <Tooltip contentStyle={tooltipStyle} formatter={f} />
            {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
            {spec.series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[s.color]} radius={[0, 6, 6, 0]} onClick={click} cursor={drill ? "pointer" : undefined}
                fillOpacity={i === 0 ? 0.95 : 0.35} maxBarSize={22} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    }
    case "bar":
    case "stacked_bar":
      return (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={spec.data} margin={{ top: 8, right: 12, left: spec.data.length > 6 ? 44 : 0, bottom: spec.data.length > 6 ? 24 : 8 }}>
            <CartesianGrid stroke={grid} vertical={false} />
            <XAxis dataKey={xf} tickLine={false} axisLine={false} interval={0} angle={spec.data.length > 6 ? -28 : 0} textAnchor={spec.data.length > 6 ? "end" : "middle"} height={spec.data.length > 6 ? 90 : 30} tick={{ fontSize: 11, fill: "#94A3B8" }} />
            <YAxis tickFormatter={f} tickLine={false} axisLine={false} width={52} />
            <Tooltip contentStyle={tooltipStyle} formatter={f} />
            {spec.series.length > 1 && <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />}
            {spec.series.map((s) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[s.color]} stackId={spec.chart_type === "stacked_bar" ? "a" : undefined}
                radius={spec.chart_type === "stacked_bar" ? 0 : [6, 6, 0, 0]} maxBarSize={44} onClick={click} cursor={drill ? "pointer" : undefined} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      );
    case "error_bar":
      return (
        <ResponsiveContainer width="100%" height={Math.max(height, spec.data.length * 34 + 40)}>
          <ComposedChart data={spec.data.map((d) => ({ ...d, _err: [d[spec.y_field!] - d[spec.error_low_field!], d[spec.error_high_field!] - d[spec.y_field!]] }))}
            layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 4 }}>
            <CartesianGrid stroke={grid} horizontal={false} />
            <XAxis type="number" domain={[0, "auto"]} tickFormatter={f} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey={xf} width={170} tickLine={false} axisLine={false} tick={{ fill: "#CBD5E1", fontSize: 12 }} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any, p: any) => n === "_err" ? null : [`${f(v)} (95% CI ${pct(p.payload[spec.error_low_field!])}–${pct(p.payload[spec.error_high_field!])}, n=${p.payload.conversations})`, "Negative rate"]} />
            <Bar dataKey={spec.y_field!} fill={COLORS.violet} fillOpacity={0.75} radius={[0, 6, 6, 0]} maxBarSize={16} onClick={click} cursor={drill ? "pointer" : undefined}>
              <ErrorBar dataKey="_err" width={6} strokeWidth={1.5} stroke="#E2E8F0" direction="x" />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      );
    case "line":
    case "area": {
      const hasCi = spec.error_low_field && spec.data[0]?.[spec.error_low_field] !== undefined;
      const data = hasCi ? spec.data.map((d) => ({ ...d, _band: [d[spec.error_low_field!], d[spec.error_high_field!]] })) : spec.data;
      return (
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid stroke={grid} vertical={false} />
            <XAxis dataKey={xf} tickLine={false} axisLine={false} />
            <YAxis tickFormatter={f} tickLine={false} axisLine={false} width={52} domain={spec.value_format === "score" ? [-1, 1] : ["auto", "auto"]} />
            {spec.value_format === "score" && <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" />}
            <Tooltip contentStyle={tooltipStyle} formatter={(v: any, n: any) => (n === "95% CI" && Array.isArray(v) ? `${f(v[0])} – ${f(v[1])}` : f(v))}
              labelFormatter={(l, p) => (p?.[0]?.payload?.text ? `Turn ${l}: ${p[0].payload.text}` : String(l))} />
            {hasCi && <Area dataKey="_band" name="95% CI" stroke="none" fill={COLORS.cyan} fillOpacity={0.12} isAnimationActive={false} />}
            {spec.series.map((s, i) => (
              <Line key={s.key} dataKey={s.key} name={s.label} stroke={COLORS[s.color]} strokeWidth={i === 0 ? 2.5 : 1.5} animationDuration={500} strokeDasharray={i === 0 ? undefined : "5 4"}
                dot={(p: any) => {
                  const tp = p.payload?.turning_point;
                  return <circle key={p.index} cx={p.cx} cy={p.cy} r={tp && i === 0 ? 6 : 3.5} fill={tp && i === 0 ? (tp === "improved" ? COLORS.positive : COLORS.negative) : COLORS[s.color]}
                    stroke="#0B1020" strokeWidth={1.5} style={{ cursor: drill ? "pointer" : undefined }} onClick={() => drill?.(p.payload)} />;
                }} activeDot={{ r: 6 }} />
            ))}
            {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
          </ComposedChart>
        </ResponsiveContainer>
      );
    }
    case "donut": {
      const total = spec.data.reduce((s, d) => s + d.conversations, 0);
      return (
        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <ResponsiveContainer width="100%" height={height}>
            <PieChart>
              <Pie data={spec.data} dataKey="conversations" nameKey={xf} innerRadius="58%" outerRadius="85%" paddingAngle={2} stroke="none">
                {spec.data.map((d) => <Cell key={d[xf]} fill={COLORS[d.color] ?? COLORS.muted} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v.toLocaleString()} (${pct(v / total)})`} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="min-w-[160px] space-y-1.5 text-sm">
            {spec.data.map((d) => (
              <li key={d[xf]} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[d.color] }} />
                <span className="flex-1 capitalize text-muted">{d[xf]}</span><span className="num text-ink">{pct(d.share)}</span></li>
            ))}
          </ul>
        </div>
      );
    }
    case "priority_matrix": {
      const maxScore = Math.max(...spec.data.map((d) => d.priority_score));
      return (
        <ResponsiveContainer width="100%" height={height + 40}>
          <ScatterChart margin={{ top: 16, right: 24, left: 0, bottom: 16 }}>
            <CartesianGrid stroke={grid} />
            <XAxis type="number" dataKey="conversations" name="Conversations" tickLine={false} axisLine={false} label={{ value: "Conversations (volume)", position: "insideBottom", offset: -8, fill: "#64748B", fontSize: 11 }} />
            <YAxis type="number" dataKey="negative_rate" name="Negative rate" tickFormatter={(v) => pct(v, 0)} tickLine={false} axisLine={false} width={48} domain={["auto", "auto"]} />
            <ZAxis type="number" dataKey="priority_score" range={[120, 900]} name="Priority score" />
            <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }}
              content={({ payload }) => payload?.[0] ? (
                <div style={tooltipStyle} className="p-2.5">
                  <p className="font-medium">{payload[0].payload.name}</p>
                  <p className="text-muted">{payload[0].payload.conversations} conversations · {pct(payload[0].payload.negative_rate)} negative</p>
                  <p className="text-cyan">Priority {payload[0].payload.priority_score} · {payload[0].payload.priority}</p>
                </div>) : null} />
            <Scatter data={spec.data} onClick={click} cursor={drill ? "pointer" : undefined}>
              {spec.data.map((d) => <Cell key={d.name} fill={d.priority_score === maxScore ? COLORS.negative : d.priority === "High" ? COLORS.warning : d.priority === "Medium" ? COLORS.violet : COLORS.indigo} fillOpacity={0.75} />)}
              <LabelList dataKey="name" position="right" offset={12}
                content={(p: any) => {
                  const d = spec.data[p.index];
                  if (!d || (d.priority !== "High" && d.conversations !== Math.max(...spec.data.map((x) => x.conversations)))) return null;
                  return <text x={p.x + p.width + 6} y={p.y + p.height / 2} dy={4} fill="#CBD5E1" fontSize={11}>{d.name}</text>;
                }} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      );
    }
    case "scatter":
      return (
        <ResponsiveContainer width="100%" height={height}>
          <ScatterChart><CartesianGrid stroke={grid} /><XAxis dataKey={xf} /><YAxis dataKey={spec.y_field!} /><Tooltip contentStyle={tooltipStyle} />
            <Scatter data={spec.data} fill={COLORS.indigo} /></ScatterChart>
        </ResponsiveContainer>
      );
    default:
      return <DataTable rows={spec.data} />;
  }
}

export { LineChart };
