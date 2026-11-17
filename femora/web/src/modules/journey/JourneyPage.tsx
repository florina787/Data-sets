import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Download, Plus, Trash2, BookOpen } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { dayKey, uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { SOURCES } from "../conversation/sources";
import { AgeContextCard, NextPeriodCard } from "../forecast/ForecastCards";
import { SYMPTOMS, cycleLengths, cycleStats, doctorSummary, periodLength, stageHint, weeklySymptoms, type Confounder, type Flow, type Ovulation, type Period } from "./logic";

const CONFOUNDERS: Confounder[] = ["hormonal contraception", "hysterectomy", "ovaries removed", "pregnant or breastfeeding", "cancer treatment", "other medical cause"];
const tip = { contentStyle: { background: "var(--f-surface)", border: "1px solid var(--f-line)", borderRadius: 12, color: "var(--f-ink)" } };
const PALETTE = ["var(--f-primary)", "var(--f-accent)", "var(--f-warm)", "var(--f-good)"];

function Calendar({ month, periods, symptomDays, onPrev, onNext }: { month: Date; periods: Period[]; symptomDays: Set<string>; onPrev: () => void; onNext: () => void }) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const offset = (first.getDay() + 6) % 7;
  const inPeriod = (k: string) => periods.some((p) => k >= p.start && k <= (p.end ?? p.start));
  const isStart = (k: string) => periods.some((p) => p.start === k);
  const today = dayKey(new Date());
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <Button size="sm" aria-label="Previous month" onClick={onPrev}><ChevronLeft size={16} /></Button>
        <span className="font-display text-xl">{first.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</span>
        <Button size="sm" aria-label="Next month" onClick={onNext}><ChevronRight size={16} /></Button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d}>{d}</div>)}</div>
      <div className="mt-1 grid grid-cols-7 gap-1" role="grid" aria-label="Cycle calendar">
        {Array.from({ length: offset }, (_, i) => <div key={"e" + i} />)}
        {Array.from({ length: days }, (_, i) => {
          const k = dayKey(new Date(month.getFullYear(), month.getMonth(), i + 1, 12));
          const p = inPeriod(k), sym = symptomDays.has(k);
          return (
            <div key={k} role="gridcell" aria-label={`${k}${p ? ", period" : ""}${sym ? ", symptoms logged" : ""}`}
              className={`relative grid aspect-square place-items-center rounded-full text-sm ${p ? "bg-warm text-white" : "bg-surface-2"} ${isStart(k) ? "ring-2 ring-warm ring-offset-2 ring-offset-surface" : ""} ${k === today ? "font-bold outline outline-1 outline-ink" : ""}`}>
              {i + 1}{sym && <span className="absolute bottom-1 h-1.5 w-1.5 rounded-full bg-accent" />}
            </div>);
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted"><span className="flex items-center gap-1"><span className="h-3 w-3 rounded-full bg-warm" /> Period</span><span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-accent" /> Symptoms logged</span></div>
    </div>
  );
}

export function JourneyPage() {
  const app = useApp();
  const [periods, setPeriods] = usePersistent<Period[]>(`periods:${app.profile.id}`, () => []);
  const [ovu, setOvu] = usePersistent<Ovulation[]>(`ovulation:${app.profile.id}`, () => []);
  const [conf, setConf] = usePersistent<Confounder[]>(`confounders:${app.profile.id}`, () => []);
  const [month, setMonth] = useState(() => new Date());
  const [pf, setPf] = useState({ start: dayKey(new Date()), end: "", flow: "medium" as Flow, pain: 0 as 0 | 1 | 2 | 3, note: "" });
  const [sf, setSf] = useState({ name: SYMPTOMS[0], severity: 2 as 1 | 2 | 3, impact: 1 as 0 | 1 | 2 | 3, date: dayKey(new Date()), note: "" });
  const [of, setOf] = useState({ date: dayKey(new Date()), kind: "LH test positive" as Ovulation["kind"], value: "" });
  const [weeks, setWeeks] = useState(8);

  const sorted = [...periods].sort((a, b) => b.start.localeCompare(a.start));
  const stats = cycleStats(periods);
  const hint = stageHint(periods, conf);
  const lengths = cycleLengths(periods).map((c) => ({ cycle: new Date(c.start + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }), days: c.length }));
  const weekly = useMemo(() => weeklySymptoms(app.symptoms, weeks), [app.symptoms, weeks]);
  const top = useMemo(() => { const c: Record<string, number> = {}; app.symptoms.forEach((s) => { c[s.name] = (c[s.name] ?? 0) + 1; }); return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([n]) => n); }, [app.symptoms]);
  const symptomDays = new Set(app.symptoms.map((s) => dayKey(new Date(s.at))));

  function download() {
    const url = URL.createObjectURL(new Blob([doctorSummary(app.profile.name, periods, app.symptoms, ovu, conf, hint)], { type: "text/plain" }));
    const a = document.createElement("a"); a.href = url; a.download = "menopause-journey-summary.txt"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="Menopause journey" sub="Your cycles, symptoms and patterns, in your own records. Muse explains what patterns can mean, with honest uncertainty. It never diagnoses or predicts your final period."
        actions={<Button data-tour="journey-summary" variant="primary" onClick={download}><Download size={16} /> Doctor-ready summary</Button>} />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <Card><div data-tour="journey-calendar"><Calendar month={month} periods={periods} symptomDays={symptomDays} onPrev={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} onNext={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} /></div></Card>

        <Card title="What your pattern may mean">
          <div className="rounded-f-sm bg-surface-2 p-4">
            <div className="flex items-center gap-2"><Badge tone={hint.key === "regular" || hint.key === "insufficient" ? "neutral" : hint.key === "not-applicable" ? "warn" : "accent"}>Educational</Badge><b>{hint.title}</b></div>
            <p className="mt-1 text-sm">{hint.text}</p>
          </div>
          {stats && <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-f-sm bg-surface-2 p-3"><dt className="text-xs text-muted">Average cycle</dt><dd className="font-display text-3xl">{stats.mean}<span className="text-sm text-muted"> d</span></dd></div>
            <div className="rounded-f-sm bg-surface-2 p-3"><dt className="text-xs text-muted">Range</dt><dd className="font-display text-3xl">{stats.min}–{stats.max}</dd></div>
            <div className="rounded-f-sm bg-surface-2 p-3"><dt className="text-xs text-muted">Biggest change</dt><dd className="font-display text-3xl">{stats.maxConsecutiveDiff}<span className="text-sm text-muted"> d</span></dd></div>
          </dl>}
          <fieldset className="mt-4"><legend className="text-sm font-medium">Anything that affects your cycles?</legend>
            <div className="mt-1 flex flex-wrap gap-2">{CONFOUNDERS.map((c) => { const on = conf.includes(c); return <button key={c} aria-pressed={on} onClick={() => setConf(on ? conf.filter((x) => x !== c) : [...conf, c])} className={`rounded-full px-3 py-1 text-sm ${on ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{c}</button>; })}</div></fieldset>
          <p className="mt-3 text-xs text-muted">Based on STRAW+10 staging criteria [{SOURCES[1].publisher}, {SOURCES[1].year}]. Patterns are estimates from what you log; only a clinician can assess your stage.</p>
        </Card>
      </div>

      <div data-tour="journey-forecast" className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.6fr]">
        <NextPeriodCard periods={periods} />
        <AgeContextCard age={app.profile.age} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title="Cycle lengths">
          {lengths.length === 0 ? <p className="text-sm text-muted">Log at least two period start dates to see your cycle lengths.</p> : (
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
            </figure>)}
        </Card>

        <Card title="Symptoms over time" actions={<select aria-label="Date range" className="rounded-full border border-line bg-surface px-3 py-1 text-sm" value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}><option value={4}>4 weeks</option><option value={8}>8 weeks</option><option value={12}>12 weeks</option><option value={26}>6 months</option></select>}>
          {app.symptoms.length === 0 ? <p className="text-sm text-muted">Log symptoms below, or from a conversation with Muse, to see your trends.</p> : (
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
            </figure>)}
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <Card title="Log a period">
          <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (!pf.start) return; setPeriods([...periods, { id: uid(), start: pf.start, end: pf.end || undefined, flow: pf.flow, pain: pf.pain, note: pf.note || undefined }]); setPf({ ...pf, end: "", note: "" }); }}>
            <Field label="First day"><input type="date" className={inputCls} value={pf.start} onChange={(e) => setPf({ ...pf, start: e.target.value })} required /></Field>
            <Field label="Last day of bleeding (optional)"><input type="date" className={inputCls} value={pf.end} min={pf.start} onChange={(e) => setPf({ ...pf, end: e.target.value })} /></Field>
            <Field label="Flow"><select className={inputCls} value={pf.flow} onChange={(e) => setPf({ ...pf, flow: e.target.value as Flow })}>{["spotting", "light", "medium", "heavy"].map((f) => <option key={f}>{f}</option>)}</select></Field>
            <Field label="Pain (0–3)"><input type="range" min={0} max={3} value={pf.pain} onChange={(e) => setPf({ ...pf, pain: Number(e.target.value) as 0 | 1 | 2 | 3 })} /></Field>
            <Field label="Note"><input className={inputCls} value={pf.note} onChange={(e) => setPf({ ...pf, note: e.target.value })} placeholder="e.g. spotting before" /></Field>
            <Button type="submit" variant="primary"><Plus size={16} /> Save period</Button>
          </form>
          {sorted.length > 0 && <ul className="mt-4 divide-y divide-line text-sm">{sorted.slice(0, 8).map((p) => (
            <li key={p.id} className="flex items-center gap-2 py-2"><span className="flex-1">{new Date(p.start + "T12:00").toLocaleDateString()}{p.end ? ` · ${periodLength(p)} days` : ""} · {p.flow}</span>
              <button aria-label={`Delete period starting ${p.start}`} className="text-muted hover:text-danger" onClick={() => setPeriods(periods.filter((x) => x.id !== p.id))}><Trash2 size={15} /></button></li>))}</ul>}
        </Card>

        <Card title="Log a symptom">
          <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); app.logSymptom(sf.name, sf.severity, "form", { impact: sf.impact, note: sf.note || undefined, at: new Date(sf.date + "T12:00").getTime() }); setSf({ ...sf, note: "" }); }}>
            <Field label="Symptom"><select className={inputCls} value={sf.name} onChange={(e) => setSf({ ...sf, name: e.target.value })}>{SYMPTOMS.map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Date"><input type="date" className={inputCls} value={sf.date} onChange={(e) => setSf({ ...sf, date: e.target.value })} /></Field>
            <Field label="Severity"><div className="flex gap-2">{(["Mild", "Moderate", "Severe"] as const).map((l, i) => <button type="button" key={l} aria-pressed={sf.severity === i + 1} onClick={() => setSf({ ...sf, severity: (i + 1) as 1 | 2 | 3 })} className={`rounded-full px-3 py-1 text-sm ${sf.severity === i + 1 ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{l}</button>)}</div></Field>
            <Field label="Effect on your day"><div className="flex flex-wrap gap-2">{["None", "A little", "A lot", "Severe"].map((l, i) => <button type="button" key={l} aria-pressed={sf.impact === i} onClick={() => setSf({ ...sf, impact: i as 0 | 1 | 2 | 3 })} className={`rounded-full px-3 py-1 text-sm ${sf.impact === i ? "bg-accent text-white" : "bg-surface-2"}`}>{l}</button>)}</div></Field>
            <Field label="Note"><input className={inputCls} value={sf.note} onChange={(e) => setSf({ ...sf, note: e.target.value })} /></Field>
            <Button type="submit" variant="primary"><Plus size={16} /> Save symptom</Button>
          </form>
          {app.symptoms.length > 0 && <ul className="mt-4 divide-y divide-line text-sm">{[...app.symptoms].sort((a, b) => b.at - a.at).slice(0, 6).map((s) => (
            <li key={s.id} className="flex items-center gap-2 py-2"><span className="flex-1">{s.name} · {["", "mild", "moderate", "severe"][s.severity]} · {new Date(s.at).toLocaleDateString()}</span>
              <button aria-label={`Delete ${s.name}`} className="text-muted hover:text-danger" onClick={() => app.removeSymptom(s.id)}><Trash2 size={15} /></button></li>))}</ul>}
        </Card>

        <Card title="Ovulation observations">
          <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); setOvu([...ovu, { id: uid(), date: of.date, kind: of.kind, value: of.value || undefined }]); setOf({ ...of, value: "" }); }}>
            <Field label="Date"><input type="date" className={inputCls} value={of.date} onChange={(e) => setOf({ ...of, date: e.target.value })} /></Field>
            <Field label="Observation"><select className={inputCls} value={of.kind} onChange={(e) => setOf({ ...of, kind: e.target.value as Ovulation["kind"] })}>{["LH test positive", "LH test negative", "Basal temperature", "Cervical mucus", "Clinician result"].map((k) => <option key={k}>{k}</option>)}</select></Field>
            <Field label="Value (optional)"><input className={inputCls} value={of.value} onChange={(e) => setOf({ ...of, value: e.target.value })} placeholder="e.g. 36.6 °C, egg-white" /></Field>
            <Button type="submit" variant="primary"><Plus size={16} /> Save</Button>
          </form>
          {ovu.length > 0 && <ul className="mt-4 divide-y divide-line text-sm">{[...ovu].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 6).map((o) => (
            <li key={o.id} className="flex items-center gap-2 py-2"><span className="flex-1">{o.date} · {o.kind}{o.value ? ` · ${o.value}` : ""}</span>
              <button aria-label={`Delete observation ${o.date}`} className="text-muted hover:text-danger" onClick={() => setOvu(ovu.filter((x) => x.id !== o.id))}><Trash2 size={15} /></button></li>))}</ul>}
          <Notice tone="neutral">Calendar dates alone can't confirm ovulation, and fertile-window estimates are not contraception.</Notice>
        </Card>
      </div>

      <Card className="mt-5" title={<span className="flex items-center gap-2"><BookOpen size={18} className="text-accent" /> Understanding the transition</span>}>
        <div className="grid gap-5 text-sm md:grid-cols-3">
          <div><h4 className="font-display text-lg">Perimenopause</h4><p className="mt-1 text-muted">The years before periods stop, when hormone levels fluctuate. Cycles may become irregular, and symptoms like hot flashes, sleep changes and mood shifts can begin, sometimes years before the final period.</p></div>
          <div><h4 className="font-display text-lg">Menopause</h4><p className="mt-1 text-muted">The final menstrual period, recognised only looking back after 12 months without a period. Most women reach it between 45 and 55 [S1]. Earlier menopause, or menopause after surgery or treatment, deserves specific medical advice.</p></div>
          <div><h4 className="font-display text-lg">Postmenopause</h4><p className="mt-1 text-muted">The years after. Some symptoms ease while bone and heart health become more important. Effective hormonal and non-hormonal treatments exist [S3]; a clinician can help you weigh them.</p></div>
        </div>
        <ul className="mt-4 space-y-1 text-xs text-muted">{SOURCES.map((s) => <li key={s.id}>[{s.id}] <a className="underline" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.publisher}, {s.year}</li>)}</ul>
      </Card>
    </div>
  );
}
