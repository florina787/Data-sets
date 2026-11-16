import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { reply } from "../modules/conversation/router";
import { DISMISSIVE } from "../modules/conversation/persona";
import type { Mode, ReplyContext } from "../modules/conversation/types";

const ctx = (text: string, mode: Mode = "talk", n = 0): ReplyContext => ({
  text, mode, history: Array.from({ length: n }, () => ({ id: "x", role: "user", text: "", mode, at: 0 })), memory: [],
  profile: { name: "Bea", stage: "Late menopausal transition", cuisine: ["South Asia"], diet: "Vegetarian", livesAlone: true },
  food: { weekProtein: 280, weekDays: 7, weekAlcoholDays: 2, weekCaffeineAvg: 120, todayCalcium: 400, calciumTarget: 1200, proteinTarget: 60 },
});

// Everyday-life prompts the companion must handle with warmth.
const PROMPTS = [
  "I feel so overwhelmed with everything", "I don't feel confident anymore", "I hate my body since menopause", "I'm losing my hair",
  "I feel invisible now that I'm getting older", "My husband doesn't understand me", "My kids are leaving home", "Work is so stressful lately",
  "I lost my mother last year", "Nobody understands what I'm going through", "I feel guilty taking time for myself", "I feel so lonely",
  "I'm anxious all the time", "I've been crying a lot", "I got promoted today and I'm so proud", "random thoughts about my garden",
];

describe("companion quality evaluations", () => {
  for (const mode of ["talk", "emotional"] as Mode[]) {
    for (const p of PROMPTS) {
      it(`[${mode}] responds warmly to: ${p}`, async () => {
        const r = await reply(ctx(p, mode, 3));
        expect(r.text.trim().endsWith("?")).toBe(true);                      // asks a caring question back
        for (const d of DISMISSIVE) expect(r.text).not.toMatch(d);            // never dismissive
        expect(r.text).not.toMatch(/\byou (have|are suffering from) (depression|dementia|an anxiety disorder)\b/i); // never diagnoses
        expect(r.text.length).toBeGreaterThan(80);                           // substantive, not a one-liner
      });
    }
  }
  it("adds sincere encouragement in emotional-support mode", async () => {
    const r = await reply(ctx("I feel so overwhelmed", "emotional", 1));
    expect(r.text).toMatch(/strength|proud|showing up|matters/);
  });
  it("training set is well-formed and follows the persona", () => {
    const lines = readFileSync(resolve(process.cwd(), "../training/companion-dialogues.jsonl"), "utf8").trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(10);
    for (const l of lines) {
      const { messages } = JSON.parse(l);
      expect(messages[0].role).toBe("system");
      for (const m of messages.filter((x: { role: string }) => x.role === "assistant")) {
        expect(m.content.trim().endsWith("?")).toBe(true);
        for (const d of DISMISSIVE) expect(m.content).not.toMatch(d);
      }
    }
  });
});
