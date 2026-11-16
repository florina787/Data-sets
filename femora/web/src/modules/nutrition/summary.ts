import { dayKey, addDays } from "../../lib/storage";
import { totals, type LogEntry } from "./engine";
import { loadLog, loadTargets } from "./store";
import type { ReplyContext } from "../conversation/types";

/** Deterministic facts the copilot is allowed to quote about food. */
export function foodFacts(profileId: string, today = new Date()): ReplyContext["food"] {
  const log = loadLog(profileId);
  const targets = loadTargets(profileId);
  const days = Array.from({ length: 7 }, (_, i) => dayKey(addDays(today, -i)));
  const byDay = (d: string) => log.filter((e: LogEntry) => e.date === d);
  const logged = days.filter((d) => byDay(d).length);
  const week = totals(log.filter((e) => days.includes(e.date)));
  return {
    weekProtein: week.values.protein,
    weekDays: logged.length,
    weekAlcoholDays: logged.filter((d) => totals(byDay(d)).values.alcohol > 0).length,
    weekCaffeineAvg: logged.length ? week.values.caffeine / logged.length : 0,
    todayCalcium: totals(byDay(dayKey(today))).values.calcium,
    calciumTarget: targets.calcium ?? 1200,
    proteinTarget: targets.protein ?? 60,
  };
}
