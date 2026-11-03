import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Activity, BadgeCheck, Bot, Briefcase, Cloud, Code2, Coins, FileBarChart, Gauge, Leaf, Menu, MessageSquare, PiggyBank, Scale, Settings, ShieldCheck, X,
} from "lucide-react";
import { SherinAvatar } from "./SherinAvatar";
import { DataClassBadge, Segmented } from "./ui";
import { DEFAULT_MONTH, useApp, type Currency, type PeriodKind, type Role } from "../lib/store";
import { lastMonths, monthLabel } from "../lib/format";
import { useApi } from "../lib/api";

export const NAV = [
  { to: "/", label: "Financial Command Center", icon: Gauge },
  { to: "/chat", label: "Sherin Copilot", icon: MessageSquare },
  { to: "/portfolio", label: "Portfolio Dashboard", icon: Briefcase },
  { to: "/guardian", label: "Investment Judgment", icon: ShieldCheck },
  { to: "/harness", label: "Agent Harness", icon: Bot },
  { to: "/azure", label: "Azure DevOps", icon: Cloud },
  { to: "/python", label: "Python Engineering", icon: Code2 },
  { to: "/tokens", label: "Token Analytics", icon: Coins },
  { to: "/savings", label: "AI Savings", icon: PiggyBank },
  { to: "/metrics", label: "System Metrics", icon: Activity },
  { to: "/approvals", label: "Manager Approvals", icon: BadgeCheck },
  { to: "/esg", label: "ESG & Compliance", icon: Leaf },
  { to: "/reports", label: "Executive Reporting", icon: FileBarChart },
  { to: "/settings", label: "Settings", icon: Settings },
];

const ROLES: Role[] = ["SHERIN_MANAGER", "RISK_OFFICER", "COMPLIANCE_OFFICER", "PORTFOLIO_MANAGER", "ENGINEER", "VIEWER"];
const ROLE_USERS: Record<Role, string> = { SHERIN_MANAGER: "mgr.sherin", RISK_OFFICER: "risk.maya", COMPLIANCE_OFFICER: "comp.omar", PORTFOLIO_MANAGER: "pm.ananya", ENGINEER: "eng.ravi", VIEWER: "viewer.board" };

export function GlobalControls() {
  const s = useApp();
  const months = lastMonths(DEFAULT_MONTH, 14);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented label="Period" value={s.periodKind} onChange={(v) => s.setPeriodKind(v as PeriodKind)}
        options={[{ value: "month", label: "Month" }, { value: "quarter", label: "Quarter" }, { value: "year", label: "Year" }, { value: "ttm", label: "12M" }]} />
      <label className="sr-only" htmlFor="month">Accounting month</label>
      <select id="month" value={s.month} onChange={(e) => s.setMonth(e.target.value)} className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-flo-900">
        {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
      </select>
      <Segmented label="Currency" value={s.currency} onChange={(v) => s.setCurrency(v as Currency)}
        options={[{ value: "USD", label: "USD" }, { value: "INR", label: "INR" }, { value: "CAD", label: "CAD" }]} />
      <Segmented label="Data" value={s.dc} onChange={(v) => s.setDc(v as "synthetic" | "measured")}
        options={[{ value: "synthetic", label: "Demo ledger" }, { value: "measured", label: "Measured" }]} />
    </div>
  );
}

export function RoleSwitcher({ compact = false }: { compact?: boolean }) {
  const s = useApp();
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted">
      {!compact && <span>Acting as</span>}
      <select aria-label="Role" value={s.role} onChange={(e) => { const r = e.target.value as Role; s.setRole(r); s.setUser(ROLE_USERS[r]); }}
        className="rounded-full border border-line bg-white px-2.5 py-1 text-xs font-semibold text-flo-900">
        {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
      </select>
    </label>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const { dc } = useApp();
  const inbox = useApi<any[]>("/approvals", { status: "open" }, 15000);
  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    if (loc.hash) setTimeout(() => document.getElementById(loc.hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
  }, [loc.hash, loc.pathname]);
  const pending = inbox.data?.length ?? 0;
  return (
    <div className="flex min-h-full">
      <aside className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-flo-950 text-white transition lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-3 px-5 pb-4 pt-5">
          <SherinAvatar size="md" />
          <div>
            <div className="font-display text-lg font-semibold leading-tight">FLO Bank</div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-flo-200">Sherin AI 3.0</div>
          </div>
          <button type="button" className="ml-auto lg:hidden" aria-label="Close navigation" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button>
        </div>
        <nav aria-label="Main" className="space-y-0.5 px-3 pb-6">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"}
              className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${isActive ? "bg-flo-800 font-semibold text-white" : "text-flo-100/80 hover:bg-flo-900 hover:text-white"}`}>
              <Icon className="h-4 w-4" aria-hidden />
              <span className="flex-1">{label}</span>
              {to === "/approvals" && pending > 0 && <span className="rounded-full bg-gold px-1.5 text-[10px] font-bold text-flo-950" aria-label={`${pending} open approvals`}>{pending}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="mx-4 rounded-xl border border-flo-800 bg-flo-900/60 p-3 text-[11px] leading-snug text-flo-100/80">
          <Scale className="mb-1 h-4 w-4 text-gold" aria-hidden />
          Money-first view. Revenue, cost and savings are computed by one deterministic engine; estimates and forecasts are labelled.
        </div>
      </aside>
      {open && <button type="button" aria-label="Close navigation overlay" className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-white/85 backdrop-blur">
          <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 lg:px-6">
            <button type="button" className="lg:hidden" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
            <GlobalControls />
            <div className="ml-auto flex items-center gap-2"><DataClassBadge dc={dc} /><RoleSwitcher /></div>
          </div>
          {dc === "synthetic" && (
            <div className="border-t border-[#E8D7AE] bg-gold-light px-4 py-1 text-center text-[11px] font-medium text-[#7A5D1E] lg:px-6">
              Demonstration mode: financial figures are synthetic and clearly separated from measured system data. They are not FLO Bank's actual performance.
            </div>
          )}
        </header>
        <main className="min-w-0 flex-1 px-4 py-5 lg:px-6">{children}</main>
      </div>
    </div>
  );
}
