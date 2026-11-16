// Proactive Muse: suggestions derived ONLY from the user's own records and approved settings. Deterministic.
import type { Checkup, Medication } from "../reminders/logic";
import { checkupState, daysUntil, doseStatus } from "../reminders/logic";

export interface Suggestion { id: string; text: string; action?: { label: string; to: string } }

export function greeting(name: string, now = new Date()) {
  const h = now.getHours();
  return `${h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"}, ${name}.`;
}

const weekday = (d: string) => new Date(d + "T12:00:00").toLocaleDateString(undefined, { weekday: "long" });

export function suggestions(input: { name: string; city?: string; meds: Medication[]; checkups: Checkup[]; interests: string[]; hasFoodToday: boolean; privateMedication: boolean }, now = new Date()): Suggestion[] {
  const out: Suggestion[] = [];
  const upcoming = input.checkups.filter((c) => checkupState(c, now) === "soon").sort((a, b) => a.next!.localeCompare(b.next!));
  for (const c of upcoming.slice(0, 2)) {
    const d = daysUntil(c.next!, now);
    const when = d === 0 ? "today" : d === 1 ? "tomorrow" : `on ${weekday(c.next!)}`;
    out.push({ id: `ck-${c.id}`, text: `${input.name}, you have a ${c.kind.toLowerCase()} ${when}.${c.questions.length ? " Would you like to review the questions you saved for your clinician?" : " Would you like to note some questions for your clinician?"}`, action: { label: "Review", to: "/app/reminders" } });
  }
  const overdue = input.checkups.filter((c) => checkupState(c, now) === "overdue");
  if (overdue.length) out.push({ id: "ck-overdue", text: `The date for your ${overdue[0].kind.toLowerCase()} has passed. Would you like to mark it done or reschedule?`, action: { label: "Update", to: "/app/reminders" } });
  const due = doseStatus(input.meds, now).filter((d) => d.status === "due");
  if (due.length) out.push({ id: "meds-due", text: input.privateMedication ? `You have ${due.length} scheduled reminder${due.length > 1 ? "s" : ""} waiting.` : `It's time for ${due.map((d) => d.med.name).join(", ")}.`, action: { label: "Open", to: "/app/reminders" } });
  if (!input.meds.length && !input.checkups.length) out.push({ id: "setup-planner", text: "Would you like help setting up reminders for medication or upcoming check-ups?", action: { label: "Set up", to: "/app/reminders" } });
  out.push(input.city
    ? { id: "discover", text: `I can check for verified women's health events and wellness activities around ${input.city}.`, action: { label: "Check", to: "/app/free-care" } }
    : { id: "city", text: "Tell me your city, and I can look for verified health events and wellness activities near you.", action: { label: "Add city", to: "/app/settings" } });
  if (!input.hasFoodToday) out.push({ id: "food", text: "Would you like to log today's meals? It only takes a sentence.", action: { label: "Log food", to: "/app/food" } });
  if (!input.interests.length) out.push({ id: "interests", text: "What would you like Muse to help with? Choose a few interests so suggestions fit you.", action: { label: "Choose", to: "/app/settings" } });
  return out;
}
