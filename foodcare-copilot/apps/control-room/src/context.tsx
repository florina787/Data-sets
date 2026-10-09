import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { onAuthChange, storedUser, User } from "./api";
import { usePoll } from "./hooks";

type Ctx = {
  user: User | null;
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
