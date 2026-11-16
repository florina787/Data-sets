// Deterministic nutrition engine. No AI here: numbers come only from the food table × portion.
import { FOODS, foodById, type Food, type Nutrient, type Nutrients } from "./foods";

export type Meal = "Breakfast" | "Lunch" | "Dinner" | "Snacks";
export const MEALS: Meal[] = ["Breakfast", "Lunch", "Dinner", "Snacks"];

export interface LogEntry { id: string; foodId: string; meal: Meal; portion: number; date: string } // portion = servings multiplier

export interface Totals { values: Nutrients; missing: Partial<Record<Nutrient, number>>; entries: number; plantEstrogenServings: number }

export const NUTRIENTS: Nutrient[] = ["kcal", "protein", "carbs", "fiber", "fat", "satFat", "addedSugar", "calcium", "iron", "vitD", "b12", "sodium", "caffeine", "alcohol"];

export const META: Record<Nutrient, { label: string; unit: string; kind: "goal" | "limit" | "info" }> = {
  kcal: { label: "Energy", unit: "kcal", kind: "info" },
  protein: { label: "Protein", unit: "g", kind: "goal" },
  carbs: { label: "Carbohydrates", unit: "g", kind: "info" },
  fiber: { label: "Fiber", unit: "g", kind: "goal" },
  fat: { label: "Fat", unit: "g", kind: "info" },
  satFat: { label: "Saturated fat", unit: "g", kind: "limit" },
  addedSugar: { label: "Added sugar", unit: "g", kind: "limit" },
  calcium: { label: "Calcium", unit: "mg", kind: "goal" },
  iron: { label: "Iron", unit: "mg", kind: "goal" },
  vitD: { label: "Vitamin D", unit: "µg", kind: "goal" },
  b12: { label: "Vitamin B12", unit: "µg", kind: "goal" },
  sodium: { label: "Sodium", unit: "mg", kind: "limit" },
  caffeine: { label: "Caffeine", unit: "mg", kind: "limit" },
  alcohol: { label: "Alcohol", unit: "g", kind: "limit" },
};

/** Default reference values for women 51+, editable by the user. Sources noted in docs/AUDIT.md §9; to be verified
 *  against country-specific guidance in the research workstream. Energy is shown, never targeted by default. */
export const DEFAULT_TARGETS: Partial<Record<Nutrient, number>> = {
  protein: 60, fiber: 21, calcium: 1200, iron: 8, vitD: 15, b12: 2.4, satFat: 20, addedSugar: 25, sodium: 2300, caffeine: 400, alcohol: 10,
};

export const zero = (): Nutrients => Object.fromEntries(NUTRIENTS.map((k) => [k, 0])) as Nutrients;

export function totals(entries: LogEntry[]): Totals {
  const values = zero();
  const missing: Partial<Record<Nutrient, number>> = {};
  let plantEstrogenServings = 0;
  for (const e of entries) {
    const food = foodById(e.foodId);
    if (!food) continue;
    if (food.plantEstrogen) plantEstrogenServings += e.portion;
    for (const k of NUTRIENTS) {
      const v = food.n[k];
      if (v === undefined) {
        // caffeine/alcohol absent means "none" for most foods; other nutrients absent means unknown.
        if (k !== "caffeine" && k !== "alcohol") missing[k] = (missing[k] ?? 0) + 1;
      } else values[k] += v * e.portion;
    }
  }
  for (const k of NUTRIENTS) values[k] = Math.round(values[k] * 10) / 10;
  return { values, missing, entries: entries.length, plantEstrogenServings: Math.round(plantEstrogenServings * 10) / 10 };
}

/** Parse free text like "2 idli and sambar for breakfast, coffee" into candidate entries. Deterministic matcher. */
const WORDNUM: Record<string, number> = { a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, half: 0.5, "1/2": 0.5 };
export function parseNatural(text: string): { meal?: Meal; items: { food: Food; portion: number }[]; unmatched: string[] } {
  const lower = text.toLowerCase();
  const meal = MEALS.find((m) => lower.includes(m.toLowerCase())) ?? (lower.includes("snack") ? "Snacks" : undefined);
  const parts = lower.replace(/\b(for|at|in)\s+(breakfast|lunch|dinner|snacks?)\b/g, "").split(/,|\band\b|\bwith\b|\+|;/).map((s) => s.trim()).filter(Boolean);
  const items: { food: Food; portion: number }[] = [];
  const unmatched: string[] = [];
  for (const p of parts) {
    const qm = p.match(/^(\d+(?:\.\d+)?|a|an|one|two|three|four|half|1\/2)\b\s*(?:cups?|bowls?|plates?|glass(?:es)?|pieces?|servings?|of)?\s*/);
    let portion = 1;
    let rest = p;
    if (qm) { portion = Number(qm[1]) || WORDNUM[qm[1]] || 1; rest = p.slice(qm[0].length); }
    const words = rest.replace(/^(i had|had|ate|i ate|some)\s+/, "").trim();
    if (!words) continue;
    const match = bestMatch(words);
    if (match) {
      // "2 idli" means 2 pieces, and the serving is already 2 pieces; normalise piece-counted foods.
      const per = Number(match.serving.match(/^(\d+)\s+(pieces?|tacos?)/)?.[1] ?? 0);
      items.push({ food: match, portion: per && qm && /^\d/.test(qm[1]) ? Math.round((portion / per) * 100) / 100 : portion });
    } else unmatched.push(words);
  }
  return { meal, items, unmatched };
}

function bestMatch(q: string): Food | undefined {
  let best: { f: Food; s: number } | undefined;
  for (const food of FOODS) {
    for (const name of [food.name.toLowerCase(), ...food.aliases]) {
      let s = 0;
      if (q === name) s = 100;
      else if (q.includes(name)) s = 60 + name.length;
      else if (name.includes(q) && q.length >= 3) s = 40 + q.length;
      else {
        const qw = q.split(/\s+/).filter((w) => w.length > 2);
        const hit = qw.filter((w) => name.includes(w.replace(/s$/, ""))).length;
        if (hit) s = 10 * hit;
      }
      if (s > (best?.s ?? 0)) best = { f: food, s };
    }
  }
  return best && best.s >= 10 ? best.f : undefined;
}

export function searchFoods(q: string, region?: string): Food[] {
  const s = q.trim().toLowerCase();
  return FOODS.filter((x) => (!region || region === "All" || x.region === region) &&
    (!s || x.name.toLowerCase().includes(s) || x.aliases.some((a) => a.includes(s)) || x.region.toLowerCase().includes(s)));
}

/** Added sugar as a percentage of energy (1 g sugar = 4 kcal). WHO: under 10%, ideally under 5%. */
export const SUGAR_LIMIT_PCT = 10;
export const SUGAR_IDEAL_PCT = 5;
export function sugarPct(n: Partial<Nutrients>): number | null {
  if (!n.kcal || n.addedSugar === undefined) return null;
  return Math.round(((n.addedSugar * 4) / n.kcal) * 1000) / 10;
}
export function sugarLevel(pct: number | null): "unknown" | "low" | "moderate" | "high" {
  if (pct === null) return "unknown";
  return pct < SUGAR_IDEAL_PCT ? "low" : pct < SUGAR_LIMIT_PCT ? "moderate" : "high";
}

/** Share of energy from protein, carbohydrate, fat (4/4/9 kcal per g). Percentages of the macro-derived total. */
export function energySplit(n: Partial<Nutrients>) {
  const p = (n.protein ?? 0) * 4, c = (n.carbs ?? 0) * 4, f = (n.fat ?? 0) * 9;
  const sum = p + c + f;
  if (!sum) return null;
  const r = (x: number) => Math.round((x / sum) * 100);
  return { protein: r(p), carbs: r(c), fat: 100 - r(p) - r(c) };
}
