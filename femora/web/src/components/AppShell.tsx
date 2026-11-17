import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { Bell, Clock, MapPin, Menu, Moon, Sun, ThumbsDown, ThumbsUp, Wifi, WifiOff, X } from "lucide-react";
import { NAV } from "../modules/navigation";
import { useApp } from "../lib/app-state";
import { load } from "../lib/storage";
import { Logo } from "./ui";
import { Credit } from "./Credit";
import { LocationDialog } from "./LocationDialog";
import { ReminderWatcher } from "../modules/reminders/useReminders";
import { GuardianWatcher } from "../modules/guardian/useGuardian";
import { Onboarding } from "../modules/onboarding/Onboarding";
import { TourOverlay } from "../modules/onboarding/TourOverlay";
import { tourStore } from "../modules/onboarding/tours";
import { usePersistent } from "../lib/usePersistent";
import { setProvider } from "../modules/conversation/router";
import { llamaProvider, DEFAULT_LLAMA, type LlamaConfig } from "../modules/conversation/llamaProvider";

function useOnline() {
  const [on, setOn] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  useEffect(() => { const u = () => setOn(true), d = () => setOn(false); addEventListener("online", u); addEventListener("offline", d); return () => { removeEventListener("online", u); removeEventListener("offline", d); }; }, []);
  return on;
}

export function AppShell() {
  const app = useApp();
  const [open, setOpen] = useState(false);
  const [editLoc, setEditLoc] = useState(false);
  const [bell, setBell] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const online = useOnline();
  const [onboarded, setOnboarded] = usePersistent("onboarded", () => false);
  useEffect(() => { const t = new URLSearchParams(loc.search).get("tour"); if (t) tourStore.start(t); }, [loc.search]);
  useEffect(() => { setBell(false); }, [loc.pathname]);
  useEffect(() => { const c = load<LlamaConfig>("llama", DEFAULT_LLAMA); if (c.enabled) setProvider(llamaProvider(c)); }, []);
  const unread = app.notices.filter((n) => !n.read).length;

  return (
    <div className="min-h-screen">
      <ReminderWatcher />
      <GuardianWatcher />
      {!onboarded ? <Onboarding onDone={() => setOnboarded(true)} /> : (!app.location || editLoc) && <LocationDialog onClose={app.location ? () => setEditLoc(false) : undefined} />}
      <TourOverlay />
      <div className="flex">
        <aside className={`fixed inset-y-0 left-0 z-30 w-68 transform border-r border-line bg-surface px-4 py-6 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`} aria-label="Main navigation">
          <div className="mb-8 flex items-center justify-between px-2">
            <Link to="/" className="flex items-center gap-2"><Logo /><span className="font-display text-2xl tracking-wide">FEMORA <span className="text-accent">Muse</span></span></Link>
            <button className="lg:hidden" aria-label="Close menu" onClick={() => setOpen(false)}><X /></button>
          </div>
          <nav className="space-y-0.5" data-tour="nav">
            {NAV.map((n) => (
              <NavLink key={n.path} to={n.path} end={n.path === "/app"} onClick={() => setOpen(false)}
                className={({ isActive }) => `flex items-center gap-3 rounded-f-sm px-3 py-2.5 text-[15px] ${isActive ? "bg-primary text-primary-ink" : "text-ink hover:bg-surface-2"}`}>
                <n.icon size={18} strokeWidth={1.6} /> <span className="flex-1">{n.label}</span>
                {n.status === "planned" && <span className="text-[10px] uppercase tracking-widest opacity-60">Coming</span>}
              </NavLink>
            ))}
          </nav>
        </aside>
        {open && <div className="fixed inset-0 z-20 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-bg/85 px-4 py-3 backdrop-blur lg:px-8">
            <button className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu /></button>
            <button onClick={() => setEditLoc(true)} className="flex items-center gap-1 rounded-full px-2 py-1 text-sm text-muted hover:bg-surface-2" aria-label="Change location">
              <MapPin size={15} /> <span className="hidden sm:inline">{app.location ? `${app.location.city} · ${app.location.region}` : "Set location"}</span></button>
            <span className={`flex items-center gap-1 text-xs ${online ? "text-good" : "text-warn"}`} role="status" title={online ? "Online: live listings can refresh" : "Offline: showing saved data only"}>
              {online ? <Wifi size={14} /> : <WifiOff size={14} />}<span className="hidden sm:inline">{online ? "Online" : "Offline · saved data only"}</span></span>
            <div className="ml-auto flex items-center gap-2">
              <select data-tour="theme" aria-label="Theme" className="hidden rounded-full border border-line bg-surface px-3 py-1.5 text-sm md:block" value={app.preset} onChange={(e) => app.setPreset(e.target.value as typeof app.preset)}>
                <option value="onyx">Onyx & Champagne</option><option value="emerald">Emerald & Ivory</option><option value="midnight">Midnight & Pearl</option>
              </select>
              <div className="relative" data-tour="bell">
                <button aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} aria-expanded={bell} className="relative rounded-full p-2 hover:bg-surface-2" onClick={() => setBell(!bell)}>
                  <Bell size={18} />{unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-accent px-1 text-[11px] font-semibold text-white">{unread}</span>}
                </button>
                {bell && (
                  <div className="absolute right-0 z-40 mt-2 w-96 max-w-[92vw] rounded-f bg-surface p-2 shadow-f ring-1 ring-line" role="dialog" aria-label="Notifications">
                    <div className="flex items-center justify-between px-2 py-1"><span className="font-display text-lg">Notifications</span>
                      <span className="flex gap-2 text-xs"><button className="text-primary underline" onClick={app.markAllRead}>Mark all read</button><Link className="text-muted underline" to="/app/settings">Preferences</Link></span></div>
                    {app.notices.length === 0 ? <p className="px-2 py-3 text-sm text-muted">You're all caught up.</p> : (
                      <ul className="max-h-[28rem] overflow-y-auto">{app.notices.map((n) => (
                        <li key={n.id} className={`rounded-f-sm px-2 py-2 ${n.read ? "" : "bg-accent/8"}`}>
                          <button className="w-full text-left" onClick={() => { setBell(false); if (n.link) nav(n.link); }}>
                            <div className="flex items-center gap-2 text-sm font-medium">{n.title}{n.digest && <span className="rounded bg-surface-2 px-1 text-[10px] uppercase text-muted">digest</span>}</div>
                            <div className="text-xs text-muted">{n.body}</div><div className="text-[11px] text-muted">{new Date(n.at).toLocaleString()}</div></button>
                          <div className="mt-1 flex gap-1 text-muted">
                            <button aria-label="Snooze 1 hour" title="Snooze 1 hour" className="rounded p-1 hover:bg-surface-2" onClick={() => app.snooze(n.key, 60)}><Clock size={14} /></button>
                            <button aria-label="Useful" title="Useful" className={`rounded p-1 hover:bg-surface-2 ${n.feedback === "useful" ? "text-good" : ""}`} onClick={() => app.feedback(n.id, true)}><ThumbsUp size={14} /></button>
                            <button aria-label="Not relevant" title="Not relevant" className={`rounded p-1 hover:bg-surface-2 ${n.feedback === "not-relevant" ? "text-warn" : ""}`} onClick={() => app.feedback(n.id, false)}><ThumbsDown size={14} /></button>
                            <button aria-label="Dismiss" title="Dismiss" className="ml-auto rounded p-1 hover:bg-surface-2" onClick={() => app.dismiss(n.id)}><X size={14} /></button>
                          </div>
                        </li>))}</ul>)}
                  </div>)}
              </div>
              <button aria-label={app.theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} className="rounded-full p-2 hover:bg-surface-2" onClick={() => app.setTheme(app.theme === "dark" ? "light" : "dark")}>
                {app.theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
            </div>
          </header>
          <main className="f-rise mx-auto min-h-[calc(100vh-4rem)] max-w-7xl p-4 lg:p-10" key={loc.pathname}><Suspense fallback={<div role="status" aria-label="Loading" className="grid min-h-[40vh] place-items-center"><span className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-accent" /></div>}><Outlet /></Suspense></main>
          <footer className="border-t border-line px-4 py-6 text-center lg:px-8"><Credit /></footer>
        </div>
      </div>
    </div>
  );
}
