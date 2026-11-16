import { describe, expect, it, vi } from "vitest";
import { sugarPct, sugarLevel, energySplit } from "../modules/nutrition/engine";
import { doseStatus, checkupState, completeCheckup, record, adherence, type Medication, type Checkup } from "../modules/reminders/logic";
import { flagOf, questionsFor, triage, explain } from "../modules/medscan/logic";
import { OFFICIAL_RESOURCES, filterFor, validFeed, resourcesFor, toICS, type Opportunity } from "../modules/opportunities/data";
import { whatsappUrl, emailUrl } from "../modules/connections/share";
import { DEFAULT_PREFS, decide, inQuietHours, applyFeedback } from "../modules/notifications/engine";
import { suggestions } from "../modules/muse/proactive";
import { llamaProvider, testLlama, contextBlock } from "../modules/conversation/llamaProvider";

describe("sugar percentage", () => {
  it("computes added sugar as % of calories", () => {
    expect(sugarPct({ kcal: 200, addedSugar: 5 })).toBe(10);
    expect(sugarPct({ kcal: 200 })).toBeNull();
    expect(sugarLevel(3)).toBe("low"); expect(sugarLevel(7)).toBe("moderate"); expect(sugarLevel(12)).toBe("high");
  });
  it("splits energy by macronutrient", () => expect(energySplit({ protein: 25, carbs: 25, fat: 0 })).toEqual({ protein: 50, carbs: 50, fat: 0 }));
});

describe("medication planner (deterministic)", () => {
  const med: Medication = { id: "m", profileId: "bea", name: "Vitamin D", dose: "1000 IU", frequency: "Twice daily", times: ["08:00", "20:00"], log: {} };
  const noon = new Date("2026-11-16T12:00:00");
  it("marks past doses due and future upcoming", () => expect(doseStatus([med], noon).map((x) => x.status)).toEqual(["due", "upcoming"]));
  it("records taken, skipped and snoozed", () => {
    expect(doseStatus([record(med, "08:00", "taken", noon)], noon)[0].status).toBe("taken");
    expect(doseStatus([record(med, "08:00", "skipped", noon)], noon)[0].status).toBe("skipped");
    expect(doseStatus([record(med, "08:00", "snoozed", noon)], noon)[0].status).toBe("snoozed");
    expect(doseStatus([record(med, "08:00", "snoozed", noon)], new Date("2026-11-16T12:30:00"))[0].status).toBe("due");
  });
  it("respects start and end dates", () => {
    expect(doseStatus([{ ...med, start: "2026-11-20" }], noon)).toHaveLength(0);
    expect(doseStatus([{ ...med, end: "2026-11-10" }], noon)).toHaveLength(0);
  });
  it("computes adherence only from history", () => {
    expect(adherence(med, 7, noon)).toBe(0);
    expect(adherence({ ...med, start: "2026-11-16" }, 7, noon)).toBeNull();
  });
});

describe("check-up planner never invents intervals", () => {
  const now = new Date("2026-11-16T10:00:00");
  const c: Checkup = { id: "c", profileId: "nancy", kind: "Breast screening", next: "2026-11-01", questions: [] };
  it("flags passed dates", () => expect(checkupState(c, now)).toBe("overdue"));
  it("without an interval, completing does not schedule a next date", () => {
    const d = completeCheckup(c, now); expect(d.next).toBeUndefined(); expect(d.last).toBe("2026-11-16");
  });
  it("with an explicit interval, schedules the next date", () => expect(completeCheckup({ ...c, repeatMonths: 12, source: "clinician" }, now).next).toBe("2027-11-16"));
  it("no date means no reminder", () => expect(checkupState({ ...c, next: undefined }, now)).toBe("none"));
});

describe("notification engine", () => {
  const n = { key: "k1", category: "community" as const, priority: "normal" as const, title: "Walk", body: "Saturday" };
  const day = new Date("2026-11-16T12:00:00"), night = new Date("2026-11-16T23:30:00");
  it("delivers immediate categories, digests digest categories", () => {
    expect(decide({ ...n, category: "health" }, DEFAULT_PREFS, [], day).action).toBe("deliver");
    expect(decide(n, DEFAULT_PREFS, [], day).action).toBe("digest");
  });
  it("respects quiet hours across midnight", () => {
    expect(inQuietHours(DEFAULT_PREFS.quietHours, night)).toBe(true);
    expect(inQuietHours(DEFAULT_PREFS.quietHours, day)).toBe(false);
    expect(decide({ ...n, category: "health" }, DEFAULT_PREFS, [], night).action).toBe("digest");
  });
  it("always delivers critical safety alerts", () => expect(decide({ ...n, category: "safety", priority: "critical" }, DEFAULT_PREFS, [], night).action).toBe("deliver"));
  it("suppresses muted categories, duplicates and snoozed items", () => {
    expect(decide({ ...n, category: "lifestyle" }, DEFAULT_PREFS, [], day).action).toBe("suppress");
    expect(decide(n, DEFAULT_PREFS, [{ key: "k1", category: "community", at: day.getTime() }], day).action).toBe("suppress");
    expect(decide(n, DEFAULT_PREFS, [], day, { k1: day.getTime() + 60000 }).action).toBe("suppress");
  });
  it("enforces daily limits", () => {
    const hist = [1, 2, 3].map((i) => ({ key: `x${i}`, category: "community" as const, at: day.getTime() - i }));
    const prefs = { ...DEFAULT_PREFS, categories: { ...DEFAULT_PREFS.categories, community: { enabled: true, mode: "immediate" as const, maxPerDay: 2 } } };
    expect(decide(n, prefs, hist, day).reason).toBe("daily limit reached");
  });
  it("hides medication names when privacy is on", () => {
    const d = decide({ ...n, category: "health", title: "Time for Estradiol", body: "1 mg", sensitive: { title: "Reminder from Muse", body: "You have a reminder." } }, DEFAULT_PREFS, [], day);
    expect(d.title).toBe("Reminder from Muse"); expect(d.body).not.toContain("1 mg");
  });
  it("learns from 'not relevant' feedback", () => expect(applyFeedback(DEFAULT_PREFS, "health", false, 2).categories.health.maxPerDay).toBe(6));
});

describe("proactive Muse uses only real records", () => {
  const now = new Date("2026-11-16T09:00:00");
  it("mentions an appointment only when it exists", () => {
    const none = suggestions({ name: "Nancy", city: "Nashville", meds: [], checkups: [], interests: [], hasFoodToday: false, privateMedication: true }, now);
    expect(none.some((s) => /appointment|screening|check-up on/.test(s.text) && !/help setting up/.test(s.text))).toBe(false);
    expect(none.find((s) => s.id === "discover")?.text).toContain("Nashville");
    const withCk = suggestions({ name: "Nancy", city: "Nashville", meds: [], interests: [], hasFoodToday: true, privateMedication: true,
      checkups: [{ id: "a", profileId: "nancy", kind: "General health check-up", next: "2026-11-19", questions: ["Ask about sleep"] }] }, now);
    expect(withCk[0].text).toMatch(/^Nancy, you have a general health check-up on Thursday\. Would you like to review the questions you saved/);
  });
  it("asks for the city rather than assuming it", () => {
    const s = suggestions({ name: "Bea", meds: [], checkups: [], interests: [], hasFoodToday: true, privateMedication: true }, now);
    expect(s.some((x) => x.id === "city")).toBe(true);
  });
});

describe("verified discovery", () => {
  it("official resources carry a verification date and https URL", () => {
    for (const r of OFFICIAL_RESOURCES) { expect(r.url.startsWith("https://")).toBe(true); expect(r.verifiedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/); }
    expect(resourcesFor("United States", "Nashville")[0].city).toBe("Nashville");
  });
  const base: Opportunity = { id: "1", organization: "Health Dept", title: "Screening day", category: "Screening campaign", country: "United States", city: "Nashville", venue: "Clinic", online: false, start: "2026-12-01", eligibility: "", cost: "free", registration: "", url: "https://example.org", verifiedAt: "2026-11-16", provenance: "verified-feed" };
  it("rejects unverified feed items", () => {
    expect(validFeed([base, { ...base, id: "2", verifiedAt: undefined }, { ...base, id: "3", url: "http://x" }])).toHaveLength(1);
  });
  it("hides commercial offers unless she opts in", () => {
    const d = { ...base, id: "d", category: "Discount" as const, cost: "discount" as const };
    expect(filterFor([base, d], { city: "Nashville", commercial: false })).toHaveLength(1);
    expect(filterFor([base, d], { city: "Nashville", commercial: true })).toHaveLength(2);
  });
  it("exports calendar files", () => expect(toICS(base)).toContain("SUMMARY:Screening day"));
});

describe("MedScan uses the report's own range", () => {
  const r = { test: "Vitamin D (25-OH)", value: 18, unit: "ng/mL", low: 30, high: 100, what: "" };
  it("flags and explains", () => { expect(flagOf(r)).toBe("low"); expect(explain(r)).toContain("30–100"); expect(questionsFor([r]).length).toBe(2); });
  it("without a range, never flags", () => expect(flagOf({ ...r, low: undefined, high: undefined })).toBe("normal"));
  it("triages red flags first", () => {
    expect(triage(["Chest pain or pressure"], [], 0, 0).level).toBe("emergency");
    expect(triage([], ["Poor sleep"], 1, 1).level).toBe("self-care");
  });
});

describe("llama.cpp adapter", () => {
  const ctx = { text: "hi", mode: "talk" as const, history: [{ id: "1", role: "user" as const, text: "hi", mode: "talk" as const, at: 0 }], memory: [], profile: { name: "Bea", cuisine: [] },
    food: { weekProtein: 0, weekDays: 0, weekAlcoholDays: 0, weekCaffeineAvg: 0, todayCalcium: 0, calciumTarget: 1200, proteinTarget: 60 } };
  it("calls the OpenAI-compatible endpoint with persona and facts", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ choices: [{ message: { content: "Hello Bea" } }] })));
    const r = await llamaProvider({ url: "http://localhost:8080/", enabled: true, maxTokens: 64 }, f as unknown as typeof fetch).respond(ctx);
    expect(r.text).toBe("Hello Bea");
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8080/v1/chat/completions");
    expect(JSON.parse(init.body as string).messages[0].content).toContain("Menopause stage: not recorded; do not assume.");
  });
  it("reports connection failures", async () => {
    await expect(testLlama("http://localhost:1", (async () => new Response("", { status: 503 })) as unknown as typeof fetch)).rejects.toThrow("503");
  });
  it("never claims a stage that wasn't recorded", () => expect(contextBlock(ctx)).not.toMatch(/perimenopause|postmenopause/));
});

describe("connections", () => {
  it("builds WhatsApp and email links without sending anything", () => {
    expect(whatsappUrl("Hi there", "+1 (615) 555-0100")).toBe("https://wa.me/16155550100?text=Hi%20there");
    expect(emailUrl("a@example.com", "Hi", "Body")).toBe("mailto:a%40example.com?subject=Hi&body=Body");
  });
});
