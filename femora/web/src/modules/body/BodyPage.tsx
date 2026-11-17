import { useMemo, useState } from "react";
import { Download, Plus, Trash2, ChevronDown } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { dayKey, uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { METRICS, RANGES, bpNote, daily, glucoseNote, hba1cNote, inRange, metric, summary, toCSV, type BodyRecord, type MetricId, type RangeKey, type RangeNote } from "./logic";

const tip = { contentStyle: { background: "var(--f-surface)", border: "1px solid var(--f-line)", borderRadius: 12, color: "var(--f-ink)" } };
const fmtDate = (d: string) => new Date(d + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
const show = (id: MetricId, v: number, v2?: number) => (id === "bp" ? `${v}/${v2 ?? "–"}` : metric(id).scale ? metric(id).scale![v] ?? String(v) : id === "steps" ? Math.round(v).toLocaleString() : String(v));

function Spark({ data }: { data: { value: number }[] }) {
  if (data.length < 2) return <div className="h-10" />;
  const vs = data.map((d) => d.value), min = Math.min(...vs), max = Math.max(...vs), r = max - min || 1;
  const pts = vs.map((v, i) => `${(i / (vs.length - 1)) * 100},${36 - ((v - min) / r) * 32}`).join(" ");
  return <svg viewBox="0 0 100 40" className="h-10 w-full" aria-hidden preserveAspectRatio="none"><polyline points={pts} fill="none" stroke="var(--f-accent)" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>;
}

function noteFor(r: BodyRecord): RangeNote | null {
  if (r.metric === "bp" && r.value2) return bpNote(r.value, r.value2);
  if (r.metric === "hba1c") return hba1cNote(r.value);
  if (r.metric === "glucose") return glucoseNote(r.value, r.context);
  return null;
}

export function BodyPage() {
  const app = useApp();
  const [records, setRecords] = usePersistent<BodyRecord[]>(`body:${app.profile.id}`, () => []);
  const [sel, setSel] = useState<MetricId>("sleep");
  const [range, setRange] = useState<RangeKey>("30d");
  const [compare, setCompare] = useState<MetricId | "">("");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ date: dayKey(new Date()), value: "", value2: "", location: "", context: "", note: "" });
  const m = metric(sel);
  const series = useMemo(() => inRange(records, sel, range), [records, sel, range]);
  const s = summary(series);
  const cmp = compare ? daily(inRange(records, compare, range)) : [];
  const chart = useMemo(() => {
    const map = new Map<string, Record<string, number | string | undefined>>();
    daily(series).forEach((d) => map.set(d.date, { date: d.date, [m.label]: d.value, ...(sel === "bp" ? { Diastolic: d.value2 } : {}) }));
    cmp.forEach((d) => map.set(d.date, { ...(map.get(d.date) ?? { date: d.date }), [metric(compare as MetricId).label]: d.value }));
    return [...map.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [series, cmp, sel, compare, m.label]);
  const lastNote = s ? noteFor(s.latest) : null;

  function add(e: React.FormEvent) {
    e.preventDefault();
    const v = Number(f.value); if (f.value === "" || Number.isNaN(v)) return;
    const rec: BodyRecord = { id: uid(), metric: sel, date: f.date, value: v, value2: sel === "bp" && f.value2 ? Number(f.value2) : undefined, location: f.location || undefined, context: f.context || undefined, note: f.note || undefined };
    setRecords([...records, rec]);
    const n = noteFor(rec);
    if (n?.urgent) app.notify({ key: `urgent-${rec.id}`, category: "safety", priority: "critical", title: n.label, body: n.text, link: "/app/body" });
    setF({ ...f, value: "", value2: "", note: "" });
  }

  function exportCSV() {
    const url = URL.createObjectURL(new Blob([toCSV(records)], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "health-records.csv"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="Body, movement & mind" sub="Your own records, from blood pressure and sleep to joints, skin and mood. Muse shows trends and explains published guideline ranges. No scores, no diagnoses."
        actions={records.length ? <Button onClick={exportCSV}><Download size={16} /> Export CSV</Button> : undefined} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        {METRICS.map((x) => { const r = inRange(records, x.id, "30d"); const su = summary(r); return (
          <button key={x.id} onClick={() => setSel(x.id)} aria-pressed={sel === x.id} className={`rounded-f-sm p-3 text-left transition ${sel === x.id ? "bg-primary text-primary-ink" : "bg-surface shadow-f hover:-translate-y-0.5"}`}>
            <div className={`text-xs ${sel === x.id ? "opacity-80" : "text-muted"}`}>{x.label}</div>
            <div className="font-display text-xl">{su ? show(x.id, su.latest.value, su.latest.value2) : "–"}</div>
            {sel !== x.id && <Spark data={daily(r)} />}
          </button>); })}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <Card title={`${m.label}${m.unit && !m.scale ? ` (${m.unit})` : ""}`} actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-full bg-surface-2 p-0.5" role="radiogroup" aria-label="Date range">{(Object.keys(RANGES) as RangeKey[]).map((k) => <button key={k} role="radio" aria-checked={range === k} onClick={() => setRange(k)} className={`rounded-full px-2.5 py-1 text-xs ${range === k ? "bg-surface shadow-f" : "text-muted"}`}>{k}</button>)}</div>
            <select aria-label="Compare with" className="rounded-full border border-line bg-surface px-2 py-1 text-xs" value={compare} onChange={(e) => setCompare(e.target.value as MetricId | "")}><option value="">Compare with…</option>{METRICS.filter((x) => x.id !== sel).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
          </div>}>
          {chart.length === 0 ? <p className="py-10 text-center text-sm text-muted">No {m.label.toLowerCase()} records in this period. Add one on the right.</p> : (
            <figure aria-label={`${m.label} over ${range}: ${series.length} records${s ? `, average ${s.avg}` : ""}`}>
              <div className="h-72"><ResponsiveContainer><LineChart data={chart} margin={{ top: 10, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--f-line)" />
                <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="a" tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
                {compare && <YAxis yAxisId="b" orientation="right" tick={{ fill: "var(--f-muted)", fontSize: 12 }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />}
                <Tooltip {...tip} labelFormatter={(d) => fmtDate(String(d))} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                {sel === "bp" && <ReferenceLine yAxisId="a" y={130} stroke="var(--f-warn)" strokeDasharray="4 4" label={{ value: "130", fill: "var(--f-muted)", fontSize: 11 }} />}
                <Line yAxisId="a" type="monotone" dataKey={m.label} stroke="var(--f-primary)" strokeWidth={2.5} dot={{ r: 3 }} connectNulls animationDuration={700} />
                {sel === "bp" && <Line yAxisId="a" type="monotone" dataKey="Diastolic" stroke="var(--f-warm)" strokeWidth={2} dot={{ r: 3 }} connectNulls animationDuration={700} />}
                {compare && <Line yAxisId="b" type="monotone" dataKey={metric(compare).label} stroke="var(--f-accent)" strokeWidth={2} strokeOpacity={0.85} dot={{ r: 2.5, fill: "var(--f-accent)" }} connectNulls animationDuration={700} />}
              </LineChart></ResponsiveContainer></div>
              {compare && <figcaption className="text-xs text-muted">Comparing two of your own measures over time shows patterns, not causes.</figcaption>}
            </figure>)}
          {s && (
            <div className="mt-3">
              <button className="flex items-center gap-1 text-sm font-medium text-primary" aria-expanded={open} onClick={() => setOpen(!open)}><ChevronDown size={16} className={`transition ${open ? "rotate-180" : ""}`} /> Insights</button>
              {open && <dl className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div><dt className="text-muted">Latest</dt><dd className="font-medium">{show(sel, s.latest.value, s.latest.value2)} · {fmtDate(s.latest.date)}</dd></div>
                <div><dt className="text-muted">Average</dt><dd className="font-medium">{m.scale ? s.avg : s.avg.toLocaleString()}</dd></div>
                <div><dt className="text-muted">Range</dt><dd className="font-medium">{s.min}–{s.max}</dd></div>
                <div><dt className="text-muted">Change</dt><dd className="font-medium">{s.change > 0 ? "+" : ""}{s.change} {m.scale ? "" : m.unit}</dd></div>
              </dl>}
            </div>)}
          {lastNote && <div className={`mt-4 rounded-f-sm p-3 text-sm ${lastNote.tone === "danger" ? "bg-danger/12" : lastNote.tone === "warn" ? "bg-warn/15" : lastNote.tone === "good" ? "bg-good/12" : "bg-surface-2"}`} role={lastNote.urgent ? "alert" : "note"}>
            <Badge tone={lastNote.tone === "danger" ? "danger" : lastNote.tone === "warn" ? "warn" : lastNote.tone === "good" ? "good" : "neutral"}>{lastNote.label}</Badge> <span className="ml-1">{lastNote.text}</span></div>}
        </Card>

        <Card title={`Add ${m.label.toLowerCase()}`}>
          <p className="mb-3 text-sm text-muted">{m.help}</p>
          <form className="space-y-2" onSubmit={add}>
            <Field label="Date"><input type="date" className={inputCls} value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></Field>
            {m.scale ? (
              <Field label={m.label}><div className="flex flex-wrap gap-2">{m.scale.map((l, i) => l && <button type="button" key={l} aria-pressed={f.value === String(i)} onClick={() => setF({ ...f, value: String(i) })} className={`rounded-full px-3 py-1 text-sm ${f.value === String(i) ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{l}</button>)}</div></Field>
            ) : sel === "bp" ? (
              <div className="grid grid-cols-2 gap-2"><Field label="Systolic"><input type="number" min={60} max={260} className={inputCls} value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} required /></Field>
                <Field label="Diastolic"><input type="number" min={30} max={160} className={inputCls} value={f.value2} onChange={(e) => setF({ ...f, value2: e.target.value })} required /></Field></div>
            ) : <Field label={`${m.label} (${m.unit})`}><input type="number" step={m.step} min={m.min} max={m.max} className={inputCls} value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} required /></Field>}
            {m.locations && <Field label="Where"><select className={inputCls} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })}><option value="">Choose…</option>{m.locations.map((l) => <option key={l}>{l}</option>)}</select></Field>}
            {sel === "glucose" && <Field label="When"><select className={inputCls} value={f.context} onChange={(e) => setF({ ...f, context: e.target.value })}><option value="">Not specified</option><option value="fasting">Fasting</option><option value="after-meal">After a meal</option><option value="random">Random</option></select></Field>}
            <Field label="Note (optional)"><input className={inputCls} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
            <Button type="submit" variant="primary" disabled={f.value === ""}><Plus size={16} /> Save</Button>
          </form>
          {series.length > 0 && <ul className="mt-4 max-h-64 divide-y divide-line overflow-y-auto text-sm">{[...series].reverse().map((r) => (
            <li key={r.id} className="flex items-center gap-2 py-2"><span className="w-16 text-muted">{fmtDate(r.date)}</span><span className="flex-1 font-medium">{show(r.metric, r.value, r.value2)}{r.location ? ` · ${r.location}` : ""}{r.context ? ` · ${r.context}` : ""}</span>
              <button aria-label={`Delete ${m.label} on ${r.date}`} className="text-muted hover:text-danger" onClick={() => setRecords(records.filter((x) => x.id !== r.id))}><Trash2 size={15} /></button></li>))}</ul>}
        </Card>
      </div>
      <Notice tone="neutral">Ranges shown come from published guidelines (ACC/AHA 2017 for blood pressure, ADA for glucose and HbA1c). They help you talk with your clinician. They're not a diagnosis. Wearable import (Apple Health, Health Connect) needs the mobile app.</Notice>
    </div>
  );
}
