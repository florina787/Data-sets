import { useState } from "react";
import { Check, Clock, Download, Pill, Plus, SkipForward, Stethoscope, Trash2 } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { CHECKUP_KINDS, adherence, checkupState, completeCheckup, daysUntil, doseStatus, record, refillSoon, validTime, type Medication } from "./logic";
import { useReminders } from "./useReminders";

const emptyMed = { name: "", dose: "", frequency: "Once daily", times: "08:00", start: "", end: "", prescriber: "", refill: "", notes: "", supplement: false };

export function RemindersPage() {
  const app = useApp();
  const { meds, setMeds, checkups, setCheckups } = useReminders();
  const [m, setM] = useState(emptyMed);
  const [c, setC] = useState({ kind: CHECKUP_KINDS[0], next: "", last: "", repeatMonths: "", source: "self" as const, notes: "" });
  const [q, setQ] = useState<Record<string, string>>({});
  const doses = doseStatus(meds);
  const times = m.times.split(",").map((t) => t.trim()).filter(Boolean);
  const timesOk = times.length > 0 && times.every(validTime);
  const update = (id: string, f: (x: Medication) => Medication) => setMeds((ms) => ms.map((x) => (x.id === id ? f(x) : x)));

  function exportList() {
    const body = [`Medication & supplement list for ${app.profile.name}, exported ${new Date().toLocaleString()}`, "",
      ...meds.map((x) => `- ${x.name}${x.supplement ? " (supplement)" : ""}: ${x.dose}, ${x.frequency} at ${x.times.join(", ")}${x.prescriber ? `; prescriber ${x.prescriber}` : ""}${x.start ? `; from ${x.start}` : ""}${x.end ? ` to ${x.end}` : ""}${x.notes ? `; notes: ${x.notes}` : ""}`)].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const a = document.createElement("a"); a.href = url; a.download = "medication-list.txt"; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="Medication & check-up planner" sub="Reminders follow exactly the schedule you enter. Muse never changes doses or timing, and never suggests starting or stopping a medicine." />
      <Notice tone="neutral">Stored only in this browser. Notifications appear while Muse is open, and browser alerts need your permission (Settings → Notifications). Delivery on locked or closed devices needs the future mobile app.</Notice>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><Pill size={18} className="text-primary" /> Today</span>} actions={meds.length ? <Button size="sm" onClick={exportList}><Download size={14} /> Export list</Button> : undefined}>
          {doses.length === 0 ? <p className="text-sm text-muted">No medication or supplements scheduled. Add one below.</p> : (
            <ul className="divide-y divide-line">{doses.map((d) => (
              <li key={d.med.id + d.time} className="flex flex-wrap items-center gap-2 py-2.5">
                <span className="w-12 font-medium">{d.time}</span>
                <span className="flex-1"><b className="font-medium">{d.med.name}</b> <span className="text-sm text-muted">{d.med.dose}</span></span>
                {d.status === "taken" || d.status === "skipped" ? <Badge tone={d.status === "taken" ? "good" : "neutral"}>{d.status}</Badge> : <>
                  {d.status === "due" && <Badge tone="warn">Due</Badge>}{d.status === "snoozed" && <Badge>Snoozed</Badge>}
                  <Button size="sm" variant="primary" onClick={() => update(d.med.id, (x) => record(x, d.time, "taken"))}><Check size={14} /> Taken</Button>
                  <Button size="sm" onClick={() => update(d.med.id, (x) => record(x, d.time, "snoozed"))} aria-label={`Snooze ${d.med.name} 15 minutes`}><Clock size={14} /></Button>
                  <Button size="sm" onClick={() => update(d.med.id, (x) => record(x, d.time, "skipped"))} aria-label={`Skip ${d.med.name}`}><SkipForward size={14} /></Button></>}
              </li>))}</ul>)}
          {meds.length > 0 && <ul className="mt-3 space-y-1 border-t border-line pt-3 text-sm">{meds.map((x) => { const a = adherence(x, 7); return (
            <li key={x.id} className="flex items-center gap-2"><span className="flex-1">{x.name} · {x.frequency} · {x.times.join(", ")}{refillSoon(x) && <> <Badge tone="warn">Refill soon</Badge></>}</span>
              <span className="text-xs text-muted">{a === null ? "no history" : `${a}% taken, 7 days`}</span>
              <button aria-label={`Delete ${x.name}`} className="text-muted hover:text-danger" onClick={() => setMeds((ms) => ms.filter((y) => y.id !== x.id))}><Trash2 size={15} /></button></li>); })}</ul>}
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); if (!m.name.trim() || !timesOk) return;
            setMeds((ms) => [...ms, { id: uid(), profileId: app.profile.id, name: m.name.trim(), dose: m.dose.trim(), frequency: m.frequency.trim(), times, start: m.start || undefined, end: m.end || undefined, prescriber: m.prescriber || undefined, refill: m.refill || undefined, notes: m.notes || undefined, supplement: m.supplement, log: {} }]);
            setM(emptyMed); }}>
            <Field label="Name"><input className={inputCls} value={m.name} onChange={(e) => setM({ ...m, name: e.target.value })} required /></Field>
            <Field label="Prescribed dose"><input className={inputCls} value={m.dose} onChange={(e) => setM({ ...m, dose: e.target.value })} /></Field>
            <Field label="Frequency (as prescribed)"><input className={inputCls} value={m.frequency} onChange={(e) => setM({ ...m, frequency: e.target.value })} /></Field>
            <Field label="Reminder times" hint={timesOk ? "24-hour, comma-separated" : "Use HH:MM, e.g. 08:00, 20:00"}><input className={inputCls} value={m.times} onChange={(e) => setM({ ...m, times: e.target.value })} aria-invalid={!timesOk} /></Field>
            <Field label="Start date"><input type="date" className={inputCls} value={m.start} onChange={(e) => setM({ ...m, start: e.target.value })} /></Field>
            <Field label="End date (optional)"><input type="date" className={inputCls} value={m.end} onChange={(e) => setM({ ...m, end: e.target.value })} /></Field>
            <Field label="Prescribing clinician"><input className={inputCls} value={m.prescriber} onChange={(e) => setM({ ...m, prescriber: e.target.value })} /></Field>
            <Field label="Refill date"><input type="date" className={inputCls} value={m.refill} onChange={(e) => setM({ ...m, refill: e.target.value })} /></Field>
            <Field label="Notes"><input className={inputCls} value={m.notes} onChange={(e) => setM({ ...m, notes: e.target.value })} /></Field>
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={m.supplement} onChange={(e) => setM({ ...m, supplement: e.target.checked })} /> Supplement</label>
            <div className="col-span-2"><Button type="submit" variant="primary" disabled={!m.name.trim() || !timesOk}><Plus size={16} /> Add</Button></div>
          </form>
        </Card>

        <Card title={<span className="flex items-center gap-2"><Stethoscope size={18} className="text-primary" /> Check-ups & appointments</span>}>
          {checkups.length === 0 ? <p className="text-sm text-muted">Record your last check-ups and upcoming appointments. Muse only reminds you about dates you enter.</p> : (
            <ul className="divide-y divide-line">{[...checkups].sort((a, b) => (a.next ?? "9").localeCompare(b.next ?? "9")).map((x) => { const s = checkupState(x); const d = x.next ? daysUntil(x.next) : 0; return (
              <li key={x.id} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex-1"><b className="font-medium">{x.kind}</b><br /><span className="text-xs text-muted">{x.next ? `Next ${new Date(x.next).toLocaleDateString()}` : "No date set"}{x.last ? ` · last ${new Date(x.last).toLocaleDateString()}` : ""}{x.repeatMonths ? ` · every ${x.repeatMonths} months (${x.source})` : ""}</span></span>
                  {s !== "none" && <Badge tone={s === "overdue" ? "danger" : s === "soon" ? "warn" : "neutral"}>{s === "overdue" ? "date passed" : d === 0 ? "today" : `in ${d} days`}</Badge>}
                  {x.next && <Button size="sm" onClick={() => setCheckups((cs) => cs.map((y) => (y.id === x.id ? completeCheckup(y) : y)))}><Check size={14} /> Done</Button>}
                  <button aria-label={`Delete ${x.kind}`} className="text-muted hover:text-danger" onClick={() => setCheckups((cs) => cs.filter((y) => y.id !== x.id))}><Trash2 size={15} /></button>
                </div>
                <div className="mt-2 pl-1 text-sm">
                  {x.questions.length > 0 && <ul className="list-disc pl-5 text-muted">{x.questions.map((qq, i) => <li key={i}>{qq}</li>)}</ul>}
                  <form className="mt-1 flex gap-2" onSubmit={(e) => { e.preventDefault(); const t = (q[x.id] ?? "").trim(); if (!t) return; setCheckups((cs) => cs.map((y) => (y.id === x.id ? { ...y, questions: [...y.questions, t] } : y))); setQ({ ...q, [x.id]: "" }); }}>
                    <input aria-label={`Add a question for ${x.kind}`} className={inputCls + " !py-1"} placeholder="Add a question for your clinician" value={q[x.id] ?? ""} onChange={(e) => setQ({ ...q, [x.id]: e.target.value })} />
                    <Button size="sm" type="submit">Add</Button></form>
                </div>
              </li>); })}</ul>)}
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault();
            setCheckups((cs) => [...cs, { id: uid(), profileId: app.profile.id, kind: c.kind, next: c.next || undefined, last: c.last || undefined, repeatMonths: c.repeatMonths ? Number(c.repeatMonths) : undefined, source: c.repeatMonths ? c.source : undefined, notes: c.notes || undefined, questions: [] }]);
            setC({ ...c, next: "", last: "", repeatMonths: "", notes: "" }); }}>
            <Field label="Type"><select className={inputCls} value={c.kind} onChange={(e) => setC({ ...c, kind: e.target.value })}>{CHECKUP_KINDS.map((k) => <option key={k}>{k}</option>)}</select></Field>
            <Field label="Next appointment"><input type="date" className={inputCls} value={c.next} onChange={(e) => setC({ ...c, next: e.target.value })} /></Field>
            <Field label="Last done"><input type="date" className={inputCls} value={c.last} onChange={(e) => setC({ ...c, last: e.target.value })} /></Field>
            <Field label="Repeat every (months)" hint="Only if your clinician or guideline says so"><input type="number" min={1} className={inputCls} value={c.repeatMonths} onChange={(e) => setC({ ...c, repeatMonths: e.target.value })} /></Field>
            <div className="col-span-2"><Button type="submit" variant="primary"><Plus size={16} /> Add check-up</Button></div>
          </form>
        </Card>
      </div>
    </div>
  );
}
