// Whole-body health records: user-entered only. Deterministic summaries; guideline ranges are explained, never scored.
export type MetricId = "weight" | "waist" | "bp" | "glucose" | "hba1c" | "sleep" | "steps" | "exercise" | "joint" | "brainfog" | "mood" | "skin" | "hair" | "nails";
export interface Metric { id: MetricId; label: string; unit: string; group: "Metabolic" | "Heart" | "Movement & sleep" | "Mind" | "Body"; min: number; max: number; step: number; scale?: string[]; help: string; locations?: string[] }

const SEV = ["None", "Mild", "Moderate", "Severe"];
export const METRICS: Metric[] = [
  { id: "weight", label: "Weight", unit: "kg", group: "Metabolic", min: 20, max: 300, step: 0.1, help: "Weigh at the same time of day for comparable readings." },
  { id: "waist", label: "Waist", unit: "cm", group: "Metabolic", min: 40, max: 200, step: 0.5, help: "Measure at the level of your navel, breathing out." },
  { id: "bp", label: "Blood pressure", unit: "mmHg", group: "Heart", min: 60, max: 260, step: 1, help: "Sit quietly for 5 minutes first; record systolic / diastolic." },
  { id: "glucose", label: "Blood glucose", unit: "mg/dL", group: "Metabolic", min: 20, max: 600, step: 1, help: "Note whether fasting or after a meal." },
  { id: "hba1c", label: "HbA1c", unit: "%", group: "Metabolic", min: 3, max: 15, step: 0.1, help: "From your lab report." },
  { id: "sleep", label: "Sleep", unit: "hours", group: "Movement & sleep", min: 0, max: 16, step: 0.25, help: "Total hours slept." },
  { id: "steps", label: "Steps", unit: "steps", group: "Movement & sleep", min: 0, max: 100000, step: 100, help: "From your phone or watch." },
  { id: "exercise", label: "Exercise", unit: "min", group: "Movement & sleep", min: 0, max: 600, step: 5, help: "Strength, yoga, walking, swimming…" },
  { id: "joint", label: "Joint & hip pain", unit: "0–3", group: "Body", min: 0, max: 3, step: 1, scale: SEV, help: "Where and how much.", locations: ["Hip", "Knee", "Back", "Shoulder", "Hands", "Feet", "Other"] },
  { id: "brainfog", label: "Brain fog", unit: "0–3", group: "Mind", min: 0, max: 3, step: 1, scale: SEV, help: "Forgetfulness, trouble concentrating." },
  { id: "mood", label: "Mood", unit: "1–5", group: "Mind", min: 1, max: 5, step: 1, scale: ["", "Very low", "Low", "Okay", "Good", "Great"], help: "How you felt overall today." },
  { id: "skin", label: "Skin", unit: "0–3", group: "Body", min: 0, max: 3, step: 1, scale: SEV, help: "Dryness, itching, acne, sensitivity…" },
  { id: "hair", label: "Hair & scalp", unit: "0–3", group: "Body", min: 0, max: 3, step: 1, scale: SEV, help: "Shedding, thinning, dry scalp…" },
  { id: "nails", label: "Nails", unit: "0–3", group: "Body", min: 0, max: 3, step: 1, scale: SEV, help: "Brittleness, splitting, changes…" },
];
export const metric = (id: MetricId) => METRICS.find((m) => m.id === id)!;

export interface BodyRecord { id: string; metric: MetricId; date: string; value: number; value2?: number; location?: string; context?: string; note?: string }

export const RANGES = { "7d": 7, "30d": 30, "90d": 90, "1y": 365, all: 100000 } as const;
export type RangeKey = keyof typeof RANGES;

export function inRange(records: BodyRecord[], id: MetricId, range: RangeKey, today = new Date()) {
  const from = new Date(today); from.setDate(from.getDate() - RANGES[range]);
  const f = from.toISOString().slice(0, 10);
  return records.filter((r) => r.metric === id && r.date >= f).sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
}

export function summary(rs: BodyRecord[]) {
  if (!rs.length) return null;
  const vals = rs.map((r) => r.value);
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  return { count: rs.length, latest: rs[rs.length - 1], first: rs[0], avg: Math.round(avg * 10) / 10, min: Math.min(...vals), max: Math.max(...vals), change: Math.round((rs[rs.length - 1].value - rs[0].value) * 10) / 10 };
}

/** Daily series for charts (multiple same-day entries averaged). */
export function daily(rs: BodyRecord[]) {
  const m = new Map<string, { v: number[]; v2: number[] }>();
  rs.forEach((r) => { const e = m.get(r.date) ?? { v: [], v2: [] }; e.v.push(r.value); if (r.value2 !== undefined) e.v2.push(r.value2); m.set(r.date, e); });
  const avg = (a: number[]) => (a.length ? Math.round((a.reduce((x, y) => x + y, 0) / a.length) * 10) / 10 : undefined);
  return [...m.entries()].sort().map(([date, e]) => ({ date, value: avg(e.v)!, value2: avg(e.v2) }));
}

export interface RangeNote { label: string; tone: "good" | "neutral" | "warn" | "danger"; text: string; urgent?: boolean }

/** Blood pressure categories from the 2017 ACC/AHA guideline. One reading is not a diagnosis. */
export function bpNote(sys: number, dia: number): RangeNote {
  if (sys > 180 || dia > 120) return { label: "Very high reading", tone: "danger", urgent: true, text: "Above 180/120. Rest for a few minutes and measure again. If it stays this high, or you have chest pain, shortness of breath, weakness, vision or speech changes, call your local emergency number now." };
  if (sys >= 140 || dia >= 90) return { label: "Stage 2 range", tone: "warn", text: "In the range the ACC/AHA guideline calls stage 2 high blood pressure. Discuss repeated readings with a clinician." };
  if (sys >= 130 || dia >= 80) return { label: "Stage 1 range", tone: "warn", text: "In the stage 1 range of the ACC/AHA guideline. Several readings over time matter more than one." };
  if (sys >= 120) return { label: "Elevated range", tone: "neutral", text: "Systolic 120–129 with diastolic under 80 is called 'elevated' in the ACC/AHA guideline." };
  return { label: "Normal range", tone: "good", text: "Under 120/80, the ACC/AHA normal range." };
}

/** HbA1c ranges used by the American Diabetes Association. Only a clinician can diagnose. */
export function hba1cNote(v: number): RangeNote {
  if (v >= 6.5) return { label: "ADA diabetes range", tone: "warn", text: "6.5% or above is in the range the ADA uses for diabetes. Diagnosis needs confirmation by a clinician." };
  if (v >= 5.7) return { label: "ADA prediabetes range", tone: "neutral", text: "5.7–6.4% is the range the ADA calls prediabetes. Lifestyle changes can make a real difference." };
  return { label: "Below 5.7%", tone: "good", text: "Below the ADA prediabetes range." };
}

export function glucoseNote(v: number, context?: string): RangeNote | null {
  if (v < 54) return { label: "Very low reading", tone: "danger", urgent: true, text: "Below 54 mg/dL is very low. If you feel shaky, confused or faint, take fast-acting sugar and get help." };
  if (v > 300) return { label: "Very high reading", tone: "danger", urgent: true, text: "Above 300 mg/dL. Contact a clinician promptly, especially if you feel unwell." };
  if (context === "fasting") return v >= 126 ? { label: "High fasting reading", tone: "warn", text: "126 mg/dL or more fasting is above the ADA threshold; repeated readings should be reviewed by a clinician." } : v >= 100 ? { label: "Fasting 100–125", tone: "neutral", text: "The ADA calls fasting 100–125 mg/dL impaired fasting glucose." } : { label: "Fasting under 100", tone: "good", text: "Under 100 mg/dL fasting." };
  return null;
}

/** Facts for the copilot. */
export function bodyFacts(records: BodyRecord[], today = new Date()) {
  const avg7 = (id: MetricId) => summary(inRange(records, id, "7d", today))?.avg;
  const bp = inRange(records, "bp", "all", today).at(-1);
  return { sleep7: avg7("sleep"), steps7: avg7("steps"), mood7: avg7("mood"), lastBp: bp ? { sys: bp.value, dia: bp.value2 ?? 0, date: bp.date } : undefined, weightChange30: summary(inRange(records, "weight", "30d", today))?.change };
}

export function toCSV(records: BodyRecord[]) {
  const head = "date,metric,value,value2,unit,location,context,note";
  const esc = (s?: string) => (s ? `"${s.replace(/"/g, '""')}"` : "");
  return [head, ...[...records].sort((a, b) => a.date.localeCompare(b.date)).map((r) => [r.date, r.metric, r.value, r.value2 ?? "", metric(r.metric).unit, esc(r.location), esc(r.context), esc(r.note)].join(","))].join("\n");
}
