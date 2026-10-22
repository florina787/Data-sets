import { useQuery } from "@tanstack/react-query";
import { Bell, Bot, Briefcase, Building2, CheckSquare, Database, FileSearch, Gauge, History, Landmark, LineChart, LogOut, Moon, Scale,
  Shield, ShieldCheck, Sun, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { LANGS, t, type Lang } from "@/lib/i18n";
import { AskFloPanel } from "./AskFloPanel";
import { Badge, Button, Input, Select, cn } from "./ui";

const ICONS: Record<string, any> = { executive: Gauge, investment: LineChart, scenarios: Scale, wealth: Users, products: Briefcase, compliance: Landmark,
  approvals: CheckSquare, decisions: History, knowledge: FileSearch, aiops: Bot, governance: ShieldCheck, privacy: Shield, data: Database };

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout, lang, setLang, theme, toggleTheme, ask, filters, setFilters, can } = useApp();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const gov = useQuery({ queryKey: ["gov"], queryFn: () => api("/api/governance/status") });
  const pending = useQuery({ queryKey: ["approvals", "pending"], queryFn: () => api("/api/approvals?status=pending"), refetchInterval: 30000 });
  const pendingCount = (pending.data?.approvals ?? []).filter((a: any) => me && a.requested_by !== me.user_id).length;
  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-gold focus:p-2 focus:text-bg">Skip to content</a>
      <nav className="hidden w-60 shrink-0 flex-col border-r border-line bg-side md:flex" aria-label="Primary">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-bg ring-1 ring-gold/50"><Building2 className="h-4 w-4 text-gold" /></div>
          <div><div className="font-semibold tracking-wide">FLO</div><div className="text-[10px] text-muted leading-tight">Financial Leadership, Operations &amp; Wealth Intelligence</div></div>
        </div>
        <div className="flex-1 overflow-y-auto scroll-thin px-2 space-y-0.5">
          {me?.navigation.map((n) => {
            const Icon = ICONS[n.id] ?? Gauge;
            return (
              <NavLink key={n.id} to={`/${n.id}`} className={({ isActive }) => cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm",
                isActive ? "bg-card text-ink ring-1 ring-gold/40" : "text-muted hover:bg-card/60 hover:text-ink")}>
                <Icon className="h-4 w-4" />{t(n.id, lang)}
                {n.id === "approvals" && pendingCount > 0 && <span className="ml-auto rounded-full bg-gold px-1.5 text-[10px] font-semibold text-bg">{pendingCount}</span>}
              </NavLink>
            );
          })}
        </div>
        <div className="border-t border-line p-3 text-[11px] text-muted space-y-1">
          <div className="flex items-center gap-1"><ShieldCheck className="h-3 w-3 text-pos" />Policy {gov.data?.policy_version ?? "…"}</div>
          <div>PDP: {gov.data?.pdp ?? "…"}</div>
          <div>Telemetry: {gov.data?.observability ?? "…"}</div>
          <div>Integrations: mock adapters</div>
          <Badge tone="gold">{t("synthetic", lang)} · independent demo</Badge>
        </div>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-line bg-side/60 px-4 py-2">
          <form className="flex-1 min-w-[180px] max-w-md" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/knowledge?q=${encodeURIComponent(q)}`); }}>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search", lang)} aria-label="Global search" />
          </form>
          <Select aria-label="Date range" value={filters.months} onChange={(e) => setFilters({ months: Number(e.target.value) as 12 | 24 })}>
            <option value={12}>Trailing 12 months</option><option value={24}>Trailing 24 months</option>
          </Select>
          {(can("finance:read") || can("investment:read")) && (
            <Select aria-label="Asset class filter" value={filters.asset_class} onChange={(e) => setFilters({ asset_class: e.target.value })}>
              <option value="">All asset classes</option>{["Equity", "Fixed Income", "Balanced", "Alternatives", "Cash"].map((x) => <option key={x}>{x}</option>)}
            </Select>
          )}
          <span className="text-xs text-muted">{t("dataAsOf", lang)} <b className="text-ink">{me?.data_as_of}</b></span>
          <div className="ml-auto flex items-center gap-1">
            <Button size="icon" variant="ghost" aria-label={`Notifications: ${pendingCount} approvals waiting`} title="Pending approvals" onClick={() => nav("/approvals")}>
              <Bell className="h-4 w-4" />{pendingCount > 0 && <span className="sr-only">{pendingCount}</span>}
            </Button>
            <Select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value as Lang)} className="h-8 text-xs">
              {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </Select>
            <Button size="icon" variant="ghost" onClick={toggleTheme} aria-label="Toggle theme">{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</Button>
            <Button variant="primary" size="sm" onClick={() => ask({})}><Bot className="h-4 w-4" />{t("ask", lang)}</Button>
            <div className="ml-2 hidden text-right text-xs sm:block"><div className="font-medium">{me?.display_name}</div><div className="text-muted">{me?.title}</div></div>
            <Button size="icon" variant="ghost" onClick={() => { logout(); nav("/"); }} aria-label="Sign out" title="Switch user"><LogOut className="h-4 w-4" /></Button>
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-line px-2 py-1 md:hidden" aria-label="Primary mobile">
          {me?.navigation.map((n) => <NavLink key={n.id} to={`/${n.id}`} className="whitespace-nowrap rounded px-2 py-1 text-xs text-muted">{t(n.id, lang)}</NavLink>)}
        </nav>
        <main id="main" className="flex-1 overflow-y-auto scroll-thin p-4 md:p-6">{children}</main>
      </div>
      <AskFloPanel />
    </div>
  );
}
