import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Currency = "USD" | "INR" | "CAD";
export type DataClass = "synthetic" | "measured";
export type PeriodKind = "month" | "quarter" | "year" | "ttm";
export type Role = "SHERIN_MANAGER" | "RISK_OFFICER" | "COMPLIANCE_OFFICER" | "PORTFOLIO_MANAGER" | "ENGINEER" | "VIEWER";

export interface AppState {
  currency: Currency; setCurrency: (c: Currency) => void;
  dc: DataClass; setDc: (d: DataClass) => void;
  periodKind: PeriodKind; setPeriodKind: (p: PeriodKind) => void;
  month: string; setMonth: (m: string) => void;
  role: Role; setRole: (r: Role) => void;
  user: string; setUser: (u: string) => void;
}

const Ctx = createContext<AppState | null>(null);

function load<T>(k: string, d: T): T {
  try { const v = localStorage.getItem(`sherin.${k}`); return v ? (JSON.parse(v) as T) : d; } catch { return d; }
}
function save(k: string, v: unknown) { try { localStorage.setItem(`sherin.${k}`, JSON.stringify(v)); } catch { /* storage unavailable */ } }

export const DEFAULT_MONTH = "2026-10";

export function AppProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrency] = useState<Currency>(() => load("currency", "USD"));
  const [dc, setDc] = useState<DataClass>(() => load("dc", "synthetic"));
  const [periodKind, setPeriodKind] = useState<PeriodKind>(() => load("periodKind", "month"));
  const [month, setMonth] = useState<string>(() => load("month", DEFAULT_MONTH));
  const [role, setRole] = useState<Role>(() => load("role", "SHERIN_MANAGER"));
  const [user, setUser] = useState<string>(() => load("user", "mgr.sherin"));
  useEffect(() => { save("currency", currency); save("dc", dc); save("periodKind", periodKind); save("month", month); save("role", role); save("user", user); },
    [currency, dc, periodKind, month, role, user]);
  useEffect(() => { identity.role = role; identity.user = user; }, [role, user]);
  const v = useMemo(() => ({ currency, setCurrency, dc, setDc, periodKind, setPeriodKind, month, setMonth, role, setRole, user, setUser }),
    [currency, dc, periodKind, month, role, user]);
  identity.role = role; identity.user = user;
  return <Ctx.Provider value={v}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}

/** Module-level identity so the API client can send headers without prop drilling. */
export const identity: { role: Role; user: string } = { role: "SHERIN_MANAGER", user: "mgr.sherin" };

export function periodParams(s: Pick<AppState, "periodKind" | "month" | "currency" | "dc">): Record<string, string> {
  return { period: s.periodKind, value: s.month, currency: s.currency, dc: s.dc };
}
export function trendParams(s: Pick<AppState, "month" | "currency" | "dc">): Record<string, string> {
  return { period: "ttm", value: s.month, currency: s.currency, dc: s.dc };
}
