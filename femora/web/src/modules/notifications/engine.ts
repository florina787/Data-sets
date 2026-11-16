// Muse notification engine: deterministic delivery rules. No model decides whether or when to notify.
export type NotifCategory = "health" | "wellbeing" | "community" | "spiritual" | "lifestyle" | "safety" | "joy";
export type Priority = "critical" | "high" | "normal" | "low";

export const CATEGORY_LABEL: Record<NotifCategory, string> = {
  health: "Health (medication, check-ups, screening)", wellbeing: "Wellbeing (walking, yoga, sleep, hydration)", community: "Community & sisterhood",
  spiritual: "Spiritual & personal growth", lifestyle: "Lifestyle, free classes & offers", safety: "Safety", joy: "Joy & encouragement",
};

export interface CategoryPref { enabled: boolean; mode: "immediate" | "digest"; maxPerDay: number }
export interface NotifPrefs {
  categories: Record<NotifCategory, CategoryPref>;
  quietHours: { enabled: boolean; start: string; end: string };   // "22:00"–"07:00"
  privateMedication: boolean;   // hide medication names in notification text
  browserNotifications: boolean;
}

export const DEFAULT_PREFS: NotifPrefs = {
  categories: {
    health: { enabled: true, mode: "immediate", maxPerDay: 12 },
    wellbeing: { enabled: true, mode: "digest", maxPerDay: 2 },
    community: { enabled: true, mode: "digest", maxPerDay: 2 },
    spiritual: { enabled: false, mode: "digest", maxPerDay: 1 },  // off until she chooses spiritual preferences
    lifestyle: { enabled: false, mode: "digest", maxPerDay: 1 },  // commercial content is opt-in
    safety: { enabled: true, mode: "immediate", maxPerDay: 20 },
    joy: { enabled: false, mode: "digest", maxPerDay: 1 },        // uplifting messages only if she approves
  },
  quietHours: { enabled: true, start: "22:00", end: "07:00" },
  privateMedication: true,
  browserNotifications: false,
};

export interface NotifInput { key: string; category: NotifCategory; priority: Priority; title: string; body: string; link?: string; sensitive?: { title: string; body: string } }
export interface Delivered { key: string; category: NotifCategory; at: number }

const mins = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
export function inQuietHours(q: NotifPrefs["quietHours"], now: Date) {
  if (!q.enabled) return false;
  const n = now.getHours() * 60 + now.getMinutes(), s = mins(q.start), e = mins(q.end);
  return s <= e ? n >= s && n < e : n >= s || n < e;
}

export type Decision = { action: "deliver" | "digest" | "suppress"; reason: string; title: string; body: string };

/**
 * Decide what to do with a notification. Rules, in order:
 * duplicate → suppress; snoozed/muted → suppress; critical safety/health always delivers; quiet hours → digest;
 * category disabled → suppress; daily cap reached → digest; digest mode → digest; else deliver.
 */
export function decide(n: NotifInput, prefs: NotifPrefs, history: Delivered[], now: Date, snoozedUntil: Record<string, number> = {}): Decision {
  const text = prefs.privateMedication && n.sensitive ? n.sensitive : { title: n.title, body: n.body };
  const out = (action: Decision["action"], reason: string): Decision => ({ action, reason, ...text });
  if (history.some((h) => h.key === n.key)) return out("suppress", "already delivered");
  if ((snoozedUntil[n.key] ?? 0) > now.getTime()) return out("suppress", "snoozed");
  const cat = prefs.categories[n.category];
  if (n.priority === "critical") return out("deliver", "critical");
  if (!cat.enabled) return out("suppress", "category muted");
  if (inQuietHours(prefs.quietHours, now) && n.priority !== "high") return out("digest", "quiet hours");
  const today = new Date(now); today.setHours(0, 0, 0, 0);
  const sentToday = history.filter((h) => h.category === n.category && h.at >= today.getTime()).length;
  if (sentToday >= cat.maxPerDay) return out("digest", "daily limit reached");
  if (cat.mode === "digest" && n.priority !== "high") return out("digest", "digest mode");
  return out("deliver", "allowed");
}

/** Feedback learning: "not relevant" twice in a category halves its daily limit (min 1); "useful" restores it. */
export function applyFeedback(prefs: NotifPrefs, category: NotifCategory, useful: boolean, notRelevantCount: number): NotifPrefs {
  const c = prefs.categories[category];
  const maxPerDay = useful ? Math.min(DEFAULT_PREFS.categories[category].maxPerDay, c.maxPerDay + 1) : notRelevantCount >= 2 ? Math.max(1, Math.floor(c.maxPerDay / 2)) : c.maxPerDay;
  return { ...prefs, categories: { ...prefs.categories, [category]: { ...c, maxPerDay } } };
}
