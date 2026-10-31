import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity, Bot, Boxes, BrainCircuit, Building2, Cable, FileBarChart, FileCheck2, FlaskConical, Gauge, Gauge as GaugeIcon, LayoutDashboard, Menu, Moon,
  Plane, Radar, ScanSearch, Settings, ShieldCheck, Sparkles, Sun, Wrench, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { get, post } from "@/lib/api";
import { useSession } from "@/lib/store";
import type { Actor, Persona } from "@/lib/types";
import { BrandMark } from "./Brand";
import { Badge } from "./ui";

/** Twelve primary sections (Flying_Florina 2.0). Every pre-2.0 route still works and is listed under Workspace. */
export const NAV = [
  { to: "/command", label: "Executive Command Center", icon: LayoutDashboard },
  { to: "/", label: "Flying_Florina AI Assistant", icon: Sparkles },
  { to: "/aog", label: "Aircraft Recovery Intelligence", icon: Activity },
  { to: "/predictive", label: "Predictive Maintenance", icon: Radar },
  { to: "/fleet", label: "Fleet Readiness", icon: Plane },
  { to: "/parts", label: "Spare Parts Intelligence", icon: Boxes },
  { to: "/legacy", label: "Legacy X-Ray", icon: ScanSearch },
  { to: "/agents", label: "Multi-Agent Operations", icon: Bot },
  { to: "/trust", label: "Governance & Compliance", icon: ShieldCheck },
  { to: "/simulator", label: "Simulation & ROI", icon: FlaskConical },
  { to: "/bridge", label: "Integrations & MCP", icon: Cable },
  { to: "/observability", label: "Evaluation & Observability", icon: GaugeIcon },
];
export const NAV_MORE = [
  { to: "/maintenance", label: "Maintenance & MRO", icon: Wrench },
  { to: "/quality", label: "Engineering Quality", icon: Gauge },
  { to: "/compliance", label: "Compliance Evidence", icon: FileCheck2 },
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

type LlmStatus = { available: boolean; mode: string; label: string; required?: boolean; discovery: { found: boolean; model: string | null; quantization: string | null; runtime: string | null; reason: string } };

function QwenIndicator() {
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["llm-status"], queryFn: () => get<LlmStatus>("/api/llm/status"), refetchInterval: 30_000 });
  const s = data?.data;
  const ok = s?.available;
  const label = !s ? "Checking Local Qwen…" : ok ? `Local Qwen · ${s.discovery.model}${s.discovery.quantization ? ` · ${s.discovery.quantization}` : ""}` : s.mode === "off" ? "Local Qwen · off" : s.required ? "Local Qwen · required, not reachable" : "Local Qwen · not found";
  const title = !s ? "" : ok ? `Your local Qwen model answers via ${s.discovery.runtime}. No cloud or paid inference.` : s.discovery.reason;
  return (
    <button onClick={() => navigate("/observability")} title={title} data-testid="qwen-indicator" aria-label={`Model status: ${label}`}
      className="flex shrink-0 items-center gap-2 rounded-full border border-token bg-white/[0.03] px-2 py-1.5 text-xs muted hover:text-[var(--text)] sm:px-3">
      <span className={`h-2 w-2 rounded-full ${!s ? "bg-faint" : ok ? "bg-pos shadow-[0_0_10px_#34D399]" : s.required ? "bg-neg shadow-[0_0_10px_#F87171]" : "bg-warn"}`} />
      <BrainCircuit className="hidden h-3.5 w-3.5 sm:block" aria-hidden />
      <span className="hidden max-w-[260px] truncate sm:inline">{label}</span>
    </button>
  );
}

function PersonaSelect() {
  const actor = useSession((s) => s.actor);
  const login = useLogin();
  const navigate = useNavigate();
  const { data } = useQuery({ queryKey: ["personas"], queryFn: () => get<Persona[]>("/api/personas") });
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="sr-only">Persona</span>
      <select aria-label="Switch persona" data-testid="persona-select" className="input !rounded-full !py-1 max-w-[7.5rem] text-xs sm:max-w-none" value={actor?.id ?? ""}
        onChange={async (e) => { await login(e.target.value); navigate("/"); }}>
        {(data?.data ?? []).map((p) => <option key={p.user_id} value={p.user_id}>{p.persona} ({p.user_id})</option>)}
      </select>
    </label>
  );
}

function NavItem({ to, label, icon: Icon, onClick }: { to: string; label: string; icon: typeof Sparkles; onClick?: () => void }) {
  return (
    <NavLink to={to} end={to === "/"} onClick={onClick}
      className={({ isActive }) => `relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors ${isActive ? "text-[var(--text)]" : "muted hover:bg-white/[0.03] hover:text-[var(--text)]"}`}>
      {({ isActive }) => (
        <>
          {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl border border-indigo/25 bg-gradient-to-r from-indigo/15 to-transparent"
            transition={{ type: "spring", stiffness: 400, damping: 34 }} />}
          <Icon className={`relative h-4 w-4 shrink-0 ${isActive ? "text-cyan" : ""}`} aria-hidden />
          <span className="relative">{label}</span>
        </>
      )}
    </NavLink>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { theme, setTheme, actor } = useSession();
  const [open, setOpen] = useState(false);
  const { data: cfg } = useQuery({ queryKey: ["config"], queryFn: () => get<{ demo_mode: boolean; offline_mode: boolean }>("/api/config") });
  const c = cfg?.data;
  const nav = (onClick?: () => void) => (
    <nav aria-label="Primary" className="flex flex-col gap-0.5">
      {NAV.map((n) => <NavItem key={n.to} {...n} onClick={onClick} />)}
      <p className="label mt-4 px-3 pb-1">Workspace</p>
      {NAV_MORE.map((n) => <NavItem key={n.to} {...n} onClick={onClick} />)}
    </nav>
  );
  return (
    <div className={theme === "dark" ? "dark" : ""}>
      <div className="app-bg flex min-h-screen flex-col text-[var(--text)]">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded focus:bg-indigo focus:p-2 focus:text-white">Skip to content</a>
        <header className="sticky top-0 z-30 border-b border-token bg-[var(--bg)]/75 backdrop-blur-xl">
          <div className="mx-auto flex h-14 max-w-[1680px] items-center gap-2 px-3 sm:gap-3 sm:px-4">
            <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
            <NavLink to="/" className="flex items-center gap-2.5 rounded-lg">
              <BrandMark size={30} />
              <div className="leading-tight">
                <p className="text-sm font-semibold tracking-tight">Flying_Florina</p>
                <p className="hidden text-[10px] uppercase tracking-[0.14em] text-faint sm:block">Aerospace &amp; Defense Intelligence Copilot</p>
              </div>
            </NavLink>
            <div className="ml-4 hidden flex-wrap items-center gap-1.5 xl:flex" aria-label="Environment indicators">
              <Badge tone="gold">SYNTHETIC DATA</Badge>
              {c?.demo_mode && <Badge tone="purple">DEMO MODE</Badge>}
              <Badge tone="amber">NO LIVE IFS CONNECTION</Badge>
              {c?.offline_mode && <Badge tone="gray">OFFLINE MODE</Badge>}
            </div>
            <div className="ml-auto flex min-w-0 items-center gap-1.5 sm:gap-2">
              <QwenIndicator />
              <PersonaSelect />
              {actor && <span className="muted hidden text-xs 2xl:inline" data-testid="actor">{actor.display_name} · {actor.role}</span>}
              {!actor && <span data-testid="actor" />}
              <button className="btn btn-ghost !rounded-full !p-1.5" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode">
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </header>
        <div className="mx-auto flex w-full max-w-[1680px] flex-1">
          <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-64 shrink-0 flex-col overflow-y-auto border-r border-token px-3 py-5 lg:flex">
            {nav()}
            <div className="mt-auto rounded-xl border border-token bg-white/[0.02] p-3 text-[11px] leading-relaxed text-faint">
              Decision support, not decisions. Numbers come from deterministic analytics; local Qwen explains them; humans approve every consequential action.
            </div>
          </aside>
          {open && (
            <div className="fixed inset-0 z-40 lg:hidden">
              <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} aria-hidden />
              <aside className="absolute inset-y-0 left-0 w-72 overflow-y-auto border-r border-token bg-[var(--bg)] px-3 py-4" aria-label="Mobile navigation">
                <button className="mb-3 ml-auto block" onClick={() => setOpen(false)} aria-label="Close navigation"><X className="h-5 w-5" /></button>
                {nav(() => setOpen(false))}
              </aside>
            </div>
          )}
          <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
        <footer className="border-t border-token px-6 py-3 text-center text-[11px] text-faint">
          Independent concept demo | Not affiliated with or endorsed by IFS · All data synthetic and fictional · Local inference only · No certification claimed
        </footer>
      </div>
    </div>
  );
}
