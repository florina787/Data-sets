import { useState } from "react";
import { NavLink, Outlet, Link } from "react-router-dom";
import { Bell, MapPin, Menu, Moon, Sun, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { ReminderWatcher } from "../modules/reminders/useReminders";
import { LocationDialog } from "./LocationDialog";
import { NAV } from "../modules/navigation";
import { useApp } from "../lib/app-state";
import { PROFILES } from "../data/demo/profiles";
import { Logo, StatusBadge } from "./ui";
import { Credit } from "./Credit";

export function AppShell() {
  const app = useApp();
  const [open, setOpen] = useState(false);
  const [editLoc, setEditLoc] = useState(false);
  const [bell, setBell] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  useEffect(() => { setBell(false); }, [loc.pathname]);
  const unread = app.notices.filter((n) => !n.read).length;
  return (
    <div className="min-h-screen">
      <div className="bg-warn/15 px-4 py-1.5 text-center text-xs text-ink" role="note">
        Leadership demo · all people and health data are <b>fictional</b> · AI responses are <b>simulated</b> · not medical advice
      </div>
      {(!app.location || editLoc) && <LocationDialog onClose={app.location ? () => setEditLoc(false) : undefined} />}
      <ReminderWatcher />
      <div className="flex">
        <aside className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-line bg-surface p-4 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`} aria-label="Main navigation">
          <div className="mb-6 flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2 font-semibold tracking-[0.18em]"><Logo /> FEMORA</Link>
            <button className="lg:hidden" aria-label="Close menu" onClick={() => setOpen(false)}><X /></button>
          </div>
          <nav className="space-y-1">
            {NAV.map((n) => (
              <NavLink key={n.path} to={n.path} end={n.path === "/app"} onClick={() => setOpen(false)}
                className={({ isActive }) => `flex items-center gap-3 rounded-f-sm px-3 py-2 text-[15px] ${isActive ? "bg-primary text-primary-ink" : "hover:bg-surface-2"}`}>
                <n.icon size={18} /> <span className="flex-1">{n.label}</span>
                {n.status === "planned" && <span className="text-[10px] uppercase tracking-wide opacity-70">soon</span>}
              </NavLink>
            ))}
          </nav>
        </aside>
        {open && <div className="fixed inset-0 z-20 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
        <div className="min-w-0 flex-1">
          <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3 lg:px-8">
            <button className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu /></button>
            <label className="flex items-center gap-2 text-sm"><span className="hidden text-muted sm:inline">Demo profile</span>
              <select className="rounded-full border border-line bg-surface px-3 py-1.5" value={app.profile.id} onChange={(e) => app.setProfileId(e.target.value)}>
                {PROFILES.map((p) => <option key={p.id} value={p.id}>{p.name}, {p.age} · {p.city || p.country}</option>)}
              </select>
            </label>
            <button onClick={() => setEditLoc(true)} className="flex items-center gap-1 rounded-full px-2 py-1 text-sm text-muted hover:bg-surface-2" aria-label="Change location">
              <MapPin size={15} /> <span className="hidden sm:inline">{app.location ? `${app.location.city} · ${app.location.region}` : "Set location"}</span></button>
            <span className="hidden sm:inline"><StatusBadge status="simulated" /></span>
            <div className="ml-auto flex items-center gap-2">
              <label className="hidden items-center gap-1 text-sm md:flex"><span className="text-muted">Theme</span>
                <select className="rounded-full border border-line bg-surface px-3 py-1.5" value={app.preset} onChange={(e) => app.setPreset(e.target.value as typeof app.preset)}>
                  <option value="sky">Sky</option><option value="forest">Forest</option><option value="indigo">Indigo</option>
                </select></label>
              <div className="relative">
                <button aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} aria-expanded={bell} className="relative rounded-full p-2 hover:bg-surface-2" onClick={() => { setBell(!bell); if (!bell) setTimeout(app.markAllRead, 1500); }}>
                  <Bell size={18} />{unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-warm px-1 text-[11px] font-semibold text-white">{unread}</span>}
                </button>
                {bell && (
                  <div className="absolute right-0 z-40 mt-2 w-80 rounded-f bg-surface p-2 shadow-f ring-1 ring-line" role="dialog" aria-label="Notifications">
                    <div className="px-2 py-1 text-sm font-semibold">Notifications</div>
                    {app.notices.length === 0 ? <p className="px-2 py-3 text-sm text-muted">You're all caught up.</p> : (
                      <ul className="max-h-96 overflow-y-auto">{app.notices.map((n) => (
                        <li key={n.id}><button className={`w-full rounded-f-sm px-2 py-2 text-left hover:bg-surface-2 ${n.read ? "" : "bg-primary/5"}`} onClick={() => { setBell(false); if (n.link) nav(n.link); }}>
                          <div className="text-sm font-medium">{n.title}</div><div className="text-xs text-muted">{n.body}</div><div className="text-[11px] text-muted">{new Date(n.at).toLocaleString()}</div></button></li>))}</ul>)}
                  </div>)}
              </div>
              <button aria-label={app.theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} className="rounded-full p-2 hover:bg-surface-2" onClick={() => app.setTheme(app.theme === "dark" ? "light" : "dark")}>
                {app.theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>
          </header>
          <main className="mx-auto max-w-7xl p-4 lg:p-8"><Outlet /></main>
          <footer className="border-t border-line px-4 py-4 text-center lg:px-8"><Credit /></footer>
        </div>
      </div>
    </div>
  );
}
