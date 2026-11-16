import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppStateProvider } from "../lib/app-state";
import { AppRoutes } from "../App";
import { cycleLengths, cycleStats, stageHint, weeklySymptoms, journeyFacts, doctorSummary, type Period } from "../modules/journey/logic";
import { reply } from "../modules/conversation/router";

const P = (start: string, end?: string): Period => ({ id: start, start, end, flow: "medium" });
const now = new Date("2026-11-16T12:00:00");

describe("journey logic", () => {
  it("computes start-to-start cycle lengths and stats", () => {
    const ps = [P("2026-08-01"), P("2026-08-29"), P("2026-09-30"), P("2026-10-27")];
    expect(cycleLengths(ps).map((c) => c.length)).toEqual([28, 32, 27]);
    expect(cycleStats(ps)).toMatchObject({ mean: 29, min: 27, max: 32, maxConsecutiveDiff: 5 });
  });
  it("needs data before describing patterns", () => expect(stageHint([P("2026-11-01")], [], now).key).toBe("insufficient"));
  it("describes persistent ≥7-day variability as early transition (educational)", () => {
    const ps = [P("2026-05-01"), P("2026-05-26"), P("2026-06-30"), P("2026-07-24"), P("2026-08-30"), P("2026-09-24")].concat(P("2026-10-30"));
    expect(stageHint(ps, [], now).key).toBe("early-transition");
  });
  it("describes 60+ day gaps as late transition", () => expect(stageHint([P("2026-06-01"), P("2026-08-15"), P("2026-11-01")], [], now).key).toBe("late-transition"));
  it("recognises 12 months without a period only in retrospect", () => expect(stageHint([P("2025-10-01")], [], now).key).toBe("twelve-months"));
  it("switches off cycle staging with confounders", () => expect(stageHint([P("2026-06-01"), P("2026-09-01")], ["hormonal contraception"], now).key).toBe("not-applicable"));
  it("buckets symptoms by week", () => {
    const e = [{ name: "Hot flash", severity: 2, at: now.getTime() - 3600e3 }, { name: "Hot flash", severity: 3, at: now.getTime() - 8 * 864e5 }];
    const w = weeklySymptoms(e, 2, now);
    expect(w[1]["Hot flash" as keyof typeof w[1]]).toBe(1);
    expect(w[0]["Hot flash" as keyof typeof w[0]]).toBe(1);
  });
  it("builds a doctor summary from records only", () => {
    const s = doctorSummary("Nancy", [P("2026-09-01"), P("2026-10-01")], [], [], [], stageHint([], [], now));
    expect(s).toContain("Nancy"); expect(s).toContain("Self-recorded information");
  });
});

describe("Muse uses journey facts", () => {
  const base = { mode: "talk" as const, history: [], memory: [], profile: { name: "Bea", cuisine: [] },
    food: { weekProtein: 0, weekDays: 0, weekAlcoholDays: 0, weekCaffeineAvg: 0, todayCalcium: 0, calciumTarget: 1200, proteinTarget: 60 } };
  it("refuses to guess without records", async () => {
    const r = await reply({ ...base, text: "When was my last period?", journey: journeyFacts([], [], now) });
    expect(r.text).toMatch(/won't guess/);
  });
  it("answers from records", async () => {
    const r = await reply({ ...base, text: "When was my last period?", journey: journeyFacts([P("2026-10-01"), P("2026-10-29")], [], now) });
    expect(r.text).toContain("18 days ago"); expect(r.text).toContain("28 days");
  });
});

describe("journey page", () => {
  it("logs a period that persists and can be deleted", async () => {
    localStorage.setItem("femora:v1:locations", JSON.stringify({ bea: { region: "North America", city: "Austin" } }));
    const u = userEvent.setup();
    const view = render(<AppStateProvider><MemoryRouter initialEntries={["/app/journey"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    await screen.findByText("Log a period", {}, { timeout: 3000 });
    await u.click(screen.getByRole("button", { name: /Save period/ }));
    expect(JSON.parse(localStorage.getItem("femora:v1:periods:bea")!)).toHaveLength(1);
    view.unmount();
    render(<AppStateProvider><MemoryRouter initialEntries={["/app/journey"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    const del = await screen.findByLabelText(/Delete period starting/, {}, { timeout: 3000 });
    await u.click(del);
    expect(JSON.parse(localStorage.getItem("femora:v1:periods:bea")!)).toHaveLength(0);
  });
});
