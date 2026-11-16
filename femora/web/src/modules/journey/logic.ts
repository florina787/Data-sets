// Menopause Journey: deterministic cycle maths and educational stage hints. Never a diagnosis, never a prediction
// of the final period. Staging language follows STRAW+10 (Harlow et al., 2012) and is shown with uncertainty.
export type Flow = "spotting" | "light" | "medium" | "heavy";
export interface Period { id: string; start: string; end?: string; flow: Flow; pain?: 0 | 1 | 2 | 3; note?: string }
export interface Ovulation { id: string; date: string; kind: "LH test positive" | "LH test negative" | "Basal temperature" | "Cervical mucus" | "Clinician result"; value?: string }
export type Confounder = "hormonal contraception" | "hysterectomy" | "ovaries removed" | "pregnant or breastfeeding" | "cancer treatment" | "other medical cause";

export const SYMPTOMS = ["Hot flash", "Night sweats", "Sleep disruption", "Mood changes", "Anxiety", "Brain fog", "Joint pain", "Fatigue", "Headache", "Palpitations", "Vaginal dryness", "Urinary symptoms", "Low libido", "Energy change"];

const day = 86400000;
const t = (d: string) => new Date(d + "T00:00:00").getTime();
export const daysBetween = (a: string, b: string) => Math.round((t(b) - t(a)) / day);

/** Start-to-start cycle lengths, oldest first. */
export function cycleLengths(periods: Period[]): { start: string; length: number }[] {
  const s = [...periods].sort((a, b) => a.start.localeCompare(b.start));
  return s.slice(1).map((p, i) => ({ start: s[i].start, length: daysBetween(s[i].start, p.start) }));
}

export function periodLength(p: Period) { return p.end ? daysBetween(p.start, p.end) + 1 : undefined; }

export function cycleStats(periods: Period[]) {
  const L = cycleLengths(periods).map((c) => c.length);
  if (!L.length) return null;
  const mean = L.reduce((a, b) => a + b, 0) / L.length;
  const consecutiveDiffs = L.slice(1).map((x, i) => Math.abs(x - L[i]));
  return { count: L.length, mean: Math.round(mean), min: Math.min(...L), max: Math.max(...L), maxConsecutiveDiff: consecutiveDiffs.length ? Math.max(...consecutiveDiffs) : 0, longestGap: Math.max(...L) };
}

export interface StageHint { key: "not-applicable" | "insufficient" | "regular" | "early-transition" | "late-transition" | "twelve-months"; title: string; text: string }

/**
 * Educational interpretation only. Rules from STRAW+10:
 *  - early transition: persistent ≥7-day difference in length of consecutive cycles
 *  - late transition: interval of amenorrhea ≥60 days
 *  - final menstrual period recognised only retrospectively after 12 months without bleeding
 */
export function stageHint(periods: Period[], confounders: Confounder[], today = new Date()): StageHint {
  if (confounders.length) return { key: "not-applicable", title: "Cycle-based staging doesn't apply", text: `Because of ${confounders.join(", ")}, bleeding patterns can't reliably show your stage. Symptoms and a clinician's assessment matter more.` };
  const sorted = [...periods].sort((a, b) => a.start.localeCompare(b.start));
  const last = sorted[sorted.length - 1];
  const todayKey = today.toISOString().slice(0, 10);
  if (last && daysBetween(last.start, todayKey) >= 365) return { key: "twelve-months", title: "12 months since your last recorded period", text: "Menopause is usually recognised looking back, after 12 months without a period and with no other cause. Please confirm with a clinician, especially before stopping contraception. Any bleeding after this point should be checked promptly." };
  const L = cycleLengths(sorted).map((c) => c.length);
  const sinceLast = last ? daysBetween(last.start, todayKey) : 0;
  if (L.some((x) => x >= 60) || sinceLast >= 60) return { key: "late-transition", title: "A gap of 60 days or more", text: "In the STRAW+10 framework, gaps of 60+ days are a feature of the late menopausal transition. Other causes are possible, so this is a pattern to discuss, not a diagnosis." };
  if (L.length < 3) return { key: "insufficient", title: "Keep logging", text: "A few more cycles are needed before any pattern can be described. Log each period's first day." };
  const persistent = L.slice(1).filter((x, i) => Math.abs(x - L[i]) >= 7).length >= 2;
  if (persistent) return { key: "early-transition", title: "Cycle lengths vary by 7+ days", text: "Persistent differences of 7 days or more between consecutive cycles are described in STRAW+10 as a sign of the early menopausal transition. Stress, illness, thyroid conditions and other factors can also change cycles." };
  return { key: "regular", title: "Your cycles look fairly steady", text: "Your recorded cycles don't show the variability patterns used to describe the menopausal transition. That can change; keep logging." };
}

export interface SymptomLike { name: string; severity: number; at: number }

/** Weekly counts per symptom for the last n weeks (oldest first). */
export function weeklySymptoms(entries: SymptomLike[], weeks: number, now = new Date()) {
  const end = new Date(now); end.setHours(23, 59, 59, 999);
  return Array.from({ length: weeks }, (_, i) => {
    const to = end.getTime() - (weeks - 1 - i) * 7 * day, from = to - 7 * day;
    const inW = entries.filter((e) => e.at > from && e.at <= to);
    const counts: Record<string, number> = {};
    inW.forEach((e) => { counts[e.name] = (counts[e.name] ?? 0) + 1; });
    const label = new Date(from + day).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    return { week: label, total: inW.length, avgSeverity: inW.length ? Math.round((inW.reduce((a, e) => a + e.severity, 0) / inW.length) * 10) / 10 : 0, ...counts };
  });
}

export function topSymptoms(entries: SymptomLike[], since: number) {
  const c: Record<string, number> = {};
  entries.filter((e) => e.at >= since).forEach((e) => { c[e.name] = (c[e.name] ?? 0) + 1; });
  return Object.entries(c).sort((a, b) => b[1] - a[1]);
}

/** Facts the copilot may quote about cycles and symptoms. */
export function journeyFacts(periods: Period[], symptoms: SymptomLike[], now = new Date()) {
  const sorted = [...periods].sort((a, b) => a.start.localeCompare(b.start));
  const last = sorted[sorted.length - 1];
  const st = cycleStats(sorted);
  const top = topSymptoms(symptoms, now.getTime() - 14 * day).slice(0, 3);
  return { lastPeriod: last?.start, daysSinceLast: last ? daysBetween(last.start, now.toISOString().slice(0, 10)) : undefined, avgCycle: st?.mean, cyclesLogged: st?.count ?? 0, topSymptoms14d: top };
}

export function doctorSummary(name: string, periods: Period[], symptoms: (SymptomLike & { impact?: number; note?: string })[], ovulation: Ovulation[], confounders: Confounder[], hint: StageHint) {
  const st = cycleStats(periods);
  const lines = [`Menopause journey summary for ${name}, prepared ${new Date().toLocaleDateString()} from self-recorded data`, "",
    "CYCLES", ...[...periods].sort((a, b) => b.start.localeCompare(a.start)).slice(0, 12).map((p) => `- ${p.start}${p.end ? ` to ${p.end}` : ""}, flow ${p.flow}${p.pain ? `, pain ${p.pain}/3` : ""}${p.note ? ` (${p.note})` : ""}`),
    st ? `Cycle length: average ${st.mean} days (range ${st.min}–${st.max}, ${st.count} cycles); largest change between consecutive cycles ${st.maxConsecutiveDiff} days.` : "Not enough cycles for statistics.",
    `Relevant factors: ${confounders.length ? confounders.join(", ") : "none recorded"}.`, `Pattern note (educational, not a diagnosis): ${hint.title}.`, "",
    "SYMPTOMS (last 90 days)", ...topSymptoms(symptoms, Date.now() - 90 * day).map(([n, c]) => `- ${n}: ${c} entries`), "",
    ...(ovulation.length ? ["OVULATION OBSERVATIONS", ...ovulation.slice(-10).map((o) => `- ${o.date}: ${o.kind}${o.value ? ` (${o.value})` : ""}`), ""] : []),
    "Questions I'd like to discuss:", "- ", "", "Self-recorded information; not a clinical record."];
  return lines.join("\n");
}
