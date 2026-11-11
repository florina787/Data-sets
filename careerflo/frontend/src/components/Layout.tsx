import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, BarChart3, Bot, BookOpen, Boxes, Briefcase, Building2, Code2, CreditCard, FileCheck2, FileText, Github, Kanban, LogOut,
  Mail, Menu, MessagesSquare, Moon, Network, Radar, Scale, Search, Settings, ShieldCheck, Sparkles, Sun, Target, Users, Wallet, X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useUsage } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Logo } from "./Logo";
import { Button } from "./ui";

export const NAV: { group: string; items: [string, string, typeof Bot][] }[] = [
  { group: "Assistant", items: [["AI Career Assistant", "/app", Sparkles]] },
  { group: "Discover", items: [["Job Discovery", "/app/jobs", Search], ["Indeed Job Intelligence", "/app/jobs/indeed", Briefcase],
    ["LinkedIn Job Intelligence", "/app/jobs/linkedin", Briefcase], ["Hidden Job Radar", "/app/radar", Radar], ["Job Matching", "/app/matching", Target]] },
  { group: "Prepare", items: [["Resume Studio", "/app/resume", FileText], ["ATS Intelligence", "/app/ats", FileCheck2],
    ["Cover Letter Studio", "/app/cover", Mail], ["Interview Intelligence", "/app/interview", MessagesSquare], ["Live Coding Coach", "/app/coding", Code2],
    ["Skills & Learning", "/app/learning", BookOpen]] },
  { group: "Pursue", items: [["Company Research", "/app/company", Building2], ["Recruiter CRM", "/app/recruiters", Users],
    ["Application Tracker", "/app/applications", Kanban], ["GitHub Portfolio Intelligence", "/app/portfolio", Github],
    ["Salary Intelligence", "/app/salary", Wallet], ["Career Analytics", "/app/analytics", BarChart3]] },
  { group: "Control", items: [["Agent Mission Control", "/app/mission", Activity], ["MCP Tool Registry", "/app/mcp", Boxes],
    ["Governance Center", "/app/governance", ShieldCheck], ["Billing and Subscription", "/app/billing", CreditCard], ["Account Settings", "/app/settings", Settings]] },
  { group: "Intelligence", items: [["Career Graph", "/app/graph", Network]] },
];

export function useTheme() {
  const [dark, setDark] = useState(() => {
    try { return localStorage.getItem("cf.theme") === "dark" || (!localStorage.getItem("cf.theme") && matchMedia("(prefers-color-scheme: dark)").matches); }
    catch { return false; }
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem("cf.theme", dark ? "dark" : "light"); } catch { /* ignore */ }
  }, [dark]);
  return [dark, setDark] as const;
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { me, signOut } = useAuth();
  const nav = useNavigate();
  return (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-5" aria-label="Main">
      <Link to="/app" className="px-3"><Logo /></Link>
      {NAV.map((g) => (
        <div key={g.group}>
          <p className="px-3 pb-1 text-[10.5px] font-semibold uppercase tracking-[.14em] text-slate-400">{g.group}</p>
          {g.items.map(([label, to, Icon]) => (
            <NavLink key={to} to={to} end onClick={onNavigate}
              className={({ isActive }) => cn("flex items-center gap-2.5 rounded-xl px-3 py-[7px] text-[13px] transition",
                isActive ? "bg-white font-medium text-ink shadow-float dark:bg-white/10 dark:text-white" : "text-slate-600 hover:bg-white/60 dark:text-slate-400 dark:hover:bg-white/5")}>
              <Icon className="h-4 w-4 shrink-0" aria-hidden />{label}
            </NavLink>
          ))}
        </div>
      ))}
      {me?.is_admin && (
        <div className="mx-3 flex flex-col gap-1 text-[12.5px]">
          <NavLink to="/app/admin" className="text-violet">Admin revenue dashboard</NavLink>
          <NavLink to="/app/ops" className="text-violet">Operations dashboard</NavLink>
        </div>
      )}
      <button onClick={async () => { await signOut(); nav("/login"); }} className="mx-3 mt-auto flex items-center gap-2 text-[12.5px] text-slate-500">
        <LogOut className="h-3.5 w-3.5" /> Sign out {me?.email && <span className="truncate">({me.email})</span>}
      </button>
    </nav>
  );
}

function UpgradeDialog() {
  const [detail, setDetail] = useState<any>(null);
  const nav = useNavigate();
  useEffect(() => {
    const h = (e: Event) => setDetail((e as CustomEvent).detail);
    window.addEventListener("cf:upgrade", h);
    return () => window.removeEventListener("cf:upgrade", h);
  }, []);
  return (
    <AnimatePresence>
      {detail && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          role="dialog" aria-modal="true" aria-labelledby="upgrade-title">
          <motion.div className="card w-full max-w-md p-8 text-center" initial={{ y: 16, scale: 0.98 }} animate={{ y: 0, scale: 1 }}>
            <p className="eyebrow">Free trial complete</p>
            <h2 id="upgrade-title" className="mt-2 font-serif text-3xl">Keep going with Pro</h2>
            <p className="muted mt-3 text-sm">{detail?.message || "You've used your free uses of this feature."}</p>
            <p className="muted mt-2 text-xs">No charge happens automatically — you choose if and when to subscribe.</p>
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="outline" onClick={() => setDetail(null)}>Not now</Button>
              <Button onClick={() => { setDetail(null); nav("/pricing"); }}>Compare plans</Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function IntelPanel({ children }: { children?: ReactNode }) {
  const { data } = useUsage();
  const low = data?.features.filter((f) => f.trial_remaining < f.trial_limit).slice(0, 5) ?? [];
  return (
    <aside className="hidden w-72 shrink-0 flex-col gap-4 xl:flex" aria-label="Intelligence panel">
      {children}
      <div className="card p-5">
        <div className="flex items-center justify-between">
          <p className="text-[13px] font-semibold">Plan</p>
          <Link to="/app/billing" className="text-[12px] text-violet">{data?.plan.name ?? "…"}</Link>
        </div>
        <p className="muted mt-3 text-[12px]">Free uses remaining</p>
        <ul className="mt-2 space-y-1.5">
          {(low.length ? low : data?.features.slice(0, 4) ?? []).map((f) => (
            <li key={f.id} className="flex items-center justify-between text-[12.5px]">
              <span className="truncate">{f.name}</span>
              <span className={cn("tabular-nums", f.available === 0 ? "text-red-600" : "text-slate-500")}>{f.trial_remaining}/{f.trial_limit}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export function AppLayout() {
  const [dark, setDark] = useTheme();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  return (
    <div className="bloom relative min-h-dvh">
      <div className="relative z-10 flex">
        <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 lg:block"><Sidebar /></aside>
        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between px-4 py-3 lg:px-8">
            <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
            <span />
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={() => setDark(!dark)}>{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button>
              <Link to="/pricing"><Button variant="outline" size="sm"><Scale className="h-3.5 w-3.5" />Plans</Button></Link>
            </div>
          </header>
          <main className="px-4 pb-20 lg:px-8"><Outlet /></main>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-40 bg-ink/30 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)}>
            <motion.div className="h-full w-72 bg-canvas dark:bg-[#0b0f1a]" initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} onClick={(e) => e.stopPropagation()}>
              <button className="absolute right-4 top-4" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
              <Sidebar onNavigate={() => setOpen(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <UpgradeDialog />
    </div>
  );
}
