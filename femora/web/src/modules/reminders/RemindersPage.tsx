import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, Pill, Plus, Stethoscope, Trash2 } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { dayKey, uid } from "../../lib/storage";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../../components/ui";
import { CHECKUP_KINDS, checkupState, completeCheckup, daysUntil, doseStatus } from "./logic";
import { useReminders } from "./useReminders";

export function RemindersPage() {
  const app = useApp();
  const { meds, setMeds, checkups, setCheckups } = useReminders();
  const [m, setM] = useState({ name: "", dose: "", times: "08:00" });
  const [c, setC] = useState({ kind: CHECKUP_KINDS[0].kind, due: dayKey(new Date()) });
  const doses = doseStatus(meds);
  const dk = dayKey(new Date());

  const take = (id: string, time: string) => setMeds((ms) => ms.map((x) => x.id === id ? { ...x, taken: { ...x.taken, [dk]: [...(x.taken[dk] ?? []), time] } } : x));

  return (
    <div>
      <PageHeader title="Medication & check-up reminders" status="demonstrated"
        sub="Never miss a dose or a screening. Reminders appear under the bell and as browser notifications while FEMORA is open." />
      <Notice tone="neutral">Starter reminders for {app.profile.name} are fictional. FEMORA reminds you; it doesn't give medication advice. Always follow your prescriber's instructions.</Notice>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><Pill size={18} className="text-primary" /> Today's medication</span>}>
          {doses.length === 0 ? <p className="text-sm text-muted">No medication added.</p> : (
            <ul className="divide-y divide-line">{doses.map((d) => (
              <li key={d.med.id + d.time} className="flex items-center gap-3 py-2.5">
                <span className="w-14 font-medium">{d.time}</span>
                <span className="flex-1"><b className="font-medium">{d.med.name}</b> <span className="text-sm text-muted">{d.med.dose}</span></span>
                {d.status === "taken" ? <Badge tone="good">Taken</Badge> : <>
                  {d.status === "due" && <Badge tone="warn">Due</Badge>}
                  <Button size="sm" variant={d.status === "due" ? "primary" : "secondary"} onClick={() => take(d.med.id, d.time)}><Check size={14} /> Taken</Button></>}
              </li>))}</ul>)}
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); if (!m.name.trim()) return;
            setMeds((ms) => [...ms, { id: uid(), profileId: app.profile.id, name: m.name.trim(), dose: m.dose.trim(), times: m.times.split(",").map((t) => t.trim()).filter((t) => /^\d{2}:\d{2}$/.test(t)), taken: {} }]);
            setM({ name: "", dose: "", times: "08:00" }); }}>
            <Field label="Medicine or supplement"><input className={inputCls} value={m.name} onChange={(e) => setM({ ...m, name: e.target.value })} placeholder="e.g. HRT patch" /></Field>
            <Field label="Dose"><input className={inputCls} value={m.dose} onChange={(e) => setM({ ...m, dose: e.target.value })} placeholder="e.g. 50 mcg" /></Field>
            <Field label="Times" hint="24-hour, comma-separated"><input className={inputCls} value={m.times} onChange={(e) => setM({ ...m, times: e.target.value })} placeholder="08:00, 20:00" /></Field>
            <div className="flex items-end"><Button type="submit" variant="primary" className="w-full"><Plus size={16} /> Add medication</Button></div>
          </form>
          {meds.length > 0 && <details className="mt-3 text-sm"><summary className="cursor-pointer text-primary">Manage medication</summary>
            <ul className="mt-2 space-y-1">{meds.map((x) => <li key={x.id} className="flex items-center justify-between">{x.name} {x.dose} · {x.times.join(", ")}<button aria-label={`Remove ${x.name}`} className="text-muted hover:text-danger" onClick={() => setMeds((ms) => ms.filter((y) => y.id !== x.id))}><Trash2 size={15} /></button></li>)}</ul></details>}
        </Card>

        <Card title={<span className="flex items-center gap-2"><Stethoscope size={18} className="text-primary" /> Health check-ups</span>}>
          <ul className="divide-y divide-line">{[...checkups].sort((a, b) => a.due.localeCompare(b.due)).map((x) => { const s = checkupState(x); const d = daysUntil(x.due); return (
            <li key={x.id} className="flex items-center gap-3 py-2.5">
              <span className="flex-1"><b className="font-medium">{x.kind}</b><br /><span className="text-xs text-muted">Due {new Date(x.due).toLocaleDateString()} · every {x.repeatMonths} months{x.done ? ` · last done ${new Date(x.done).toLocaleDateString()}` : ""}</span></span>
              <Badge tone={s === "overdue" ? "danger" : s === "soon" ? "warn" : "neutral"}>{s === "overdue" ? `${-d} days overdue` : d === 0 ? "Today" : `in ${d} days`}</Badge>
              <Button size="sm" onClick={() => setCheckups((cs) => cs.map((y) => y.id === x.id ? completeCheckup(y) : y))}><Check size={14} /> Done</Button>
              <button aria-label={`Remove ${x.kind}`} className="text-muted hover:text-danger" onClick={() => setCheckups((cs) => cs.filter((y) => y.id !== x.id))}><Trash2 size={15} /></button>
            </li>); })}</ul>
          <form className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault();
            const rep = CHECKUP_KINDS.find((k) => k.kind === c.kind)?.repeatMonths ?? 12;
            setCheckups((cs) => [...cs, { id: uid(), profileId: app.profile.id, kind: c.kind, due: c.due, repeatMonths: rep }]); }}>
            <Field label="Check-up"><select className={inputCls} value={c.kind} onChange={(e) => setC({ ...c, kind: e.target.value })}>{CHECKUP_KINDS.map((k) => <option key={k.kind}>{k.kind}</option>)}</select></Field>
            <Field label="Due date"><input type="date" className={inputCls} value={c.due} onChange={(e) => setC({ ...c, due: e.target.value })} /></Field>
            <div className="col-span-2"><Button type="submit" variant="primary"><Plus size={16} /> Add check-up reminder</Button></div>
          </form>
          <p className="mt-3 text-sm">Looking for a free check-up? <Link className="text-primary underline" to="/app/free-care">See free care & events near you</Link></p>
          <p className="mt-1 text-xs text-muted">Typical intervals are defaults only. Screening schedules vary by country and personal history.</p>
        </Card>
      </div>
    </div>
  );
}
