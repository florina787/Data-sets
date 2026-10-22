import { motion } from "framer-motion";
import {
  Activity, BookText, BrainCircuit, Gauge, HeartHandshake, LayoutDashboard, MessagesSquare, Network, Plus, ShieldCheck, Sparkles, Waves,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { cn } from "@/lib/utils";
import { Button, Tip } from "./ui";

export const NAV = [
  { to: "/", label: "Ask Intelligence", icon: Sparkles },
  { to: "/leadership", label: "Leadership Command", icon: LayoutDashboard },
  { to: "/sentiment", label: "Sentiment Intelligence", icon: Waves },
  { to: "/coaching", label: "Agent Coaching", icon: HeartHandshake },
  { to: "/explorer", label: "Conversation Explorer", icon: MessagesSquare },
  { to: "/harness", label: "Agent Harness", icon: Network },
  { to: "/prompts", label: "Prompt Library", icon: BookText },
  { to: "/metrics", label: "System Metrics", icon: Gauge },
  { to: "/governance", label: "Governance", icon: ShieldCheck },
];

function ModelIndicator() {
  const { model, refreshModel } = useApp();
  const ok = model?.available;
  const label = !model ? "Checking model…" : ok ? `Gemini · ${model.model}` : "Deterministic mode";
  const detail = !model ? "" : ok ? "Gemini is reachable; explanations and intent use the model with deterministic checks."
    : `Gemini unavailable${model.reason ? `: ${model.reason.slice(0, 160)}` : ""}. Analytics, retrieval and memory work; answers use the deterministic explainer.`;
  return (
    <Tip content={<span>{detail} <br /><span className="text-muted">Click to re-check.</span></span>}>
      <button onClick={refreshModel} className="focus-ring flex items-center gap-2 rounded-full border border-line bg-white/[0.03] px-3 py-1.5 text-xs text-muted hover:text-ink"
        aria-label={`Model status: ${label}`}>
        <span className={cn("h-2 w-2 rounded-full", !model ? "bg-faint" : ok ? "bg-pos shadow-[0_0_10px_#34D399]" : "bg-warn")} />
        <BrainCircuit className="h-3.5 w-3.5" aria-hidden />
        <span className="hidden sm:inline">{label}</span>
      </button>
    </Tip>
  );
}

function DatasetIndicator() {
  const { health, datasetMode } = useApp();
  const db = health?.checks?.find((c: any) => c.check === "analytics_database");
  const idx = health?.checks?.find((c: any) => c.check === "retrieval_index");
  return (
    <Tip content={<span>Analytics DB: {db?.detail ?? "…"}<br />Retrieval: {idx?.detail ?? "…"}</span>}>
      <div className="hidden items-center gap-2 rounded-full border border-line bg-white/[0.03] px-3 py-1.5 text-xs text-muted md:flex" tabIndex={0}>
        <Activity className={cn("h-3.5 w-3.5", db?.status === "ok" ? "text-cyan" : "text-neg")} aria-hidden />
        <span>Syncora sample · {datasetMode}</span>
      </div>
    </Tip>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { newSession, sessionId } = useApp();
  const loc = useLocation();
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-bg/75 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4">
          <NavLink to="/" className="focus-ring flex items-center gap-2.5 rounded-lg">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <div className="leading-tight">
              <p className="text-sm font-semibold tracking-tight">Conversation Intelligence</p>
              <p className="text-[10px] uppercase tracking-[0.14em] text-faint">Copilot for contact centres</p>
            </div>
          </NavLink>
          <div className="ml-auto flex items-center gap-2">
            <DatasetIndicator />
            <ModelIndicator />
            {loc.pathname === "/" && sessionId && (
              <Button size="sm" variant="ghost" onClick={newSession} aria-label="Start a new session"><Plus className="h-3.5 w-3.5" />New</Button>
            )}
          </div>
        </div>
        <nav aria-label="Primary" className="mx-auto flex max-w-[1600px] gap-1 overflow-x-auto px-3 pb-2 lg:hidden">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => cn("focus-ring flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs",
              isActive ? "bg-elevated text-ink" : "text-muted hover:text-ink")}>
              <Icon className="h-3.5 w-3.5" aria-hidden />{label}
            </NavLink>
          ))}
        </nav>
      </header>
      <div className="mx-auto flex w-full max-w-[1600px] flex-1">
        <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 flex-col border-r border-line px-3 py-5 lg:flex">
          <nav aria-label="Primary" className="flex flex-col gap-0.5">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => cn("focus-ring group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors",
                isActive ? "text-ink" : "text-muted hover:bg-white/[0.03] hover:text-ink")}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl border border-indigo/25 bg-gradient-to-r from-indigo/15 to-transparent" transition={{ type: "spring", stiffness: 400, damping: 34 }} />}
                    <Icon className={cn("relative h-4 w-4", isActive ? "text-cyan" : "")} aria-hidden />
                    <span className="relative">{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto rounded-xl border border-line bg-white/[0.02] p-3 text-[11px] leading-relaxed text-faint">
            Decision support, not decisions. Numbers come from deterministic analytics; every answer links to source conversations.
          </div>
        </aside>
        <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
