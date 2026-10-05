"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/types/api";

interface AppState {
  userId: string;
  setUserId: (id: string) => void;
  matterId: string;
  setMatterId: (id: string) => void;
  users: User[];
  user: User | undefined;
  apiStatus: "checking" | "online" | "offline";
  demoMode: boolean | null;
}

const Ctx = createContext<AppState | null>(null);
const read = (k: string, d: string) => {
  try { return (typeof window !== "undefined" && window.localStorage.getItem(k)) || d; } catch { return d; }
};
const write = (k: string, v: string) => { try { window.localStorage.setItem(k, v); } catch { /* storage unavailable */ } };

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserIdState] = useState("U-002");
  const [matterId, setMatterIdState] = useState("M-1001");
  const [users, setUsers] = useState<User[]>([]);
  const [apiStatus, setApiStatus] = useState<AppState["apiStatus"]>("checking");
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

  useEffect(() => {
    setUserIdState(read("lexguard.user", "U-002"));
    setMatterIdState(read("lexguard.matter", "M-1001"));
    api.health().then((h) => { setApiStatus("online"); setDemoMode(h.demo_mode); }).catch(() => setApiStatus("offline"));
    api.users().then(setUsers).catch(() => setUsers([]));
  }, []);

  const setUserId = useCallback((id: string) => { setUserIdState(id); write("lexguard.user", id); }, []);
  const setMatterId = useCallback((id: string) => { setMatterIdState(id); write("lexguard.matter", id); }, []);
  const value = useMemo(() => ({ userId, setUserId, matterId, setMatterId, users, user: users.find((u) => u.user_id === userId),
    apiStatus, demoMode }), [userId, setUserId, matterId, setMatterId, users, apiStatus, demoMode]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAppState must be used inside AppStateProvider");
  return v;
}
