// Pure reminder logic (tested). Medication and check-up schedules for the demo; times are local.
import { addDays, dayKey } from "../../lib/storage";

export interface Medication { id: string; profileId: string; name: string; dose: string; times: string[]; notes?: string; taken: Record<string, string[]> } // taken[dayKey] = times taken
export interface Checkup { id: string; profileId: string; kind: string; due: string; repeatMonths: number; notes?: string; done?: string }

export const CHECKUP_KINDS = [
  { kind: "Cervical screening", repeatMonths: 36 }, { kind: "Mammogram", repeatMonths: 24 }, { kind: "Bone density (DEXA)", repeatMonths: 24 },
  { kind: "Blood tests (cholesterol, HbA1c)", repeatMonths: 12 }, { kind: "Blood pressure check", repeatMonths: 12 }, { kind: "Thyroid check", repeatMonths: 12 },
  { kind: "Eye test", repeatMonths: 24 }, { kind: "Dental check-up", repeatMonths: 6 }, { kind: "Menopause review with clinician", repeatMonths: 12 },
];

const mins = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };

/** Doses due today, with status. "due" = time has passed and not taken; "upcoming" = later today. */
export function doseStatus(meds: Medication[], now = new Date()) {
  const dk = dayKey(now), nowM = now.getHours() * 60 + now.getMinutes();
  return meds.flatMap((m) => m.times.map((t) => ({
    med: m, time: t,
    status: (m.taken[dk] ?? []).includes(t) ? "taken" as const : mins(t) <= nowM ? "due" as const : "upcoming" as const,
  }))).sort((a, b) => mins(a.time) - mins(b.time));
}

export function daysUntil(date: string, now = new Date()) {
  return Math.round((new Date(date + "T00:00:00").getTime() - new Date(dayKey(now) + "T00:00:00").getTime()) / 86400000);
}

export function checkupState(c: Checkup, now = new Date()): "overdue" | "soon" | "later" {
  const d = daysUntil(c.due, now);
  return d < 0 ? "overdue" : d <= 30 ? "soon" : "later";
}

/** Mark done: next due date moves forward by the repeat interval. */
export function completeCheckup(c: Checkup, now = new Date()): Checkup {
  const next = new Date(now); next.setMonth(next.getMonth() + c.repeatMonths);
  return { ...c, done: dayKey(now), due: dayKey(next) };
}

/** Fictional starter reminders per demo persona. */
export function seedReminders(profileId: string, today = new Date()): { meds: Medication[]; checkups: Checkup[] } {
  const mk = (name: string, dose: string, times: string[]): Medication => ({ id: `${profileId}-${name}`, profileId, name, dose, times, taken: {} });
  const ck = (kind: string, inDays: number, repeatMonths: number): Checkup => ({ id: `${profileId}-${kind}`, profileId, kind, due: dayKey(addDays(today, inDays)), repeatMonths });
  return profileId === "nancy"
    ? { meds: [mk("Vitamin D", "1000 IU", ["09:00"]), mk("Calcium", "500 mg", ["13:00", "20:00"])], checkups: [ck("Bone density (DEXA)", 12, 24), ck("Mammogram", -3, 24), ck("Blood tests (cholesterol, HbA1c)", 60, 12)] }
    : { meds: [mk("Iron", "14 mg", ["08:00"]), mk("Magnesium", "200 mg", ["21:30"])], checkups: [ck("Cervical screening", 20, 36), ck("Dental check-up", 45, 6), ck("Blood pressure check", 90, 12)] };
}
