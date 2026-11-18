import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokenStore } from "./api";
import type { Lang } from "./i18n";

export type Me = {
  user_id: string; display_name: string; title: string; tenant_id: string; roles: string[]; advisor_id: string | null;
  clearance: string; permissions: string[]; navigation: { id: string; label: string }[]; data_as_of: string; dataset_version: string;
};
export type AskContext = { chart_id?: string; page?: string; client_id?: string; portfolio_id?: string; question?: string; title?: string };
type Filters = { months: 12 | 24; asset_class: string; vehicle: string };

type AppState = {
  me: Me | null; loading: boolean; login: (u: string) => Promise<void>; logout: () => void; can: (p: string) => boolean;
  lang: Lang; setLang: (l: Lang) => void; theme: "dark" | "light"; toggleTheme: () => void;
  askOpen: boolean; ask: (c?: AskContext) => void; closeAsk: () => void; askCtx: AskContext;
  filters: Filters; setFilters: (f: Partial<Filters>) => void;
};
const Ctx = createContext<AppState>(null as unknown as AppState);
export const useApp = () => useContext(Ctx);

const read = <T,>(k: string, d: T): T => {
  try {
    const v = localStorage.getItem(k);
    return v ? (JSON.parse(v) as T) : d;
  } catch {
    return d;
  }
};
const write = (k: string, v: unknown) => {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* storage unavailable */
  }
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [lang, setLangS] = useState<Lang>(read("flo.lang", "en"));
  const [theme, setTheme] = useState<"dark" | "light">(read("flo.theme", "dark"));
  const [askOpen, setAskOpen] = useState(false);
  const [askCtx, setAskCtx] = useState<AskContext>({});
  const [filters, setF] = useState<Filters>({ months: 12, asset_class: "", vehicle: "" });

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api<Me>("/api/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
    const h = () => setMe(null);
    window.addEventListener("flo:logout", h);
    return () => window.removeEventListener("flo:logout", h);
  }, [refresh]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    write("flo.theme", theme);
  }, [theme]);

  const value: AppState = {
    me, loading,
    login: async (u) => {
      const r = await api<{ access_token: string }>("/api/auth/login", { method: "POST", json: { user_id: u } });
      tokenStore.set(r.access_token);
      setLoading(true);
      await refresh();
    },
    logout: () => {
      tokenStore.clear();
      setMe(null);
    },
    can: (p) => !!me?.permissions.includes(p),
    lang, setLang: (l) => { setLangS(l); write("flo.lang", l); },
    theme, toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    askOpen, ask: (c = {}) => { setAskCtx(c); setAskOpen(true); }, closeAsk: () => setAskOpen(false), askCtx,
    filters, setFilters: (f) => setF((x) => ({ ...x, ...f })),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
