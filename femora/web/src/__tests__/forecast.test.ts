import { describe, expect, it } from "vitest";
import { MODEL, backtest, ewma, forecastNextPeriod, populationContext } from "../modules/forecast/forecast";
import { reply } from "../modules/conversation/router";
import type { Period } from "../modules/journey/logic";

const P = (start: string): Period => ({ id: start, start, flow: "medium" });

describe("trained NHANES model (real data)", () => {
  it("was trained on the documented cohort", () => {
    expect(MODEL.data.cohort_flow.women_in_rhq_files).toBeGreaterThanOrEqual(10000);
    expect(MODEL.data.cohort_flow.analysis_cohort).toBeGreaterThan(4000);
    expect(MODEL.frameworks).toEqual(expect.arrayContaining(["scikit-learn", "lifelines", "statsmodels"]));
  });
  it("has a plausible, monotonic curve with a median near 51", () => {
    expect(MODEL.km.median_age).toBeGreaterThanOrEqual(49); expect(MODEL.km.median_age).toBeLessThanOrEqual(53);
    for (let i = 1; i < MODEL.km.reached.length; i++) expect(MODEL.km.reached[i]).toBeGreaterThanOrEqual(MODEL.km.reached[i - 1]);
  });
  it("interpolates population context with a CI", () => {
    const c = populationContext(51);
    expect(c.reached).toBeGreaterThan(0.3); expect(c.reached).toBeLessThan(0.75);
    expect(c.lo).toBeLessThanOrEqual(c.reached); expect(c.hi).toBeGreaterThanOrEqual(c.reached);
  });
  it("reports that covariates add little beyond age (honest metrics)", () => {
    const m = MODEL.metrics as Record<string, { test_auc?: number }>;
    expect(Math.abs((m.logistic_full.test_auc ?? 0) - (m.age_only_logistic.test_auc ?? 0))).toBeLessThan(0.02);
  });
});

describe("personal cycle forecaster (time series)", () => {
  it("weights recent cycles more", () => expect(ewma([28, 28, 28, 34])).toBeCloseTo(30.4, 1));
  it("backtests on rolling origins", () => expect(backtest([28, 29, 28, 30, 28])).toHaveLength(2));
  it("refuses with too little history", () => expect(forecastNextPeriod([P("2026-09-01"), P("2026-09-29")]).status).toBe("too-few"));
  it("refuses when cycles are too irregular", () => expect(forecastNextPeriod([P("2026-01-01"), P("2026-01-29"), P("2026-04-10"), P("2026-05-08")]).status).toBe("too-irregular"));
  it("forecasts with an interval for regular cycles", () => {
    const f = forecastNextPeriod([P("2026-07-01"), P("2026-07-29"), P("2026-08-27"), P("2026-09-24"), P("2026-10-22")]);
    expect(f.status).toBe("ok"); expect(f.nextStart! > "2026-11-15" && f.nextStart! < "2026-11-23").toBe(true);
    expect(f.earliest! < f.nextStart! && f.latest! > f.nextStart!).toBe(true); expect(f.backtestN).toBe(1);
  });
});

describe("Muse never predicts the final period", () => {
  const base = { mode: "talk" as const, history: [], memory: [], profile: { name: "Nancy", cuisine: [] },
    food: { weekProtein: 0, weekDays: 0, weekAlcoholDays: 0, weekCaffeineAvg: 0, todayCalcium: 0, calciumTarget: 1200, proteinTarget: 60 } };
  it("gives population context, not a personal date", async () => {
    const r = await reply({ ...base, text: "When will I reach menopause?", journey: { cyclesLogged: 0, topSymptoms14d: [], age: 50 } });
    expect(r.text).toMatch(/can predict exactly/); expect(r.text).toContain("51"); expect(r.text).toMatch(/aged 50/);
  });
  it("forecasts the next period only from her logs", async () => {
    const r = await reply({ ...base, text: "When will my next period be?", journey: { cyclesLogged: 0, topSymptoms14d: [], forecast: { status: "too-few" } } });
    expect(r.text).toMatch(/four or more logged period/);
  });
});
