// Forecasting for FEMORA Muse. Two kinds, both honest about uncertainty:
// 1. Population context: trained on real NHANES 2013-2018 data (see femora/ml). Shows how many women of a given age
//    had reached natural menopause. It never predicts an individual's final period.
// 2. Personal cycle forecast: time-series forecast of the next period from HER own logged cycles (exponentially
//    weighted mean, empirical prediction interval, rolling-origin backtest on her history).
import model from "./model.json";
import { cycleLengths, daysBetween, type Period } from "../journey/logic";

export const MODEL = model;

function interp(ages: number[], vals: number[], age: number) {
  if (age <= ages[0]) return vals[0];
  if (age >= ages[ages.length - 1]) return vals[vals.length - 1];
  const i = ages.findIndex((a) => a > age) - 1;
  const t = (age - ages[i]) / (ages[i + 1] - ages[i]);
  return vals[i] + t * (vals[i + 1] - vals[i]);
}

/** Share of U.S. women who had reached natural menopause by this age (survey-weighted KM), with 95% CI. */
export function populationContext(age: number) {
  const k = model.km;
  return { age, reached: interp(k.ages, k.reached, age), lo: interp(k.ages, k.reached_lo, age), hi: interp(k.ages, k.reached_hi, age), medianAge: k.median_age };
}

export interface CycleForecast {
  status: "ok" | "too-few" | "too-irregular";
  nextStart?: string; earliest?: string; latest?: string;
  expectedLength?: number; intervalDays?: number; backtestMAE?: number; backtestN?: number; reason?: string;
}

const addDays = (d: string, n: number) => { const x = new Date(d + "T12:00:00"); x.setDate(x.getDate() + Math.round(n)); return x.toISOString().slice(0, 10); };

/** Exponentially weighted mean of cycle lengths (recent cycles count more). */
export function ewma(lengths: number[], alpha = 0.4) {
  return lengths.reduce((acc, x, i) => (i === 0 ? x : alpha * x + (1 - alpha) * acc), 0);
}

/** Rolling-origin backtest: forecast each cycle from the ones before it. Returns absolute errors. */
export function backtest(lengths: number[], minHistory = 3, alpha = 0.4) {
  const errs: number[] = [];
  for (let i = minHistory; i < lengths.length; i++) errs.push(Math.abs(ewma(lengths.slice(0, i), alpha) - lengths[i]));
  return errs;
}

export function forecastNextPeriod(periods: Period[], alpha = 0.4): CycleForecast {
  const L = cycleLengths(periods).map((c) => c.length);
  if (L.length < 3) return { status: "too-few", reason: "Four or more logged period start dates (3 cycles) are needed." };
  if (Math.max(...L) >= 60 || Math.max(...L) - Math.min(...L.slice(-6)) > 30)
    return { status: "too-irregular", reason: "Your recent cycles vary too much for a reliable forecast, which is common during the menopausal transition." };
  const expected = ewma(L, alpha);
  const errs = backtest(L, 3, alpha);
  const resid = L.map((x, i) => (i === 0 ? 0 : x - ewma(L.slice(0, i), alpha))).slice(1);
  const sd = Math.sqrt(resid.reduce((a, r) => a + r * r, 0) / Math.max(resid.length, 1));
  const half = Math.max(3, Math.round(1.28 * sd)); // ~80% interval, at least ±3 days
  const last = [...periods].sort((a, b) => a.start.localeCompare(b.start)).at(-1)!.start;
  const next = addDays(last, expected);
  return { status: "ok", nextStart: next, earliest: addDays(next, -half), latest: addDays(next, half), expectedLength: Math.round(expected), intervalDays: half,
    backtestMAE: errs.length ? Math.round((errs.reduce((a, b) => a + b, 0) / errs.length) * 10) / 10 : undefined, backtestN: errs.length };
}

export const daysUntil = (d: string, today = new Date().toISOString().slice(0, 10)) => daysBetween(today, d);
