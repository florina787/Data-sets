import { useEffect, useRef } from "react";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { dayKey } from "../../lib/storage";
import { checkupState, doseStatus, seedReminders, type Checkup, type Medication } from "./logic";

export function useReminders() {
  const { profile } = useApp();
  const [meds, setMeds] = usePersistent<Medication[]>(`meds:${profile.id}`, () => seedReminders(profile.id).meds);
  const [checkups, setCheckups] = usePersistent<Checkup[]>(`checkups:${profile.id}`, () => seedReminders(profile.id).checkups);
  return { meds, setMeds, checkups, setCheckups };
}

/** Runs in the app shell: raises a notification once per due dose and once a day for check-ups due soon. */
export function ReminderWatcher() {
  const app = useApp();
  const { meds, checkups } = useReminders();
  const sent = useRef<Set<string>>(new Set(JSON.parse(sessionStorage.getItem("femora:sent") ?? "[]")));
  useEffect(() => {
    const tick = () => {
      const dk = dayKey(new Date());
      const fire = (key: string, title: string, body: string) => {
        if (sent.current.has(key)) return;
        sent.current.add(key); sessionStorage.setItem("femora:sent", JSON.stringify([...sent.current]));
        app.notify(title, body, "/app/reminders");
      };
      for (const d of doseStatus(meds)) if (d.status === "due") fire(`${dk}-${d.med.id}-${d.time}`, `Time for ${d.med.name}`, `${d.med.dose} · scheduled ${d.time}. Tap to mark as taken.`);
      for (const c of checkups) { const s = checkupState(c); if (s !== "later") fire(`${dk}-${c.id}`, s === "overdue" ? `${c.kind} is overdue` : `${c.kind} due soon`, `Due ${new Date(c.due).toLocaleDateString()}. Book an appointment or find a free check-up near you.`); }
    };
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [meds, checkups, app]);
  return null;
}
