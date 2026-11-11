import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { onAuthChange, storedUser, User } from "./api";
import { usePoll } from "./hooks";

/** Shared geographic selection: survives page navigation and reloads (mirrored to ?geo=). */
export type GeoSel = { country?: string; node?: string; incident?: string };

export function geoToParam(g: GeoSel): string {
  return [g.country && `c:${g.country}`, g.node && `n:${g.node}`, g.incident && `i:${g.incident}`].filter(Boolean).join("|");
}

export function geoFromParam(v: string | null): GeoSel {
  const out: GeoSel = {};
  for (const part of (v ?? "").split("|")) {
    const [k, val] = [part.slice(0, 2), part.slice(2)];
    if (!val || !/^[\w-]{1,24}$/.test(val)) continue;
    if (k === "c:") out.country = val;
    if (k === "n:") out.node = val;
    if (k === "i:") out.incident = val;
  }
  return out;
}

type Ctx = {
  user: User | null;
  geo: GeoSel;
  setGeo: (g: GeoSel) => void;
  runId: string | null;
  setRunId: (id: string | null) => void;
  runs: any[];
  system: any;
  demo: any;
  refreshAll: () => void;
};

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(storedUser());
  const [chosen, setChosen] = useState<string | null>(null);
  const runs = usePoll<{ runs: any[] }>("/api/runs", 4000);
  const system = usePoll<any>("/api/system", 4000);
  const demo = usePoll<any>("/api/demo", 2000);

  useEffect(() => onAuthChange(setUser), []);

  const location = useLocation();
  const navigate = useNavigate();
  const [geo, setGeo] = useState<GeoSel>(() => geoFromParam(new URLSearchParams(location.search).get("geo")));
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const want = geoToParam(geo);
    if ((params.get("geo") ?? "") === want) return;
    if (want) params.set("geo", want);
    else params.delete("geo");
    const search = params.toString();
    navigate({ pathname: location.pathname, search: search ? `?${search}` : "", hash: location.hash }, { replace: true });
  }, [geo, location.pathname, location.search]);

  // Each completed guided-demo step can change releases, faults and runs: refresh them.
  const progress = `${demo.data?.status}:${(demo.data?.steps ?? []).filter((x: any) => x.status === "done").length}`;
  useEffect(() => {
    runs.refresh();
    system.refresh();
  }, [progress]);

  const list = runs.data?.runs ?? [];
  const runId = chosen && list.some((r) => r.id === chosen) ? chosen : demo.data?.run_id ?? list[0]?.id ?? null;

  return (
    <AppContext.Provider
      value={{
        user,
        geo,
        setGeo,
        runId,
        setRunId: setChosen,
        runs: list,
        system: system.data,
        demo: demo.data,
        refreshAll: () => {
          runs.refresh();
          system.refresh();
          demo.refresh();
        },
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("AppProvider missing");
  return ctx;
}

export const ROLE_CAN: Record<string, string[]> = {
  "brief.submit": ["marketing"],
  "clarification.decide": ["marketing", "product_owner"],
  "requirements.approve": ["product_owner"],
  "run.advance": ["engineer", "product_owner", "marketing"],
  "run.control": ["engineer"],
  "release.approve": ["release_approver"],
  "release.deploy": ["release_approver"],
  "release.rollback": ["release_approver"],
  "incident.manage": ["engineer"],
  "fault.inject": ["engineer"],
  "traffic.generate": ["engineer"],
  "demo.control": ["engineer", "release_approver", "product_owner", "marketing"],
};

/** UI hint only; the server enforces the same rules and records rejected attempts. */
export function can(user: User | null, action: string): boolean {
  return !!user && (ROLE_CAN[action] ?? []).includes(user.role);
}

export function roleHint(action: string): string {
  return `Requires role: ${(ROLE_CAN[action] ?? []).join(" or ")}. The server enforces this too.`;
}
