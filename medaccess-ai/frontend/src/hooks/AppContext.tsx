import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { endpoints, getToken, setToken, type User, type WorkflowResult } from "../services/api";

interface AppState {
  user: User | null;
  login: (userId: string) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
  lastSearch: WorkflowResult | null;
  setLastSearch: (w: WorkflowResult | null) => void;
  reducedMotion: boolean;
  setReducedMotion: (v: boolean) => void;
  voiceEnabled: boolean;
  setVoiceEnabled: (v: boolean) => void;
  scenario: string | null;
  setScenario: (s: string | null) => void;
}

const Ctx = createContext<AppState | null>(null);
const USER_KEY = "medaccess.user";
const PREF_KEY = "medaccess.ui";

function readJson<T>(storage: () => Storage, key: string, fallback: T): T {
  try {
    const v = storage().getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(storage: () => Storage, key: string, value: unknown) {
  try {
    storage().setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable - UI keeps working in memory */
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => (getToken() ? readJson(() => sessionStorage, USER_KEY, null) : null));
  const [lastSearch, setLastSearch] = useState<WorkflowResult | null>(null);
  const ui = readJson(() => localStorage, PREF_KEY, { reducedMotion: false });
  const [reducedMotion, setReducedMotion] = useState<boolean>(ui.reducedMotion);
  const [voiceEnabled, setVoiceEnabled] = useState(false); // never persisted: opt in each session
  const [scenario, setScenario] = useState<string | null>(null);

  useEffect(() => writeJson(() => localStorage, PREF_KEY, { reducedMotion }), [reducedMotion]);

  const login = useCallback(async (userId: string) => {
    const r = await endpoints.login(userId);
    setToken(r.access_token);
    writeJson(() => sessionStorage, USER_KEY, r.user);
    setUser(r.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    try {
      sessionStorage.removeItem(USER_KEY);
    } catch {
      /* ignore */
    }
    setUser(null);
    setLastSearch(null);
  }, []);

  const value = useMemo<AppState>(
    () => ({
      user, login, logout, can: (p) => !!user?.permissions.includes(p), lastSearch, setLastSearch,
      reducedMotion, setReducedMotion, voiceEnabled, setVoiceEnabled, scenario, setScenario,
    }),
    [user, login, logout, lastSearch, reducedMotion, voiceEnabled, scenario],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp outside AppProvider");
  return c;
}
