import { createContext, useContext, useEffect, type ReactNode } from "react";
import { PROFILES, DEFAULT_PROFILE, type Profile } from "../data/examples/profiles";
import { DEFAULT_PREFS, decide, applyFeedback, type NotifInput, type NotifPrefs, type NotifCategory, type Delivered } from "../modules/notifications/engine";
import { usePersistent } from "./usePersistent";
import { uid } from "./storage";

export type ThemeMode = "light" | "dark";
export type Preset = "onyx" | "emerald" | "midnight";
export interface Symptom { id: string; profileId: string; name: string; severity: 1 | 2 | 3; at: number; source: "copilot" | "form"; impact?: 0 | 1 | 2 | 3; durationMin?: number; note?: string }
export interface MemoryItem { id: string; profileId: string; text: string; at: number }
export interface Location { region: string; city: string }
export interface Notice { id: string; key: string; category: NotifCategory; title: string; body: string; at: number; read: boolean; link?: string; digest: boolean; feedback?: "useful" | "not-relevant" }
export type SpiritualPref = "spiritual" | "religious" | "secular" | "mindfulness" | "yoga" | "nature" | "none";
export interface JoyItem { id: string; profileId: string; category: string; text: string; at: number }

interface AppState {
  profile: Profile; setProfileId: (id: string) => void;
  theme: ThemeMode; setTheme: (t: ThemeMode) => void; preset: Preset; setPreset: (p: Preset) => void;
  memoryEnabled: boolean; setMemoryEnabled: (b: boolean) => void;
  memory: MemoryItem[]; addMemory: (text: string) => void; removeMemory: (id: string) => void;
  symptoms: Symptom[]; logSymptom: (name: string, severity?: 1 | 2 | 3, source?: Symptom["source"], extra?: Partial<Pick<Symptom, "impact" | "durationMin" | "note" | "at">>) => void; removeSymptom: (id: string) => void;
  location: Location | null; setLocation: (l: Location) => void;
  updateProfile: (patch: Partial<Profile>) => void;
  notices: Notice[]; notify: (n: NotifInput) => void; markAllRead: () => void; dismiss: (id: string) => void;
  snooze: (key: string, minutes: number) => void; feedback: (id: string, useful: boolean) => void;
  prefs: NotifPrefs; setPrefs: (p: NotifPrefs) => void;
  spiritual: SpiritualPref[]; setSpiritual: (s: SpiritualPref[]) => void;
  follows: string[]; toggleFollow: (cat: string) => void;
  joy: JoyItem[]; addJoy: (category: string, text: string) => void; removeJoy: (id: string) => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = usePersistent("profile", () => DEFAULT_PROFILE);
  const [theme, setTheme] = usePersistent<ThemeMode>("theme", () => "light");
  const [preset, setPreset] = usePersistent<Preset>("preset2", () => "onyx");
  const [memoryEnabled, setMemoryEnabled] = usePersistent("memoryEnabled", () => false); // off until the user consents
  const [memoryAll, setMemory] = usePersistent<MemoryItem[]>("memory", () => []);
  const [symptomsAll, setSymptoms] = usePersistent<Symptom[]>("symptoms", () => []);
  const [locations, setLocations] = usePersistent<Record<string, Location>>("locations", () => ({}));
  const [notices, setNotices] = usePersistent<Notice[]>("notices", () => []);
  const [edits, setEdits] = usePersistent<Record<string, Partial<Profile>>>("profileEdits", () => ({}));
  const [prefs, setPrefs] = usePersistent<NotifPrefs>("notifPrefs", () => DEFAULT_PREFS);
  const [delivered, setDelivered] = usePersistent<Delivered[]>("delivered", () => []);
  const [snoozed, setSnoozed] = usePersistent<Record<string, number>>("snoozed", () => ({}));
  const [spiritualAll, setSpiritualAll] = usePersistent<Record<string, SpiritualPref[]>>("spiritual", () => ({}));
  const [follows, setFollows] = usePersistent<string[]>("follows", () => []);
  const [joyAll, setJoy] = usePersistent<JoyItem[]>("joy", () => []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.preset = preset;
  }, [theme, preset]);

  const base = PROFILES.find((p) => p.id === profileId) ?? PROFILES[0];
  const profile: Profile = { ...base, ...edits[base.id] };
  const mine = <T extends { profileId: string }>(xs: T[]) => xs.filter((x) => x.profileId === profile.id);

  const value: AppState = {
    profile, setProfileId, theme, setTheme, preset, setPreset, memoryEnabled, setMemoryEnabled,
    memory: mine(memoryAll),
    addMemory: (text) => setMemory((m) => [...m, { id: uid(), profileId: profile.id, text, at: Date.now() }]),
    removeMemory: (id) => setMemory((m) => m.filter((x) => x.id !== id)),
    symptoms: mine(symptomsAll),
    logSymptom: (name, severity = 2, source = "form", extra = {}) => setSymptoms((s) => [...s, { id: uid(), profileId: profile.id, name, severity, at: Date.now(), source, ...extra }]),
    removeSymptom: (id) => setSymptoms((s) => s.filter((x) => x.id !== id)),
    location: locations[profile.id] ?? null,
    setLocation: (l) => setLocations((m) => ({ ...m, [profile.id]: l })),
    updateProfile: (patch) => setEdits((e) => ({ ...e, [profile.id]: { ...e[profile.id], ...patch } })),
    notices,
    notify: (n) => {
      const d = decide(n, prefs, delivered, new Date(), snoozed);
      if (d.action === "suppress") return;
      setDelivered((h) => [...h.filter((x) => x.at > Date.now() - 7 * 864e5), { key: n.key, category: n.category, at: Date.now() }]);
      setNotices((list) => [{ id: uid(), key: n.key, category: n.category, title: d.title, body: d.body, link: n.link, at: Date.now(), read: false, digest: d.action === "digest" }, ...list].slice(0, 100));
      // Browser notification only for immediate items, only with permission and opt-in; content follows the privacy setting.
      if (d.action === "deliver" && prefs.browserNotifications && typeof Notification !== "undefined" && Notification.permission === "granted") new Notification(d.title, { body: d.body });
    },
    markAllRead: () => setNotices((n) => n.map((x) => ({ ...x, read: true }))),
    dismiss: (id) => setNotices((n) => n.filter((x) => x.id !== id)),
    snooze: (key, minutes) => { setSnoozed((s) => ({ ...s, [key]: Date.now() + minutes * 60000 })); setDelivered((h) => h.filter((x) => x.key !== key)); setNotices((n) => n.filter((x) => x.key !== key)); },
    feedback: (id, useful) => {
      const n = notices.find((x) => x.id === id); if (!n) return;
      const count = notices.filter((x) => x.category === n.category && x.feedback === "not-relevant").length + (useful ? 0 : 1);
      setPrefs(applyFeedback(prefs, n.category, useful, count));
      setNotices((list) => list.map((x) => (x.id === id ? { ...x, feedback: useful ? "useful" : "not-relevant" } : x)));
    },
    prefs, setPrefs,
    spiritual: spiritualAll[profile.id] ?? [],
    setSpiritual: (sp) => setSpiritualAll((m) => ({ ...m, [profile.id]: sp })),
    follows,
    toggleFollow: (cat) => setFollows((f) => (f.includes(cat) ? f.filter((x) => x !== cat) : [...f, cat])),
    joy: mine(joyAll),
    addJoy: (category, text) => setJoy((j) => [...j, { id: uid(), profileId: profile.id, category, text, at: Date.now() }]),
    removeJoy: (id) => setJoy((j) => j.filter((x) => x.id !== id)),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppStateProvider");
  return v;
}
