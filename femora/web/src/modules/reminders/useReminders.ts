import { useEffect } from "react";
import { useApp } from "../../lib/app-state";
import { usePersistent } from "../../lib/usePersistent";
import { dayKey } from "../../lib/storage";
import { checkupState, daysUntil, doseStatus, refillSoon, type Checkup, type Medication } from "./logic";

export function useReminders() {
  const { profile } = useApp();
  const [meds, setMeds] = usePersistent<Medication[]>(`meds2:${profile.id}`, () => []);
  const [checkups, setCheckups] = usePersistent<Checkup[]>(`checkups2:${profile.id}`, () => []);
  return { meds, setMeds, checkups, setCheckups };
}

/** Runs in the app shell. Only her own records generate reminders. The engine applies quiet hours, limits and privacy. */
export function ReminderWatcher() {
  const app = useApp();
  const { meds, checkups } = useReminders();
  useEffect(() => {
    const tick = () => {
      const dk = dayKey(new Date());
      for (const d of doseStatus(meds)) if (d.status === "due")
        app.notify({ key: `${dk}-${d.med.id}-${d.time}`, category: "health", priority: "high", link: "/app/reminders",
          title: `Time for ${d.med.name}`, body: `${d.med.dose} · scheduled ${d.time}`,
          sensitive: { title: "Reminder from Muse", body: `You have a scheduled reminder for ${d.time}.` } });
      for (const m of meds) if (refillSoon(m))
        app.notify({ key: `${dk}-refill-${m.id}`, category: "health", priority: "normal", link: "/app/reminders",
          title: `Refill ${m.name} soon`, body: `Refill date ${new Date(m.refill!).toLocaleDateString()}`, sensitive: { title: "Refill reminder", body: "A refill is coming up." } });
      for (const c of checkups) { const s = checkupState(c); if (s === "overdue" || s === "soon") {
        const d = daysUntil(c.next!);
        app.notify({ key: `${dk}-${c.id}`, category: "health", priority: "normal", link: "/app/reminders",
          title: d === 0 ? `${c.kind} today` : s === "overdue" ? `${c.kind} date has passed` : `${c.kind} in ${d} days`,
          body: c.questions.length ? `You saved ${c.questions.length} question${c.questions.length > 1 ? "s" : ""} for your clinician. Want to review them?` : "Would you like to add questions or a preparation checklist?",
          sensitive: { title: "Upcoming appointment", body: "You have a health appointment coming up." } }); } }
    };
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [meds, checkups, app]);
  return null;
}
