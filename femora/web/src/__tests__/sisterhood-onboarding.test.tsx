import { describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppStateProvider } from "../lib/app-state";
import { AppRoutes } from "../App";
import { PLACES, filterPlaces, toGeoJSON, geocode } from "../modules/sisterhood/places";
import { ARTICLES, searchHelp } from "../modules/onboarding/help";
import { TOURS, tourStore } from "../modules/onboarding/tours";
import { reply } from "../modules/conversation/router";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("sisterhood registry", () => {
  it("only lists verified, https, dated organisations", () => {
    for (const p of PLACES) { expect(p.url.startsWith("https://")).toBe(true); expect(p.verifiedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/); }
  });
  it("never places markers more precisely than city level, and online entries have none", () => {
    for (const p of PLACES) expect(["country", "city", "region", "online"]).toContain(p.scope);
    expect(PLACES.filter((p) => p.scope === "online").every((p) => p.lat === undefined)).toBe(true);
    expect(toGeoJSON(PLACES).features.length).toBe(PLACES.filter((p) => p.scope !== "online").length);
  });
  it("filters by text, category and cost", () => {
    expect(filterPlaces(PLACES, "india", []).map((p) => p.id)).toEqual(["ims-india"]);
    expect(filterPlaces(PLACES, "", ["Public health"]).every((p) => p.category === "Public health")).toBe(true);
    expect(filterPlaces(PLACES, "", [], true).every((p) => p.free === "free")).toBe(true);
    expect(filterPlaces(PLACES, "french", []).some((p) => p.id === "mfc")).toBe(true);
  });
  it("geocodes only the typed text", async () => {
    const f = vi.fn(async () => new Response(JSON.stringify([{ lat: "36.16", lon: "-86.78", display_name: "Nashville, Tennessee" }])));
    const r = await geocode("Nashville", f as unknown as typeof fetch);
    expect(r).toMatchObject({ lat: 36.16, lon: -86.78 });
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=Nashville");
  });
});

describe("help and tours", () => {
  it("finds the right article for natural questions", () => {
    expect(searchHelp("how do I set a medication reminder")[0].id).toBe("reminders");
    expect(searchHelp("delete my data")[0].id).toBe("privacy");
    expect(searchHelp("log my period")[0].id).toBe("period");
    expect(searchHelp("blood pressure")[0].id).toBe("dashboard");
  });
  it("every article's tour and video exist", () => {
    for (const a of ARTICLES) {
      if (a.tour) expect(TOURS.some((t) => t.id === a.tour)).toBe(true);
      if (a.video) expect(() => readFileSync(resolve(process.cwd(), `public/help/${a.video}.webm`))).not.toThrow();
    }
  });
  it("every tour step targets an element that exists in the source", () => {
    const src = ["src/components/AppShell.tsx", "src/pages/Home.tsx", "src/modules/conversation/CopilotPage.tsx", "src/modules/nutrition/FoodPage.tsx", "src/modules/journey/JourneyPage.tsx",
      "src/modules/reminders/RemindersPage.tsx", "src/modules/body/BodyPage.tsx", "src/modules/guardian/GuardianPage.tsx", "src/modules/sisterhood/SisterhoodPage.tsx"].map((f) => readFileSync(resolve(process.cwd(), f), "utf8")).join("\n");
    for (const t of TOURS) for (const s of t.steps) expect(src).toContain(`data-tour="${s.target}"`);
  });
  it("tour store moves forward, back and stops", () => {
    tourStore.start("food"); expect(tourStore.get().step).toBe(0);
    tourStore.next(); expect(tourStore.get().step).toBe(1);
    tourStore.back(); expect(tourStore.get().step).toBe(0);
    tourStore.stop(); expect(tourStore.get().tour).toBeNull();
  });
  it("Muse answers 'how do I' questions from the help centre with a tour", async () => {
    const r = await reply({ text: "How do I set a medication reminder?", mode: "talk", history: [], memory: [], profile: { name: "Bea", cuisine: [] }, food: { weekProtein: 0, weekDays: 0, weekAlcoholDays: 0, weekCaffeineAvg: 0, todayCalcium: 0, calciumTarget: 1200, proteinTarget: 60 } });
    expect(r.text).toContain("Health planner"); expect(r.actions?.some((a) => a.payload === "/app?tour=planner")).toBe(true);
  });
});

describe("onboarding", () => {
  it("welcomes first-time users and can be skipped", async () => {
    localStorage.removeItem("femora:v1:onboarded");
    const u = userEvent.setup();
    render(<AppStateProvider><MemoryRouter initialEntries={["/app"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    expect(await screen.findByRole("heading", { name: /Welcome, Bea/ })).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Continue/ }));
    expect(screen.getByRole("heading", { name: /Meet your Muse/ })).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Skip" }));
    expect(localStorage.getItem("femora:v1:onboarded")).toBe("true");
  });
  it("finishes with location and launches the home tour", async () => {
    localStorage.removeItem("femora:v1:onboarded");
    const u = userEvent.setup();
    render(<AppStateProvider><MemoryRouter initialEntries={["/app"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    for (let i = 0; i < 4; i++) await u.click(await screen.findByRole("button", { name: /Continue/ }));
    await u.type(screen.getByLabelText("City"), "Nashville");
    await u.click(screen.getByRole("button", { name: /Show me around/ }));
    expect(JSON.parse(localStorage.getItem("femora:v1:locations")!).bea.city).toBe("Nashville");
    await act(async () => { await new Promise((r) => setTimeout(r, 80)); });
    expect(tourStore.get().tour?.id).toBe("home");
    expect(await screen.findByRole("dialog", { name: /Your home: step 1 of 4/ })).toBeInTheDocument();
    act(() => tourStore.stop());
  });
  it("help centre and sisterhood pages render with the list fallback", async () => {
    localStorage.setItem("femora:v1:locations", JSON.stringify({ bea: { region: "North America", city: "Nashville" } }));
    const u = userEvent.setup();
    const v = render(<AppStateProvider><MemoryRouter initialEntries={["/app/help"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    await u.type(await screen.findByPlaceholderText(/Search, e.g./, {}, { timeout: 3000 }), "sos");
    expect(screen.getByText("How do I use Guardian in an emergency?")).toBeInTheDocument();
    v.unmount();
    render(<AppStateProvider><MemoryRouter initialEntries={["/app/sisterhood"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    await u.click(await screen.findByRole("radio", { name: /List/ }, { timeout: 3000 }));
    expect(screen.getAllByText("British Menopause Society").length).toBeGreaterThan(0);
  });
});
