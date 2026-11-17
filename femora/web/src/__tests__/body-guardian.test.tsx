import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppStateProvider } from "../lib/app-state";
import { AppRoutes } from "../App";
import { bpNote, hba1cNote, glucoseNote, inRange, summary, daily, toCSV, bodyFacts, type BodyRecord } from "../modules/body/logic";
import { checkInStatus, emergencyNumber, sosMessage, emergencyCard, CAPABILITIES, EMPTY_INFO, type CheckIn } from "../modules/guardian/logic";
import { reply } from "../modules/conversation/router";

const R = (metric: BodyRecord["metric"], date: string, value: number, value2?: number): BodyRecord => ({ id: date + metric + value, metric, date, value, value2 });
const today = new Date("2026-11-16T12:00:00");

describe("health dashboard logic", () => {
  it("explains blood pressure by ACC/AHA category, never as a score", () => {
    expect(bpNote(115, 75).label).toBe("Normal range");
    expect(bpNote(125, 78).label).toBe("Elevated range");
    expect(bpNote(134, 82).label).toBe("Stage 1 range");
    expect(bpNote(150, 95).label).toBe("Stage 2 range");
    expect(bpNote(190, 100).urgent).toBe(true);
  });
  it("explains HbA1c and glucose ranges with urgent flags", () => {
    expect(hba1cNote(5.9).label).toMatch(/prediabetes/); expect(hba1cNote(6.8).text).toMatch(/confirmation by a clinician/);
    expect(glucoseNote(50)?.urgent).toBe(true); expect(glucoseNote(110, "fasting")?.label).toBe("Fasting 100–125");
  });
  it("filters by date range and summarises", () => {
    const rs = [R("sleep", "2026-11-14", 6), R("sleep", "2026-11-15", 8), R("sleep", "2026-09-01", 5)];
    expect(inRange(rs, "sleep", "7d", today)).toHaveLength(2);
    expect(summary(inRange(rs, "sleep", "7d", today))).toMatchObject({ avg: 7, change: 2 });
    expect(inRange(rs, "sleep", "all", today)).toHaveLength(3);
  });
  it("averages same-day entries and exports CSV", () => {
    expect(daily([R("steps", "2026-11-15", 4000), R("steps", "2026-11-15", 6000)])[0].value).toBe(5000);
    expect(toCSV([R("bp", "2026-11-15", 120, 80)])).toContain("2026-11-15,bp,120,80,mmHg");
  });
  it("gives Muse facts and Muse refuses to guess without them", async () => {
    const f = bodyFacts([R("bp", "2026-11-15", 134, 82), R("sleep", "2026-11-15", 6.5)], today);
    expect(f.lastBp).toMatchObject({ sys: 134, dia: 82 }); expect(f.sleep7).toBe(6.5);
    const base = { mode: "talk" as const, history: [], memory: [], profile: { name: "Nancy", cuisine: [] }, food: { weekProtein: 0, weekDays: 0, weekAlcoholDays: 0, weekCaffeineAvg: 0, todayCalcium: 0, calciumTarget: 1200, proteinTarget: 60 } };
    expect((await reply({ ...base, text: "How is my blood pressure?", body: f })).text).toContain("134/82");
    expect((await reply({ ...base, text: "How have I been sleeping?", body: {} })).text).toMatch(/won't guess/);
  });
});

describe("Guardian logic", () => {
  it("knows local emergency numbers with a safe fallback", () => {
    expect(emergencyNumber("United States")).toBe("911"); expect(emergencyNumber("United Kingdom")).toBe("999");
    expect(emergencyNumber("India")).toBe("112"); expect(emergencyNumber("Atlantis")).toBe("112");
  });
  it("adds location to SOS only when given", () => {
    expect(sosMessage("Bea")).not.toContain("maps.google");
    expect(sosMessage("Bea", { lat: 36.16266, lon: -86.78160, accuracy: 12 })).toContain("maps.google.com/?q=36.16266,-86.78160");
  });
  it("tracks check-in status deterministically", () => {
    const c: CheckIn = { id: "c", time: "21:00", days: [1], graceMin: 30, label: "Evening", enabled: true };
    const mon = (h: number, m = 0) => new Date(2026, 10, 16, h, m);
    expect(checkInStatus(c, [], mon(20))).toBe("upcoming");
    expect(checkInStatus(c, [], mon(21, 10))).toBe("due");
    expect(checkInStatus(c, [], mon(22))).toBe("missed");
    expect(checkInStatus(c, [{ checkInId: "c", date: mon(22).toISOString().slice(0, 10), at: 0, status: "ok" }], mon(22))).toBe("done");
    expect(checkInStatus(c, [], new Date(2026, 10, 17, 22))).toBe("not-today");
  });
  it("lists capabilities that need infrastructure honestly", () => {
    expect(CAPABILITIES.filter((c) => c.status !== "works").length).toBeGreaterThanOrEqual(3);
    expect(CAPABILITIES.find((c) => c.feature.startsWith("SOS"))?.detail).toMatch(/can't confirm delivery/);
  });
  it("builds an emergency card from entered fields only", () => {
    const card = emergencyCard({ ...EMPTY_INFO, fullName: "Nancy", allergies: "Penicillin" }, []);
    expect(card).toContain("Allergies: Penicillin"); expect(card).not.toContain("Blood type");
  });
});

const at = (p: string) => { localStorage.setItem("femora:v1:locations", JSON.stringify({ bea: { region: "North America", city: "Nashville" } }));
  return render(<AppStateProvider><MemoryRouter initialEntries={[p]}><AppRoutes /></MemoryRouter></AppStateProvider>); };

describe("pages", () => {
  it("dashboard saves a record that persists and can be deleted", async () => {
    const u = userEvent.setup();
    const v = at("/app/body");
    await u.type(await screen.findByLabelText("Sleep (hours)", {}, { timeout: 3000 }), "7.5");
    await u.click(screen.getByRole("button", { name: /^Save$/ }));
    expect(JSON.parse(localStorage.getItem("femora:v1:body:bea")!)).toHaveLength(1);
    v.unmount(); at("/app/body");
    await u.click(await screen.findByLabelText(/Delete Sleep on/, {}, { timeout: 3000 }));
    expect(JSON.parse(localStorage.getItem("femora:v1:body:bea")!)).toHaveLength(0);
  });
  it("Guardian shows the emergency call and never claims an SOS was sent", async () => {
    const u = userEvent.setup();
    at("/app/guardian");
    const call = await screen.findByRole("link", { name: /Call 911/ }, { timeout: 3000 });
    expect(call).toHaveAttribute("href", "tel:911");
    await u.type(screen.getByLabelText("Name"), "Sister");
    await u.type(screen.getByLabelText("Mobile (with country code)"), "+1 615 555 0100");
    await u.click(screen.getByRole("button", { name: /Add trusted contact/ }));
    await u.click(screen.getByRole("button", { name: /SOS to my people/ }));
    const sms = screen.getByRole("link", { name: /SMS/ });
    expect(sms.getAttribute("href")).toMatch(/^sms:16155550100/);
    await u.click(sms);
    expect(screen.getAllByRole("status").some((e) => /Draft opened.*can't confirm delivery/.test(e.textContent ?? ""))).toBe(true);
    expect(screen.queryByText(/\b(sent|delivered) successfully\b/i)).toBeNull();
  });
});
