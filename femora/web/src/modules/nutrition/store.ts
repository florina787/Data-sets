import { load, save } from "../../lib/storage";
import type { LogEntry } from "./engine";
import { DEFAULT_TARGETS } from "./engine";
import type { Nutrient } from "./foods";

const key = (profileId: string) => `food:${profileId}`;

export function loadLog(profileId: string): LogEntry[] {
  return load<LogEntry[]>(key(profileId), []); // starts empty: only what she logs
}
export const saveLog = (profileId: string, entries: LogEntry[]) => save(key(profileId), entries);

export const loadTargets = (profileId: string) => ({ ...DEFAULT_TARGETS, ...load<Partial<Record<Nutrient, number>>>(`targets:${profileId}`, {}) });
export const saveTargets = (profileId: string, t: Partial<Record<Nutrient, number>>) => save(`targets:${profileId}`, t);
