import { describe, expect, it } from "vitest";
import { parseNatural, totals, searchFoods } from "../modules/nutrition/engine";
import { FOODS } from "../modules/nutrition/foods";

const e = (foodId: string, portion = 1) => ({ id: foodId, foodId, meal: "Lunch" as const, portion, date: "2026-11-16" });

describe("nutrition engine (deterministic)", () => {
  it("sums nutrients times portion", () => {
    const t = totals([e("dal", 2), e("curd")]);
    expect(t.values.protein).toBe(12 * 2 + 8);
    expect(t.values.calcium).toBe(40 * 2 + 280);
    expect(t.plantEstrogenServings).toBe(2);
  });
  it("labels missing data instead of counting it as zero", () => {
    const t = totals([e("idli")]); // idli has no vitamin D value
    expect(t.missing.vitD).toBe(1);
    expect(t.missing.caffeine).toBeUndefined(); // absent caffeine means none
  });
  it("tracks alcohol and caffeine", () => {
    const t = totals([e("red-wine"), e("coffee", 2)]);
    expect(t.values.alcohol).toBe(14);
    expect(t.values.caffeine).toBe(190);
  });
  it("parses natural language with meal and counts", () => {
    const r = parseNatural("2 idli and sambar with chai for breakfast");
    expect(r.meal).toBe("Breakfast");
    expect(r.items.map((i) => i.food.id)).toEqual(["idli", "sambar", "chai"]);
    expect(r.items[0].portion).toBe(1); // "2 idli" = one 2-piece serving
  });
  it("reports unmatched foods", () => {
    const r = parseNatural("coffee and zzqx");
    expect(r.items).toHaveLength(1);
    expect(r.unmatched).toEqual(["zzqx"]);
  });
  it("covers many world regions", () => {
    expect(new Set(FOODS.map((f) => f.region)).size).toBeGreaterThanOrEqual(9);
    expect(searchFoods("", "West Africa").length).toBeGreaterThan(0);
  });
});
