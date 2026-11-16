import { describe, expect, it } from "vitest";
import { sugarPct, sugarLevel, energySplit } from "../modules/nutrition/engine";
import { doseStatus, checkupState, completeCheckup, type Medication } from "../modules/reminders/logic";
import { SAMPLE_REPORTS, flagOf, questionsFor, triage } from "../modules/medscan/logic";
import { opportunitiesFor, toICS, CATEGORIES } from "../modules/opportunities/data";
import { whatsappUrl, emailUrl } from "../modules/connections/share";

describe("sugar percentage", () => {
  it("computes added sugar as % of calories", () => {
    expect(sugarPct({ kcal: 140, addedSugar: 39 })).toBe(111.4); // cola: every calorie from sugar (rounded table values)
    expect(sugarPct({ kcal: 200, addedSugar: 5 })).toBe(10);
    expect(sugarPct({ kcal: 200 })).toBeNull();
    expect(sugarLevel(3)).toBe("low"); expect(sugarLevel(7)).toBe("moderate"); expect(sugarLevel(12)).toBe("high");
  });
  it("splits energy by macronutrient", () => {
    expect(energySplit({ protein: 25, carbs: 25, fat: 0 })).toEqual({ protein: 50, carbs: 50, fat: 0 });
  });
});

describe("reminders", () => {
  const med: Medication = { id: "m", profileId: "bea", name: "Vitamin D", dose: "1000 IU", times: ["08:00", "20:00"], taken: {} };
  it("marks past doses as due and future as upcoming", () => {
    const s = doseStatus([med], new Date("2026-11-16T12:00:00"));
    expect(s.map((x) => x.status)).toEqual(["due", "upcoming"]);
  });
  it("knows when a dose was taken", () => {
    const s = doseStatus([{ ...med, taken: { "2026-11-16": ["08:00"] } }], new Date("2026-11-16T12:00:00"));
    expect(s[0].status).toBe("taken");
  });
  it("flags overdue check-ups and reschedules when done", () => {
    const now = new Date("2026-11-16T10:00:00");
    const c = { id: "c", profileId: "bea", kind: "Mammogram", due: "2026-11-01", repeatMonths: 24 };
    expect(checkupState(c, now)).toBe("overdue");
    expect(completeCheckup(c, now).due).toBe("2028-11-16");
  });
});

describe("MedScan", () => {
  it("flags results against the report's reference range", () => {
    const r = SAMPLE_REPORTS.nancy.results;
    expect(flagOf(r.find((x) => x.test === "Vitamin D (25-OH)")!)).toBe("low");
    expect(flagOf(r.find((x) => x.test === "TSH")!)).toBe("normal");
    expect(questionsFor(r).length).toBeGreaterThan(1);
  });
  it("triages red flags to emergency first", () => {
    expect(triage(["Chest pain or pressure"], [], 0, 0).level).toBe("emergency");
    expect(triage([], ["Hot flashes / night sweats"], 6, 1).level).toBe("appointment");
    expect(triage([], ["Poor sleep"], 1, 1).level).toBe("self-care");
  });
});

describe("free care, events & deals", () => {
  const ops = opportunitiesFor("Nashville", new Date("2026-11-16T09:00:00"));
  it("covers every category, labelled as examples, in her city", () => {
    for (const c of CATEGORIES) expect(ops.some((o) => o.category === c)).toBe(true);
    expect(ops.every((o) => o.example)).toBe(true);
    expect(ops.some((o) => o.where === "Nashville")).toBe(true);
    expect(ops.filter((o) => o.category === "Deals").every((o) => !o.free)).toBe(true);
  });
  it("exports a valid calendar event", () => {
    const ics = toICS(ops[0]);
    expect(ics).toMatch(/^BEGIN:VCALENDAR/);
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("(example)");
  });
});

describe("connections", () => {
  it("builds WhatsApp and email links without sending anything", () => {
    expect(whatsappUrl("Hi there", "+1 (615) 555-0100")).toBe("https://wa.me/16155550100?text=Hi%20there");
    expect(emailUrl("a@example.com", "Hi", "Body")).toBe("mailto:a%40example.com?subject=Hi&body=Body");
  });
});
