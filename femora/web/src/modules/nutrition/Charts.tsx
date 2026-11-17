// Purposeful, theme-aware charts. Every chart has a text alternative.
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { energySplit } from "./engine";
import type { Nutrients } from "./foods";

const C = { protein: "var(--f-primary)", carbs: "var(--f-accent)", fat: "var(--f-warm)", grid: "var(--f-line)", muted: "var(--f-muted)" };
const tip = { contentStyle: { background: "var(--f-surface)", border: "1px solid var(--f-line)", borderRadius: 12, color: "var(--f-ink)" } };

export interface DayPoint { day: string; protein: number; calcium: number; fiber: number; sugarPct: number | null }

/** 7-day progress toward goals, as % of target, so different units share one axis. */
export function WeekChart({ data, targets }: { data: DayPoint[]; targets: { protein: number; calcium: number; fiber: number } }) {
  const rows = data.map((d) => ({ day: d.day, Protein: Math.round((d.protein / targets.protein) * 100), Calcium: Math.round((d.calcium / targets.calcium) * 100), Fiber: Math.round((d.fiber / targets.fiber) * 100) }));
  const summary = rows.map((r) => `${r.day}: protein ${r.Protein}%, calcium ${r.Calcium}%, fiber ${r.Fiber}%`).join("; ");
  return (
    <figure aria-label={`Seven-day goal progress. ${summary}`}>
      <div className="h-64"><ResponsiveContainer>
        <BarChart data={rows} margin={{ top: 10, right: 8, left: -18, bottom: 0 }} barGap={2}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis dataKey="day" tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis unit="%" tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, (max: number) => Math.max(120, Math.ceil(max / 20) * 20)]} />
          <ReferenceLine y={100} stroke={C.muted} strokeDasharray="4 4" label={{ value: "goal", fill: C.muted, fontSize: 11, position: "insideTopRight" }} />
          <Tooltip {...tip} formatter={(v) => `${v}% of goal`} cursor={{ fill: "var(--f-surface-2)" }} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="Protein" fill={C.protein} radius={[6, 6, 0, 0]} />
          <Bar dataKey="Calcium" fill={C.carbs} radius={[6, 6, 0, 0]} />
          <Bar dataKey="Fiber" fill="var(--f-good)" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer></div>
      <figcaption className="text-xs text-muted">Each bar is that day's intake as a percentage of your goal. The dashed line is 100%.</figcaption>
    </figure>
  );
}

/** Where today's energy came from. */
export function EnergyDonut({ n }: { n: Partial<Nutrients> }) {
  const s = energySplit(n);
  if (!s) return <p className="text-sm text-muted">Log a meal to see where your energy comes from.</p>;
  const rows = [{ name: "Protein", value: s.protein, color: C.protein }, { name: "Carbs", value: s.carbs, color: C.carbs }, { name: "Fat", value: s.fat, color: C.fat }];
  return (
    <figure aria-label={`Energy split: protein ${s.protein}%, carbohydrates ${s.carbs}%, fat ${s.fat}%`} className="flex items-center gap-4">
      <div className="h-36 w-36 shrink-0"><ResponsiveContainer>
        <PieChart><Pie data={rows} dataKey="value" innerRadius={42} outerRadius={64} paddingAngle={3} stroke="none">{rows.map((r) => <Cell key={r.name} fill={r.color} />)}</Pie><Tooltip {...tip} formatter={(v) => `${v}%`} /></PieChart>
      </ResponsiveContainer></div>
      <ul className="space-y-1 text-sm">{rows.map((r) => <li key={r.name} className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: r.color }} />{r.name} <b>{r.value}%</b></li>)}</ul>
    </figure>
  );
}

