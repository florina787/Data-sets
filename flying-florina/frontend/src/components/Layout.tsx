import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, Bot, Boxes, Building2, Cable, FileBarChart, FileCheck2, Gauge, Menu, Moon, Plane, ScanSearch, Settings, ShieldCheck, Sun, Wrench, X, Sparkles, FlaskConical,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { get, post } from "@/lib/api";
import { useSession } from "@/lib/store";
import type { Actor, Persona } from "@/lib/types";
import { BrandMark } from "./Brand";
import { Badge } from "./ui";

export const NAV = [
  { to: "/", label: "Mission Control", icon: Sparkles, hint: "Ask Flying_Florina" },
  { to: "/fleet", label: "Fleet & Asset Health", icon: Plane },
  { to: "/aog", label: "AOG Recovery", icon: Activity },
  { to: "/maintenance", label: "Maintenance & MRO", icon: Wrench },
  { to: "/parts", label: "Parts & Supply Chain", icon: Boxes },
  { to: "/quality", label: "Engineering Quality", icon: Gauge },
  { to: "/legacy", label: "Legacy X-Ray", icon: ScanSearch },
  { to: "/bridge", label: "API & MCP Bridge Studio", icon: Cable },
  { to: "/agents", label: "Agent Mission Control", icon: Bot },
  { to: "/trust", label: "Defense Trust Center", icon: ShieldCheck },
  { to: "/compliance", label: "Compliance Evidence", icon: FileCheck2 },
  { to: "/simulator", label: "Scenario Simulator", icon: FlaskConical },
  { to: "/executive", label: "Executive Value Studio", icon: Building2 },
  { to: "/reports", label: "Reports & Exports", icon: FileBarChart },
  { to: "/settings", label: "Integrations & Settings", icon: Settings },
];

export function useLogin() {
  const setAuth = useSession((s) => s.setAuth);
  const qc = useQueryClient();
  return async (userId: string) => {
    const r = await post<{ token: string; actor: Actor }>("/api/auth/login", { user_id: userId });
    setAuth(r.data.token, r.data.actor);
    // Reset (not clear) so mounted observers refetch with the new identity.
    await qc.resetQueries();
  };
}

function PersonaSelect() {
  const actor = useSession((s) => s.actor);
  const login = useLogin();
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["personas"], queryFn: () => get<Persona[]>("/api/personas") });
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="muted hidden sm:inline">Persona</span>
      <select
        aria-label="Switch persona"
        data-testid="persona-select"
        className="input !py-1 text-xs"
        value={actor?.id ?? ""}
        onChange={async (e) => {
          await login(e.target.value);
          navigate("/");
        }}
      >
        {(data?.data ?? []).map((p) => (
          <option key={p.user_id} value={p.user_id}>
            {p.persona} ({p.user_id})
          </option>
        ))}
      </select>
    </label>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { theme, setTheme, actor } = useSession();
  const [open, setOpen] = useState(false);
  const { data: cfg } = useQuery({ queryKey: ["config"], queryFn: () => get<{ demo_mode: boolean; offline_mode: boolean; llm_enabled: boolean; inference: string }>("/api/config") });
  const c = cfg?.data;
  return (
    <div className={theme === "dark" ? "dark" : ""}>
      <div className="flex min-h-screen bg-[var(--bg)] text-[var(--text)]">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-gold focus:p-2 focus:text-navy">
          Skip to content
        </a>
        <aside
          className={`fixed inset-y-0 left-0 z-40 w-64 transform border-r border-token bg-navy text-offwhite transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
          aria-label="Primary"
        >
          <div className="flex items-center gap-3 px-4 py-4">
            <BrandMark size={40} />
            <div>
              <div className="text-base font-bold tracking-tight">Flying_Florina</div>
              <div className="text-[10px] leading-tight text-lavender">Industrial AI Command Center</div>
            </div>
            <button className="ml-auto lg:hidden" onClick={() => setOpen(false)} aria-label="Close navigation">
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex flex-col gap-0.5 px-2 pb-4">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${isActive ? "bg-purple text-white" : "text-offwhite/80 hover:bg-white/10 hover:text-white"}`
                }
              >
                <n.icon className="h-4 w-4 shrink-0" aria-hidden />
                <span>{n.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="px-4 pb-4 text-[10px] text-offwhite/60">
            From legacy systems to trusted industrial intelligence.
            <br />
            Ask. Analyze. Modernize. Govern. Act—with approval.
          </div>
        </aside>
        {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-token bg-[var(--panel)]/95 px-4 py-2 backdrop-blur">
            <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </button>
            <div className="flex flex-wrap items-center gap-1.5" aria-label="Environment indicators">
              <Badge tone="gold">SYNTHETIC DATA</Badge>
              {c?.demo_mode && <Badge tone="purple">DEMO MODE</Badge>}
              <Badge tone="amber">NO LIVE IFS CONNECTION</Badge>
              <Badge tone="teal">{c?.llm_enabled ? "LOCAL INFERENCE" : "LOCAL RULES ENGINE"}</Badge>
              {c?.offline_mode && <Badge tone="gray">OFFLINE MODE</Badge>}
            </div>
            <div className="ml-auto flex items-center gap-3">
              <PersonaSelect />
              {actor && (
                <span className="muted hidden text-xs md:inline" data-testid="actor">
                  {actor.display_name} · {actor.role}
                </span>
              )}
              <button className="btn btn-ghost !p-1.5" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode">
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
            </div>
          </header>
          <main id="main" className="mx-auto w-full max-w-[1500px] flex-1 p-4 md:p-6">
            {children}
          </main>
          <footer className="muted border-t border-token px-6 py-3 text-center text-[11px]">
            Independent concept demo | Not affiliated with or endorsed by IFS · All data synthetic and fictional · No certification claimed
          </footer>
        </div>
      </div>
    </div>
  );
}
