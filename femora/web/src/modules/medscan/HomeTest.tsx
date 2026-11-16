import { useEffect, useState } from "react";
import { FlaskConical, Home } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { Badge, Button, Card, StatusBadge, inputCls } from "../../components/ui";
import { HOME_TESTS, STAGES, resultsDate } from "./logic";

/** Book a home sample collection and follow it to results in ~2–3 days. Demo: stages advance every few seconds. */
export function HomeTest({ onResults }: { onResults: () => void }) {
  const app = useApp();
  const [test, setTest] = useState(HOME_TESTS[0].id);
  const [slot, setSlot] = useState("Tomorrow, 8–10 am");
  const [stage, setStage] = useState(-1);
  const t = HOME_TESTS.find((x) => x.id === test)!;

  useEffect(() => {
    if (stage < 0 || stage >= STAGES.length - 1) return;
    const id = setTimeout(() => {
      const next = stage + 1;
      setStage(next);
      app.notify(`${t.name}: ${STAGES[next]}`, next === STAGES.length - 1 ? "Your results are ready to view in MedScan (demo)." : "We'll update you at the next step (demo).", "/app/medscan");
      if (next === STAGES.length - 1) onResults();
    }, 2500);
    return () => clearTimeout(id);
  }, [stage, app, t.name, onResults]);

  return (
    <Card title={<span className="flex items-center gap-2"><Home size={18} className="text-primary" /> Home sample collection: results in 2–3 days</span>} actions={<StatusBadge status="simulated" />}>
      {stage < 0 ? (
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">{HOME_TESTS.map((x) => (
            <button key={x.id} aria-pressed={test === x.id} onClick={() => setTest(x.id)} className={`rounded-f-sm border p-3 text-left text-sm ${test === x.id ? "border-primary ring-2 ring-primary/30" : "border-line hover:bg-surface-2"}`}>
              <FlaskConical size={16} className="text-primary" /><div className="font-medium">{x.name}</div><div className="text-xs text-muted">{x.includes}</div><div className="mt-1"><Badge tone="good">Results ~{x.days} days</Badge></div></button>))}</div>
          <label className="block text-sm">Collection slot
            <select className={inputCls} value={slot} onChange={(e) => setSlot(e.target.value)}>{["Tomorrow, 8–10 am", "Tomorrow, 5–7 pm", "In 2 days, 8–10 am", "Send me a self-collection kit"].map((s) => <option key={s}>{s}</option>)}</select></label>
          <Button variant="primary" onClick={() => { setStage(0); app.notify(`${t.name} booked`, `${slot}. Expected results by ${resultsDate(new Date(), t.days + 1).toLocaleDateString()} (demo).`, "/app/medscan"); }}>Book home collection</Button>
          <p className="text-xs text-muted">Demo booking: no real appointment is made. Production will partner with accredited labs and include pricing and free eligibility.</p>
        </div>
      ) : (
        <div>
          <p className="text-sm"><b>{t.name}</b> · {slot} · expected by <b>{resultsDate(new Date(), t.days + 1).toLocaleDateString()}</b></p>
          <ol className="mt-3 flex items-center gap-2" aria-label="Test progress">{STAGES.map((s, i) => (
            <li key={s} className="flex flex-1 flex-col items-center gap-1 text-center text-xs">
              <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-semibold ${i <= stage ? "bg-primary text-primary-ink" : "bg-surface-2 text-muted"}`}>{i + 1}</span>{s}</li>))}</ol>
          <p className="mt-3 text-xs text-muted">Demo time is sped up: each step takes a few seconds here instead of hours.</p>
        </div>)}
    </Card>
  );
}
