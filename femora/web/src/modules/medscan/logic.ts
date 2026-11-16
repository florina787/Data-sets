// MedScan logic: deterministic interpretation of lab values against the report's own reference range, and
// rule-based symptom triage. Educational support only; never a diagnosis.
export interface LabResult { test: string; value: number; unit: string; low?: number; high?: number; what: string; ifLow?: string; ifHigh?: string }
export type Flag = "low" | "normal" | "high";

export const flagOf = (r: LabResult): Flag => (r.low !== undefined && r.value < r.low ? "low" : r.high !== undefined && r.value > r.high ? "high" : "normal");

/** Common tests with plain-language descriptions; ranges always come from HER report, never defaults. */
export const COMMON_TESTS: { test: string; unit: string; what: string }[] = [
  { test: "Hemoglobin", unit: "g/dL", what: "Carries oxygen in your blood." },
  { test: "Ferritin", unit: "ng/mL", what: "Your body's iron stores." },
  { test: "Vitamin D (25-OH)", unit: "ng/mL", what: "Helps absorb calcium for bones and supports muscles." },
  { test: "TSH", unit: "mIU/L", what: "Checks how your thyroid is working." },
  { test: "HbA1c", unit: "%", what: "Average blood sugar over about 3 months." },
  { test: "LDL cholesterol", unit: "mg/dL", what: "The cholesterol most linked to heart disease risk." },
  { test: "HDL cholesterol", unit: "mg/dL", what: "Often called 'good' cholesterol." },
  { test: "Triglycerides", unit: "mg/dL", what: "A type of fat in the blood." },
  { test: "Fasting glucose", unit: "mg/dL", what: "Blood sugar after not eating." },
];

export function explain(r: LabResult): string {
  const f = flagOf(r);
  const range = `${r.low ?? "–"}–${r.high ?? "–"} ${r.unit}`;
  if (f === "normal") return `Within the reference range on this report (${range}).`;
  return `${f === "low" ? "Below" : "Above"} the reference range on your report (${range}). ${(f === "low" ? r.ifLow : r.ifHigh) ?? "Worth discussing with your clinician."}`;
}

export function questionsFor(results: LabResult[]): string[] {
  const out = results.filter((r) => flagOf(r) !== "normal").map((r) => `My ${r.test} is ${flagOf(r)} (${r.value} ${r.unit}). What could be causing it, and does it need treatment or a retest?`);
  if (out.length) out.push("Could any of these be related to perimenopause or menopause, or to something else?");
  return out;
}

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

