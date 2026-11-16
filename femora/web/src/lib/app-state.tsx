import { createContext, useContext, useEffect, type ReactNode } from "react";
import { PROFILES, DEFAULT_PROFILE, type Profile } from "../data/demo/profiles";
import { usePersistent } from "./usePersistent";
import { uid } from "./storage";

export type ThemeMode = "light" | "dark";
export type Preset = "sky" | "forest" | "indigo";
export interface Symptom { id: string; profileId: string; name: string; severity: 1 | 2 | 3; at: number; source: "copilot" | "form" }
export interface MemoryItem { id: string; profileId: string; text: string; at: number }
export interface Location { region: string; city: string }
export interface Notice { id: string; title: string; body: string; at: number; read: boolean; link?: string }
export interface JoyItem { id: string; profileId: string; category: string; text: string; at: number }

interface AppState {
  profile: Profile; setProfileId: (id: string) => void;
  theme: ThemeMode; setTheme: (t: ThemeMode) => void; preset: Preset; setPreset: (p: Preset) => void;
  memoryEnabled: boolean; setMemoryEnabled: (b: boolean) => void;
  memory: MemoryItem[]; addMemory: (text: string) => void; removeMemory: (id: string) => void;
  symptoms: Symptom[]; logSymptom: (name: string, severity?: 1 | 2 | 3, source?: Symptom["source"]) => void;
  location: Location | null; setLocation: (l: Location) => void;
  notices: Notice[]; notify: (title: string, body: string, link?: string) => void; markAllRead: () => void;
  follows: string[]; toggleFollow: (cat: string) => void;
  joy: JoyItem[]; addJoy: (category: string, text: string) => void; removeJoy: (id: string) => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = usePersistent("profile", () => DEFAULT_PROFILE);
  const [theme, setTheme] = usePersistent<ThemeMode>("theme", () => "light");
  const [preset, setPreset] = usePersistent<Preset>("preset", () => "sky");
  const [memoryEnabled, setMemoryEnabled] = usePersistent("memoryEnabled", () => false); // off until the user consents
  const [memoryAll, setMemory] = usePersistent<MemoryItem[]>("memory", () => []);
  const [symptomsAll, setSymptoms] = usePersistent<Symptom[]>("symptoms", () => []);
  const [locations, setLocations] = usePersistent<Record<string, Location>>("locations", () => ({}));
  const [notices, setNotices] = usePersistent<Notice[]>("notices", () => []);
  const [follows, setFollows] = usePersistent<string[]>("follows", () => []);
  const [joyAll, setJoy] = usePersistent<JoyItem[]>("joy", () => []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.preset = preset;
  }, [theme, preset]);

  const profile = PROFILES.find((p) => p.id === profileId) ?? PROFILES[0];
  const mine = <T extends { profileId: string }>(xs: T[]) => xs.filter((x) => x.profileId === profile.id);

  const value: AppState = {
    profile, setProfileId, theme, setTheme, preset, setPreset, memoryEnabled, setMemoryEnabled,
    memory: mine(memoryAll),
    addMemory: (text) => setMemory((m) => [...m, { id: uid(), profileId: profile.id, text, at: Date.now() }]),
    removeMemory: (id) => setMemory((m) => m.filter((x) => x.id !== id)),
    symptoms: mine(symptomsAll),
    logSymptom: (name, severity = 2, source = "form") => setSymptoms((s) => [...s, { id: uid(), profileId: profile.id, name, severity, at: Date.now(), source }]),
    location: locations[profile.id] ?? null,
    setLocation: (l) => setLocations((m) => ({ ...m, [profile.id]: l })),
    notices,
    notify: (title, body, link) => {
      setNotices((n) => [{ id: uid(), title, body, link, at: Date.now(), read: false }, ...n].slice(0, 50));
      // Real browser notification when permitted (fires while the app is open; push delivery is a production feature).
      if (typeof Notification !== "undefined" && Notification.permission === "granted") new Notification(title, { body });
    },
    markAllRead: () => setNotices((n) => n.map((x) => ({ ...x, read: true }))),
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
