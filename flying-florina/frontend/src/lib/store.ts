import { create } from "zustand";
import type { Actor } from "./types";

type Theme = "light" | "dark";

function readTheme(): Theme {
  try {
    const t = localStorage.getItem("ff-theme");
    if (t === "light" || t === "dark") return t;
  } catch {
    /* storage unavailable */
  }
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

type SessionState = {
  token: string | null;
  actor: Actor | null;
  sessionId: string | null;
  runIds: string[];
  theme: Theme;
  expired: boolean;
  setAuth: (token: string, actor: Actor) => void;
  expire: () => void;
  setSession: (id: string | null) => void;
  pushRun: (id: string) => void;
  resetRuns: () => void;
  setTheme: (t: Theme) => void;
};

export const useSession = create<SessionState>((set) => ({
  token: null,
  actor: null,
  sessionId: null,
  runIds: [],
  theme: readTheme(),
  expired: false,
  setAuth: (token, actor) => {
    try {
      sessionStorage.setItem("ff-user", actor.id);
    } catch {
      /* ignore */
    }
    set({ token, actor, expired: false, sessionId: null, runIds: [] });
  },
  expire: () => set({ expired: true }),
  setSession: (id) => set({ sessionId: id }),
  pushRun: (id) => set((s) => ({ runIds: s.runIds.includes(id) ? s.runIds : [...s.runIds, id] })),
  resetRuns: () => set({ runIds: [], sessionId: null }),
  setTheme: (theme) => {
    try {
      localStorage.setItem("ff-theme", theme);
    } catch {
      /* ignore */
    }
    set({ theme });
  },
}));

export function rememberedUser(): string {
  try {
    return sessionStorage.getItem("ff-user") ?? "planner.marco";
  } catch {
    return "planner.marco";
  }
}
