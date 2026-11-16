// MedScan logic: deterministic interpretation of lab values against the report's own reference range, and
// rule-based symptom triage. Educational support only; never a diagnosis.
export interface LabResult { test: string; value: number; unit: string; low?: number; high?: number; what: string; ifLow?: string; ifHigh?: string }
export type Flag = "low" | "normal" | "high";

export const flagOf = (r: LabResult): Flag => (r.low !== undefined && r.value < r.low ? "low" : r.high !== undefined && r.value > r.high ? "high" : "normal");

export function explain(r: LabResult): string {
  const f = flagOf(r);
  const range = `${r.low ?? "–"}–${r.high ?? "–"} ${r.unit}`;
  if (f === "normal") return `Within the reference range on this report (${range}).`;
  return `${f === "low" ? "Below" : "Above"} the reference range on this report (${range}). ${(f === "low" ? r.ifLow : r.ifHigh) ?? "Worth discussing with your clinician."}`;
}

export function questionsFor(results: LabResult[]): string[] {
  const out = results.filter((r) => flagOf(r) !== "normal").map((r) => `My ${r.test} is ${flagOf(r)} (${r.value} ${r.unit}). What could be causing it, and does it need treatment or a retest?`);
  if (out.length) out.push("Could any of these be related to perimenopause or menopause, or to something else?");
  return out;
}

/** Fictional sample reports for the demo personas. Reference ranges are typical examples; labs differ. */
export const SAMPLE_REPORTS: Record<string, { lab: string; date: string; results: LabResult[] }> = {
  bea: { lab: "Example Diagnostics (fictional)", date: "2026-10-28", results: [
    { test: "Hemoglobin", value: 11.6, unit: "g/dL", low: 12, high: 15.5, what: "Carries oxygen in your blood.", ifLow: "Low hemoglobin (anaemia) can cause tiredness; heavy periods and low iron are common causes." },
    { test: "Ferritin", value: 12, unit: "ng/mL", low: 15, high: 150, what: "Your body's iron stores.", ifLow: "Low iron stores are common with heavy periods and can cause fatigue and hair shedding." },
    { test: "Vitamin D (25-OH)", value: 24, unit: "ng/mL", low: 30, high: 100, what: "Helps absorb calcium for bones and supports muscles.", ifLow: "Many people are low, especially in winter; your clinician may suggest a supplement." },
    { test: "TSH", value: 2.4, unit: "mIU/L", low: 0.4, high: 4.0, what: "Checks how your thyroid is working." },
    { test: "HbA1c", value: 5.2, unit: "%", high: 5.6, what: "Average blood sugar over about 3 months." },
  ] },
  nancy: { lab: "Example Diagnostics (fictional)", date: "2026-10-30", results: [
    { test: "LDL cholesterol", value: 148, unit: "mg/dL", high: 129, what: "The cholesterol linked to heart disease risk.", ifHigh: "LDL often rises after menopause; diet, activity and sometimes medicine can help." },
    { test: "HbA1c", value: 5.9, unit: "%", high: 5.6, what: "Average blood sugar over about 3 months.", ifHigh: "A level in this range can indicate higher risk of type 2 diabetes. Lifestyle changes can make a real difference." },
    { test: "Vitamin D (25-OH)", value: 18, unit: "ng/mL", low: 30, high: 100, what: "Helps absorb calcium for bones.", ifLow: "Low vitamin D matters for bone health after menopause." },
    { test: "TSH", value: 2.1, unit: "mIU/L", low: 0.4, high: 4.0, what: "Checks how your thyroid is working." },
    { test: "Hemoglobin", value: 13.4, unit: "g/dL", low: 12, high: 15.5, what: "Carries oxygen in your blood." },
  ] },
};

// ---- Symptom triage (validated-rule style; to be clinically reviewed before production)
export const RED_FLAGS = [
  "Chest pain or pressure", "Sudden severe headache or weakness/numbness on one side", "Trouble breathing", "Fainting",
  "Bleeding after 12 months without periods", "Very heavy bleeding (soaking a pad every hour)", "Thoughts of harming yourself",
];
export const COMMON = ["Hot flashes / night sweats", "Poor sleep", "Low mood or anxiety", "Brain fog", "Joint pain", "Irregular periods", "Vaginal dryness", "Palpitations", "Unusual fatigue", "Hair thinning"];

export type Triage = "emergency" | "appointment" | "self-care";
export function triage(redFlags: string[], symptoms: string[], weeks: number, impact: 0 | 1 | 2 | 3): { level: Triage; text: string } {
  if (redFlags.length) return { level: "emergency", text: "Please get urgent medical help now: call your local emergency number or go to an emergency department. Don't wait for an appointment." };
  if (impact >= 2 || weeks >= 4 || symptoms.includes("Palpitations") || symptoms.includes("Unusual fatigue"))
    return { level: "appointment", text: "These symptoms are worth a conversation with a clinician soon. A telehealth or free clinic visit may be faster than waiting for a regular appointment. Bring your FEMORA summary." };
  return { level: "self-care", text: "This sounds manageable with self-care for now. Keep tracking your symptoms, and book a visit if they last more than 4 weeks or start affecting your daily life." };
}

// ---- Home sample collection: results in a couple of days (simulated booking + tracker)
export const HOME_TESTS = [
  { id: "women-panel", name: "Women's midlife panel", includes: "Hemoglobin, ferritin, vitamin D, TSH, HbA1c, cholesterol", days: 2 },
  { id: "hpv", name: "HPV self-sampling kit", includes: "Self-collected cervical sample, posted back", days: 3 },
  { id: "bone-heart", name: "Heart & bone check", includes: "Cholesterol, HbA1c, vitamin D, calcium", days: 2 },
];
export const STAGES = ["Booked", "Sample collected", "At the lab", "Results ready"] as const;
export function resultsDate(booked: Date, days: number) { const d = new Date(booked); d.setDate(d.getDate() + days); return d; }
