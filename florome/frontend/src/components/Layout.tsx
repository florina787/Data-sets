import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { ROLES, getRole, onRoleChange, setRole, type Role } from "../lib/api";
import { Wordmark } from "./Logo";
import { cx } from "./ui";

export const NAV = [
  { to: "/", label: "Overview" },
  { to: "/topology", label: "Nervous System" },
  { to: "/rca", label: "RCA" },
  { to: "/actions", label: "Actions" },
  { to: "/integrations", label: "Integrations" },
  { to: "/sources", label: "Sources" },
  { to: "/governance", label: "Governance" },
  { to: "/finops", label: "FinOps" },
];

export function useRole(): Role {
  const [r, setR] = useState(getRole());
  useEffect(() => {
    const off = onRoleChange(() => setR(getRole()));
    return () => void off();
  }, []);
  return r;
}

export function RoleSwitcher() {
  const role = useRole();
  return (
    <label className="flex items-center gap-2 text-xs text-ink-soft">
      <span className="hidden lg:inline">Acting as</span>
      <select aria-label="Demo role" value={role} onChange={(e) => setRole(e.target.value as Role)}
        className="rounded-lg border border-dome-100 bg-white px-2 py-1.5 text-xs font-medium text-ink focus:outline-dome-500">
        {ROLES.map((r) => <option key={r} value={r}>demo {r}</option>)}
      </select>
    </label>
  );
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <div className="bg-ink px-4 py-1.5 text-center text-[11px] text-white/80">
        Demo mode: <b className="text-white">Meridian Freight</b> is a fictional tenant. All telemetry, costs and actions run against a simulated sandbox; no real system is called.
      </div>
      <header className="sticky top-0 z-30 border-b border-dome-100/70 bg-canvas/85 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-6 py-3">
          <NavLink to="/" aria-label="Florome home"><Wordmark /></NavLink>
          <nav aria-label="Primary" className="flex flex-1 gap-1 overflow-x-auto">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.to === "/"}
                className={({ isActive }) => cx("whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] transition",
                  isActive ? "bg-white font-medium text-ink shadow-sm ring-1 ring-dome-100" : "text-ink-soft hover:text-ink")}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <RoleSwitcher />
        </div>
      </header>
      <main><Outlet /></main>
      <footer className="mx-auto max-w-[1400px] px-6 py-10 text-xs text-ink-mute">
        Florome · the intelligence dome over your enterprise. Integration status is shown exactly as verified; see Integrations.
      </footer>
    </div>
  );
}

export function Page({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cx("mx-auto max-w-[1400px] px-6 py-8", className)}>{children}</div>;
}
