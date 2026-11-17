import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity, BarChart3, BookLock, Bell, Brain, Compass, FlaskConical, Gauge, Globe2, Home, LineChart, Rocket,
  Scale, Settings, Shield, Swords, Timer, TrendingUp, Wallet, Zap, Star,
} from "lucide-react";
import type { ComponentType } from "react";

type Item = { to?: string; label: string; icon: ComponentType<{ size?: number }>; planned?: boolean };
const GROUPS: { title: string; items: Item[] }[] = [
  { title: "Intelligence", items: [
    { to: "/", label: "Home", icon: Home },
    { to: "/overview", label: "Executive Overview", icon: Activity },
    { to: "/markets", label: "Global Markets", icon: Globe2 },
    { to: "/rankings", label: "AI Stock Intelligence", icon: Brain },
    { to: "/watchlist", label: "Watchlist & Guide", icon: Star },
  ] },
  { title: "Trading research", items: [
    { label: "Swift Trading", icon: Zap, planned: true },
    { label: "Intraday Trading", icon: Timer, planned: true },
    { label: "Swing Trading", icon: TrendingUp, planned: true },
    { label: "Aggressive Trading", icon: Rocket, planned: true },
    { label: "Long-Term Investing", icon: Compass, planned: true },
    { label: "Global News Globe", icon: Globe2, planned: true },
    { label: "Bull vs Bear Debate", icon: Swords, planned: true },
  ] },
  { title: "Risk", items: [
    { to: "/risk", label: "Market Crash Risk", icon: Gauge },
    { to: "/guardian", label: "Portfolio Risk Guardian", icon: Shield },
  ] },
  { title: "Accountability", items: [
    { to: "/lab", label: "Strategy Research Lab", icon: FlaskConical },
    { label: "Paper Trading", icon: Wallet, planned: true },
    { to: "/memory", label: "Prediction Memory", icon: BookLock },
    { to: "/models", label: "Model Performance", icon: BarChart3 },
    { label: "Alerts", icon: Bell, planned: true },
    { to: "/settings", label: "Data & Settings", icon: Settings },
  ] },
];

const TITLES: Record<string, string> = Object.fromEntries(GROUPS.flatMap((g) => g.items.filter((i) => i.to).map((i) => [i.to!, i.label])));

export default function Layout() {
  const loc = useLocation();
  const title = TITLES[loc.pathname] ?? (loc.pathname.startsWith("/stock/") ? "Stock detail" : "FLOW WEALTH");
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><span className="brand-mark"><LineChart size={16} /></span>FLOW WEALTH</div>
        <nav className="nav" aria-label="Main">
          {GROUPS.map((g) => (
            <div key={g.title}>
              <div className="nav-group">{g.title}</div>
              {g.items.map((it) => it.planned ? (
                <span key={it.label} className="planned" aria-disabled="true" title="Planned: not implemented yet">
                  <it.icon size={16} />{it.label}<span className="tag">planned</span>
                </span>
              ) : (
                <NavLink key={it.to} to={it.to!} end={it.to === "/"}><it.icon size={16} />{it.label}</NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <div className="main">
        {loc.pathname !== "/" && <header className="topbar"><Scale size={18} className="muted" /><h1>{title}</h1></header>}
        <Outlet />
        <footer className="disclaimer">
          FLOW WEALTH provides research and educational analytics, not investment advice. Forecasts are uncertain and
          nothing here guarantees returns. No brokerage is connected; there is no live order execution.
        </footer>
      </div>
    </div>
  );
}
