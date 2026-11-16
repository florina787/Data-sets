import { load, save, uid, dayKey, addDays } from "../../lib/storage";
import type { LogEntry, Meal } from "./engine";
import { DEFAULT_TARGETS } from "./engine";
import type { Nutrient } from "./foods";

const key = (profileId: string) => `food:${profileId}`;

// Synthetic 7-day seed per profile, built from the profile's cuisine. Clearly fictional demo data.
const SEED: Record<string, [string, Meal][][]> = {
  bea: [[["eggs", "Breakfast"], ["coffee", "Breakfast"], ["chicken-salad", "Lunch"], ["tofu", "Dinner"]],
        [["coffee", "Breakfast"], ["greek-yogurt", "Breakfast"], ["tacos", "Lunch"], ["soda", "Snacks"], ["salmon-rice", "Dinner"], ["red-wine", "Dinner"]],
        [["oats", "Breakfast"], ["coffee", "Lunch"], ["beans-rice", "Lunch"], ["almonds", "Snacks"], ["miso", "Dinner"], ["edamame", "Dinner"]]],
  nancy: [[["congee", "Breakfast"], ["green-tea", "Breakfast"], ["tofu", "Lunch"], ["salmon-rice", "Dinner"]],
          [["eggs", "Breakfast"], ["coffee", "Breakfast"], ["tacos", "Lunch"], ["edamame", "Snacks"], ["egusi", "Dinner"]],
          [["milk", "Breakfast"], ["oats", "Breakfast"], ["beans-rice", "Lunch"], ["almonds", "Snacks"], ["chicken-salad", "Dinner"], ["red-wine", "Dinner"]]],
};

export function seedEntries(profileId: string, today = new Date()): LogEntry[] {
  const days = SEED[profileId] ?? SEED.bea;
  const out: LogEntry[] = [];
  for (let i = 0; i <= 6; i++) {
    const d = dayKey(addDays(today, -i));
    const meals = days[i % days.length].filter(([, m]) => i > 0 || m === "Breakfast"); // today: breakfast only
    for (const [foodId, meal] of meals) out.push({ id: uid(), foodId, meal, portion: 1, date: d });
  }
  return out;
}

export function loadLog(profileId: string): LogEntry[] {
  const existing = load<LogEntry[] | null>(key(profileId), null);
  if (existing) return existing;
  const seeded = seedEntries(profileId);
  save(key(profileId), seeded);
  return seeded;
}
export const saveLog = (profileId: string, entries: LogEntry[]) => save(key(profileId), entries);

export const loadTargets = (profileId: string) => ({ ...DEFAULT_TARGETS, ...load<Partial<Record<Nutrient, number>>>(`targets:${profileId}`, {}) });
export const saveTargets = (profileId: string, t: Partial<Record<Nutrient, number>>) => save(`targets:${profileId}`, t);
