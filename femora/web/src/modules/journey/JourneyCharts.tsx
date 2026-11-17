import { Bar, BarChart, CartesianGrid, Legend, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const tip = { contentStyle: { background: "var(--f-surface)", border: "1px solid var(--f-line)", borderRadius: 12, color: "var(--f-ink)" } };
const PALETTE = ["var(--f-primary)", "var(--f-accent)", "var(--f-warm)", "var(--f-good)"];

export function CycleChart({ lengths }: { lengths: { cycle: string; days: number }[] }) {
  return (
    <figure aria-label={`Cycle lengths: ${lengths.map((l) => `${l.cycle} ${l.days} days`).join(", ")}`}>
              <div className="h-60"><ResponsiveContainer><BarChart data={lengths} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--f-line)" />
                <ReferenceArea y1={21} y2={35} fill="var(--f-good)" fillOpacity={0.08} />
                <XAxis dataKey="cycle" tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip {...tip} formatter={(v) => `${v} days`} cursor={{ fill: "var(--f-surface-2)" }} />
                <Bar dataKey="days" fill="var(--f-warm)" radius={[8, 8, 0, 0]} animationDuration={700} />
              </BarChart></ResponsiveContainer></div>
              <figcaption className="text-xs text-muted">Each bar is one cycle (first day to the next first day). The shaded band marks the commonly cited 21–35 day range.</figcaption>
            </figure>
  );
}

export function SymptomChart({ weekly, top, weeks }: { weekly: Record<string, string | number>[]; top: string[]; weeks: number }) {
  return (
    <figure aria-label={`Weekly symptom counts for the last ${weeks} weeks`}>
              <div className="h-60"><ResponsiveContainer><BarChart data={weekly} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--f-line)" />
                <XAxis dataKey="week" tick={{ fill: "var(--f-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip {...tip} cursor={{ fill: "var(--f-surface-2)" }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                {top.map((n, i) => <Bar key={n} dataKey={n} stackId="s" fill={PALETTE[i]} radius={i === top.length - 1 ? [6, 6, 0, 0] : 0} animationDuration={700} />)}
              </BarChart></ResponsiveContainer></div>
              <figcaption className="text-xs text-muted">Number of times each of your most-logged symptoms was recorded per week.</figcaption>
            </figure>
  );
}
