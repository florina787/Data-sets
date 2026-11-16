import { Area, ComposedChart, CartesianGrid, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { CalendarClock, LineChart as LineIcon } from "lucide-react";
import { Badge, Card } from "../../components/ui";
import type { Period } from "../journey/logic";
import { MODEL, daysUntil, forecastNextPeriod, populationContext } from "./forecast";

const tip = { contentStyle: { background: "var(--f-surface)", border: "1px solid var(--f-line)", borderRadius: 12, color: "var(--f-ink)" } };
const fmt = (d: string) => new Date(d + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

export function NextPeriodCard({ periods }: { periods: Period[] }) {
  const f = forecastNextPeriod(periods);
  return (
    <Card title={<span className="flex items-center gap-2"><CalendarClock size={18} className="text-accent" /> Next period forecast</span>} actions={<Badge tone="accent">Estimate</Badge>}>
      {f.status !== "ok" ? <p className="text-sm text-muted">{f.reason}</p> : (
        <div>
          <p className="font-display text-3xl">{fmt(f.nextStart!)} <span className="text-base text-muted">({daysUntil(f.nextStart!) >= 0 ? `in ${daysUntil(f.nextStart!)} days` : `${-daysUntil(f.nextStart!)} days ago`})</span></p>
          <p className="mt-1 text-sm">Likely between <b>{fmt(f.earliest!)}</b> and <b>{fmt(f.latest!)}</b> (about 80% range), based on a weighted average cycle of {f.expectedLength} days.</p>
          {f.backtestN ? <p className="mt-2 text-xs text-muted">Tested on your own history: off by {f.backtestMAE} days on average across {f.backtestN} past cycle{f.backtestN > 1 ? "s" : ""}.</p> : null}
          <p className="mt-2 text-xs text-muted">A time-series estimate from your logs, not a fertility or contraception tool.</p>
        </div>)}
    </Card>
  );
}

export function AgeContextCard({ age }: { age: number }) {
  const k = MODEL.km, g = MODEL.generations as unknown as Record<string, { ages: number[]; reached: number[]; n: number }>;
  const rows = k.ages.map((a, i) => ({ age: a, reached: Math.round(k.reached[i] * 100), band: [Math.round(k.reached_lo[i] * 100), Math.round(k.reached_hi[i] * 100)],
    "Born 1950s": g["1950"]?.ages.includes(a) ? Math.round(g["1950"].reached[g["1950"].ages.indexOf(a)] * 100) : undefined,
    "Born 1960s": g["1960"]?.ages.includes(a) ? Math.round(g["1960"].reached[g["1960"].ages.indexOf(a)] * 100) : undefined }));
  const ctx = age >= 35 && age <= 60 ? populationContext(age) : null;
  const flow = MODEL.data.cohort_flow;
  return (
    <Card title={<span className="flex items-center gap-2"><LineIcon size={18} className="text-accent" /> Your age in context</span>} actions={<Badge tone="primary">Real data · NHANES</Badge>}>
      {ctx ? <p className="text-sm">Among U.S. women aged <b>{age}</b>, about <b>{Math.round(ctx.reached * 100)}%</b> had reached natural menopause (95% CI {Math.round(ctx.lo * 100)}–{Math.round(ctx.hi * 100)}%). The median age was <b>{ctx.medianAge}</b>.</p>
        : <p className="text-sm text-muted">{age ? "This chart covers ages 35–60." : <>Add your age in <Link className="underline" to="/app/settings">Profile</Link> to see where you sit on this curve.</>}</p>}
      <figure aria-label={`Share of women who had reached natural menopause by age, from ${k.ages[0]} to ${k.ages[k.ages.length - 1]}; median ${k.median_age}`}>
        <div className="mt-3 h-64"><ResponsiveContainer><ComposedChart data={rows} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--f-line)" />
          <XAxis dataKey="age" tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis unit="%" domain={[0, 100]} tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip {...tip} formatter={(v) => (Array.isArray(v) ? `${v[0]}–${v[1]}%` : `${v}%`)} labelFormatter={(a) => `Age ${a}`} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Area dataKey="band" name="95% CI" fill="var(--f-accent)" fillOpacity={0.15} stroke="none" isAnimationActive />
          <Line dataKey="reached" name="All women" stroke="var(--f-primary)" strokeWidth={2.5} dot={false} animationDuration={900} />
          <Line dataKey="Born 1950s" stroke="var(--f-warm)" strokeDasharray="4 4" dot={false} connectNulls />
          <Line dataKey="Born 1960s" stroke="var(--f-good)" strokeDasharray="4 4" dot={false} connectNulls />
          {ctx && <ReferenceLine x={age} stroke="var(--f-accent)" strokeWidth={2} label={{ value: "You", fill: "var(--f-accent)", fontSize: 12, position: "top" }} />}
        </ComposedChart></ResponsiveContainer></div>
        <figcaption className="text-xs text-muted">Trained with open-source lifelines on {flow.analysis_cohort.toLocaleString()} women ({flow.natural_menopause_events.toLocaleString()} natural menopause events) from {flow.women_in_rhq_files.toLocaleString()} women in CDC NHANES 2013–2018, survey-weighted. Dashed lines compare generations. A population picture, never a prediction for you; U.S. data, self-reported ages.</figcaption>
      </figure>
    </Card>
  );
}
