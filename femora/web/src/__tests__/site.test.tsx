import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppStateProvider } from "../lib/app-state";
import { AppRoutes } from "../App";
import { DEMO_PREFIX, REAL_PREFIX, isDemo } from "../lib/storage";
import { exitDemo, startDemo } from "../site/demoData";
import { PLANS, noBilling, trialWindow, hasFeature } from "../modules/billing/entitlements";
import { SLIDES, CLIPS } from "../site/media";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const at = (p: string) => render(<AppStateProvider><MemoryRouter initialEntries={[p]}><AppRoutes /></MemoryRouter></AppStateProvider>);

describe("launch site pages", () => {
  for (const [path, h1] of [["/features", /Everything Muse can do/], ["/demo", /Explore Muse with a sample profile/], ["/club", /members' club/], ["/how-it-works", /Six gentle steps/],
    ["/gallery", /See it move/], ["/pricing", /Simple, honest plans/], ["/trust", /Plain answers/]] as const) {
    it(`renders ${path}`, async () => {
      at(path);
      expect(await screen.findByRole("heading", { level: 1, name: h1 }, { timeout: 4000 })).toBeInTheDocument();
      expect(screen.getByText("florinaregius@yahoo.com")).toBeInTheDocument();
    });
  }
  it("uses only real recorded assets that exist", () => {
    for (const s of SLIDES) for (const w of [640, 1280]) expect(existsSync(resolve(process.cwd(), `public/media/shots/${s.shot}-${w}.webp`))).toBe(true);
    for (const c of CLIPS) for (const ext of ["mp4", "webm", "webp"]) expect(existsSync(resolve(process.cwd(), `public/media/clips/${c.id}.${ext}`))).toBe(true);
    expect(CLIPS.every((c) => c.transcript.length > 0)).toBe(true);
  });
  it("carousel has 9 slides with keyboard and button navigation", async () => {
    const u = userEvent.setup();
    at("/");
    const car = screen.getByRole("region", { name: "FEMORA product tour" });
    expect(within(car).getAllByRole("article")).toHaveLength(9);
    await u.click(within(car).getByRole("button", { name: "Next slide" }));
    expect(within(car).getByText(/Slide 2 of 9: Muse AI/)).toBeInTheDocument();
  });
  it("gallery filters clips and never autoplays", async () => {
    const u = userEvent.setup();
    at("/gallery");
    await screen.findByRole("heading", { level: 1, name: /See it move/ }, { timeout: 4000 });
    expect(document.querySelectorAll("video").length).toBe(0);
    await u.click(screen.getByRole("button", { name: "Safety" }));
    expect(screen.getAllByRole("button", { name: /^Play / })).toHaveLength(1);
  });
});

describe("pricing never pretends billing works", () => {
  it("shows no invented prices and no checkout", async () => {
    at("/pricing");
    await screen.findByRole("heading", { level: 1, name: /Simple, honest plans/ }, { timeout: 4000 });
    expect(document.body.textContent).not.toMatch(/[$€£]\s?\d/);
    expect(screen.getByText(noBilling.reason!)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /checkout|subscribe|pay/i })).toBeNull();
  });
  it("billing provider cannot start a trial and plans have no prices yet", async () => {
    expect(noBilling.available).toBe(false);
    expect((await noBilling.startTrial("plus")).ok).toBe(false);
    expect(PLANS.filter((p) => p.id !== "free").every((p) => p.price === "To be announced")).toBe(true);
    expect(hasFeature("free", "hosted-ai")).toBe(false); expect(hasFeature("circle", "circles")).toBe(true);
  });
  it("computes trial dates with a reminder before expiry", () => {
    const w = trialWindow(new Date("2026-11-19T12:00:00"));
    expect(w.end.toISOString().slice(0, 10)).toBe("2026-12-19"); expect(w.reminder.toISOString().slice(0, 10)).toBe("2026-12-16");
  });
});

describe("interactive demo is labelled and isolated", () => {
  it("seeds only the demo namespace and leaves real records untouched", () => {
    localStorage.setItem(REAL_PREFIX + "periods:bea", JSON.stringify([{ id: "real" }]));
    startDemo();
    expect(isDemo()).toBe(true);
    expect(JSON.parse(localStorage.getItem(DEMO_PREFIX + "periods:bea")!).length).toBe(5);
    expect(JSON.parse(localStorage.getItem(REAL_PREFIX + "periods:bea")!)).toEqual([{ id: "real" }]);
    exitDemo();
    expect(isDemo()).toBe(false);
    expect(Object.keys(localStorage).some((k) => k.startsWith(DEMO_PREFIX))).toBe(false);
    expect(localStorage.getItem(REAL_PREFIX + "periods:bea")).not.toBeNull();
  });
  it("shows a demo banner with reset and exit inside the app", async () => {
    startDemo();
    at("/app");
    expect(await screen.findByText(/synthetic sample data for a fictional member/)).toBeInTheDocument();
    expect(screen.getByText(/not a live AI model/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset demo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exit demo" })).toBeInTheDocument();
    exitDemo();
  });
  it("demo profile is clearly fictional", () => {
    startDemo();
    expect(JSON.parse(localStorage.getItem(DEMO_PREFIX + "profileEdits")!).bea.name).toBe("Demo Bea");
    exitDemo();
  });
});

describe("SEO build script", () => {
  it("generates per-page metadata, 404 fallback, sitemap and robots", () => {
    const src = readFileSync(resolve(process.cwd(), "scripts/postbuild.mjs"), "utf8");
    for (const p of ["features", "demo", "club", "how-it-works", "gallery", "pricing", "trust"]) expect(src).toContain(`["${p}"`);
    expect(src).toMatch(/404\.html/); expect(src).toMatch(/sitemap\.xml/); expect(src).toMatch(/robots\.txt/); expect(src).toMatch(/Content-Security-Policy/);
  });
});
