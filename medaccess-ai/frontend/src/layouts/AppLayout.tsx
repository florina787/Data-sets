import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { MedAccessLogo } from "../components/Logo";
import { useApp } from "../hooks/AppContext";
import type { Role } from "../services/api";

export interface NavItem { to: string; label: string; roles?: Role[] }
export interface NavSection { id: string; label: string; items: NavItem[] }

const ENG: Role[] = ["engineer", "release_approver", "admin"];

export const NAV: NavSection[] = [
  { id: "patient", label: "Patient Services", items: [
    { to: "/", label: "Dashboard" },
    { to: "/search", label: "Find Healthcare Services" },
    { to: "/search/MRI", label: "MRI Appointments" },
    { to: "/search/CT", label: "CT Scans" },
    { to: "/search/ULTRASOUND", label: "Ultrasound" },
    { to: "/search/XRAY", label: "X-Ray" },
    { to: "/search/BLOOD_TEST", label: "Blood Tests" },
    { to: "/search/LAB_INVESTIGATION", label: "Laboratory Services" },
    { to: "/search/FAMILY_PHYSICIAN", label: "Doctor Appointments" },
    { to: "/search/SPECIALIST", label: "Specialist Consultations" },
    { to: "/facilities", label: "Nearby Facilities" },
    { to: "/map", label: "Interactive Map" },
    { to: "/compare", label: "Compare Wait Times" },
    { to: "/tracker", label: "Appointment Tracker" },
    { to: "/notifications", label: "Notifications" },
    { to: "/saved", label: "Saved Searches" },
    { to: "/history", label: "Search History" },
    { to: "/requisition", label: "Requisition Checklist" },
    { to: "/preferences", label: "Patient Preferences" },
  ] },
  { id: "copilot", label: "AI Copilot", items: [
    { to: "/christina", label: "Ask Christina" },
    { to: "/agent-activity", label: "AI Agent Activity" },
    { to: "/agent-graph", label: "Agent Workflow Graph" },
  ] },
  { id: "engineering", label: "AI Engineering", items: [
    { to: "/sdlc", label: "AI-SDLC Command Center", roles: ENG },
    { to: "/requirements", label: "Requirements Studio", roles: ENG },
    { to: "/architecture", label: "Architecture Explorer", roles: ENG },
    { to: "/development", label: "Development Workspace", roles: ENG },
    { to: "/qa", label: "QA & Test Center", roles: ENG },
  ] },
  { id: "governance", label: "Governance", items: [
    { to: "/security", label: "Security & Governance", roles: ENG },
    { to: "/approvals", label: "Human Approval Center" },
    { to: "/releases", label: "Release Management", roles: ENG },
  ] },
  { id: "operations", label: "Operations", items: [
    { to: "/monitoring", label: "Production Monitoring", roles: ENG },
    { to: "/observability", label: "LangSmith Observability", roles: ENG },
    { to: "/metrics", label: "System Metrics", roles: ENG },
    { to: "/admin", label: "Administration", roles: ["admin"] },
    { to: "/settings", label: "Settings" },
  ] },
];

export function visibleNav(role: Role | undefined): NavSection[] {
  return NAV.map((s) => ({ ...s, items: s.items.filter((i) => !i.roles || (role && i.roles.includes(role))) })).filter((s) => s.items.length);
}

const ROLE_LABEL: Record<Role, string> = { patient: "Patient", engineer: "Engineer", release_approver: "Release approver", admin: "Administrator" };

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout, reducedMotion, scenario } = useApp();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const loc = useLocation();
  const sections = visibleNav(user?.role);
  return (
    <div className={`min-h-screen ${reducedMotion ? "reduce-motion" : ""}`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:p-2">Skip to content</a>
      <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-3">
          <button className="btn-ghost px-2 py-1 lg:hidden" aria-label="Toggle navigation" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
          <MedAccessLogo />
        </div>
        <div className="hidden text-center text-xs italic text-slate-500 md:block">Smarter Healthcare Access. Shorter Waits. Better Choices.</div>
        <div className="flex items-center gap-2 text-sm">
          {scenario && <span className="hidden rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-[#9A4500] sm:inline">scenario: {scenario}</span>}
          <span className="hidden text-right sm:block"><span className="block font-semibold leading-tight">{user?.name}</span><span className="text-xs text-slate-500">{user && ROLE_LABEL[user.role]}</span></span>
          <button className="btn-ghost px-3 py-1" onClick={logout}>Sign out</button>
        </div>
      </header>
      <div className="flex">
        <nav aria-label="Main" className={`${open ? "block" : "hidden"} fixed inset-y-0 left-0 z-20 mt-[57px] w-72 overflow-y-auto border-r border-slate-200 bg-white p-3 lg:sticky lg:top-[57px] lg:mt-0 lg:block lg:h-[calc(100vh-57px)]`}>
          {sections.map((s) => (
            <div key={s.id} className="mb-2">
              <button className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 hover:bg-slate-50"
                aria-expanded={!collapsed[s.id]} onClick={() => setCollapsed({ ...collapsed, [s.id]: !collapsed[s.id] })}>
                {s.label}<span aria-hidden="true">{collapsed[s.id] ? "▸" : "▾"}</span>
              </button>
              {!collapsed[s.id] && (
                <ul>
                  {s.items.map((i) => (
                    <li key={i.to}>
                      <NavLink to={i.to} end onClick={() => setOpen(false)}
                        className={({ isActive }) => `block rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-brand-50 font-semibold text-brand-700" : "text-ink hover:bg-slate-50"}`}>
                        {i.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <p className="mt-4 px-2 text-[10px] text-slate-400">Demo build · synthetic data only · {loc.pathname}</p>
        </nav>
        <main id="main" className="min-w-0 flex-1 px-4 py-5 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
