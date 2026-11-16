import { describe, expect, it } from "vitest";
import { reply } from "../modules/conversation/router";
import { safetyCheck } from "../modules/conversation/safety";
import { SOURCES } from "../modules/conversation/sources";
import type { ReplyContext } from "../modules/conversation/types";

const ctx = (text: string): ReplyContext => ({
  text, mode: "talk", history: [], memory: [],
  profile: { name: "Bea", stage: "Late menopausal transition", cuisine: ["South Asia"], diet: "Vegetarian", livesAlone: true },
  food: { weekProtein: 280, weekDays: 7, weekAlcoholDays: 2, weekCaffeineAvg: 120, todayCalcium: 400, calciumTarget: 1200, proteinTarget: 60 },
});

describe("copilot", () => {
  it("routes crisis language to the safety layer before any provider", async () => {
    const r = await reply(ctx("Some days I want to die"));
    expect(r.safety).toBe("crisis");
    expect(r.provider).toBe("safety-rules");
    expect(r.text).toMatch(/emergency number/);
  });
  it("flags postmenopausal bleeding as urgent", () => {
    expect(safetyCheck("I have postmenopausal bleeding")?.safety).toBe("urgent-medical");
  });
  it("quotes deterministic food numbers", async () => {
    const r = await reply(ctx("How much protein did I eat this week?"));
    expect(r.text).toContain("280 g of protein");
    expect(r.text).toContain("40 g a day");
  });
  it("supports long conversations about ordinary life", async () => {
    const r = await reply(ctx("I feel so lonely since my friends moved away"));
    expect(r.followUps?.length).toBeGreaterThan(0);
    expect(r.actions?.some((a) => a.payload === "/app/sisterhood")).toBe(true);
  });
  it("only cites sources that exist", async () => {
    for (const q of ["my periods are irregular", "hot flashes at work", "I can't sleep"]) {
      const r = await reply(ctx(q));
      for (const s of r.sources ?? []) expect(SOURCES.find((x) => x.id === s)).toBeTruthy();
      for (const m of r.text.matchAll(/\[(S\d+)\]/g)) expect(r.sources).toContain(m[1]);
    }
  });
  it("proposes memory rather than saving it", async () => {
    const r = await reply(ctx("I am vegetarian"));
    expect(r.memory).toBe("Eats a vegetarian diet");
  });
});
