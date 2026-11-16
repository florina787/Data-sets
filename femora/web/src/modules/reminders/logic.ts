// Deterministic medication and check-up scheduling. No model ever sets or changes times, doses or intervals.
import { dayKey } from "../../lib/storage";

export type DoseEvent = "taken" | "skipped" | "snoozed";
export interface Medication {
  id: string; profileId: string; name: string; dose: string; frequency: string; times: string[];
  start?: string; end?: string; prescriber?: string; refill?: string; pharmacy?: string; notes?: string; supplement?: boolean;
  log: Record<string, Record<string, { event: DoseEvent; at: number; until?: number }>>; // log[day][time]
}
export interface Checkup {
  id: string; profileId: string; kind: string; next?: string; last?: string;
  repeatMonths?: number;          // only if she or her clinician sets it; never defaulted
  source?: "self" | "clinician" | "guideline"; notes?: string; questions: string[]; done?: boolean;
}

export const CHECKUP_KINDS = ["Cervical screening", "Breast screening", "General health check-up", "Dental appointment", "Eye examination", "Bone density test", "Blood pressure check", "Blood glucose / HbA1c", "Lipid test", "Thyroid test", "Clinician follow-up", "Other"];

const mins = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
export const validTime = (t: string) => /^([01]\d|2[0-3]):[0-5]\d$/.test(t);

export function activeOn(m: Medication, d: Date) {
  const k = dayKey(d);
  return (!m.start || m.start <= k) && (!m.end || m.end >= k);
}

/** Today's doses: taken / skipped / snoozed / due / upcoming. */
export function doseStatus(meds: Medication[], now = new Date()) {
  const dk = dayKey(now), nowM = now.getHours() * 60 + now.getMinutes();
  return meds.filter((m) => activeOn(m, now)).flatMap((m) => m.times.map((t) => {
    const e = m.log[dk]?.[t];
    const status = e?.event === "taken" ? "taken" : e?.event === "skipped" ? "skipped"
      : e?.event === "snoozed" && (e.until ?? 0) > now.getTime() ? "snoozed" : mins(t) <= nowM ? "due" : "upcoming";
    return { med: m, time: t, status: status as "taken" | "skipped" | "snoozed" | "due" | "upcoming" };
  })).sort((a, b) => mins(a.time) - mins(b.time));
}

export function record(m: Medication, time: string, event: DoseEvent, now = new Date(), snoozeMin = 15): Medication {
  const dk = dayKey(now);
  return { ...m, log: { ...m.log, [dk]: { ...m.log[dk], [time]: { event, at: now.getTime(), ...(event === "snoozed" ? { until: now.getTime() + snoozeMin * 60000 } : {}) } } } };
}

/** Adherence over the last n days, counting only scheduled doses. */
export function adherence(m: Medication, days: number, now = new Date()) {
  let scheduled = 0, taken = 0;
  for (let i = 1; i <= days; i++) {
    const d = new Date(now); d.setDate(d.getDate() - i);
    if (!activeOn(m, d)) continue;
    scheduled += m.times.length;
    taken += Object.values(m.log[dayKey(d)] ?? {}).filter((e) => e.event === "taken").length;
  }
  return scheduled ? Math.round((taken / scheduled) * 100) : null;
}

export function daysUntil(date: string, now = new Date()) {
  return Math.round((new Date(date + "T00:00:00").getTime() - new Date(dayKey(now) + "T00:00:00").getTime()) / 86400000);
}
export function checkupState(c: Checkup, now = new Date()): "none" | "overdue" | "soon" | "later" {
  if (!c.next || c.done) return "none";
  const d = daysUntil(c.next, now);
  return d < 0 ? "overdue" : d <= 14 ? "soon" : "later";
}

/** Mark done: next date moves only if a repeat interval was explicitly set. */
export function completeCheckup(c: Checkup, now = new Date()): Checkup {
  if (!c.repeatMonths) return { ...c, last: dayKey(now), next: undefined, done: true };
  const next = new Date(now); next.setMonth(next.getMonth() + c.repeatMonths);
  return { ...c, last: dayKey(now), next: dayKey(next), done: false };
}

export const refillSoon = (m: Medication, now = new Date()) => !!m.refill && daysUntil(m.refill, now) <= 5;
