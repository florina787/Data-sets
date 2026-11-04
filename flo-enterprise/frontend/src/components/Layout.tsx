import { useQuery } from "@tanstack/react-query";
import { Bell, Bot, Briefcase, CheckSquare, Database, FileSearch, Gauge, History, Landmark, LineChart, LogOut, MessageSquare, Moon,
  PanelLeftClose, PanelLeftOpen, Plus, Scale, Shield, ShieldCheck, Sparkles, Sun, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { LANGS, t, type Lang } from "@/lib/i18n";
import { Logo } from "./Logo";
import { Badge, Button, Input, Select, cn } from "./ui";

const readCollapsed = () => {
  try {
    return localStorage.getItem("flo.sidebar") === "collapsed";
  } catch {
    return false;
  }
};

const ICONS: Record<string, any> = { executive: Gauge, investment: LineChart, scenarios: Scale, wealth: Users, products: Briefcase, compliance: Landmark,
  approvals: CheckSquare, decisions: History, knowledge: FileSearch, aiops: Bot, governance: ShieldCheck, privacy: Shield, data: Database };

export function Layout({ children }: { children: ReactNode }) {
  const { me, logout, lang, setLang, theme, toggleTheme, filters, setFilters, can, askOpen } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  const onFlo = loc.pathname === "/";
  // "Explain with FLO" anywhere in the enterprise modules opens the conversation, where FLO is the primary interface
  useEffect(() => { if (askOpen && !onFlo) nav("/"); }, [askOpen, onFlo, nav]);
  const [q, setQ] = useState("");
  const gov = useQuery({ queryKey: ["gov"], queryFn: () => api("/api/governance/status") });
  const pending = useQuery({ queryKey: ["approvals", "pending"], queryFn: () => api("/api/approvals?status=pending"), refetchInterval: 30000 });
  const pendingCount = (pending.data?.approvals ?? []).filter((a: any) => me && a.requested_by !== me.user_id).length;
  const recents = useQuery({ queryKey: ["conversations", ""], enabled: can("ask:use"),
    queryFn: () => api<{ conversations: { id: string; title: string }[] }>("/api/conversations") });
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const toggle = () => setCollapsed((c) => {
    try {
      localStorage.setItem("flo.sidebar", c ? "open" : "collapsed");
    } catch { /* storage unavailable */ }
    return !c;
  });
  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-gold focus:p-2 focus:text-bg">Skip to content</a>
      <nav className={cn("hidden shrink-0 flex-col border-r border-line bg-side transition-[width] duration-200 md:flex", collapsed ? "w-[68px]" : "w-64")} aria-label="Primary">
        <div className={cn("flex items-center px-3.5 py-4", collapsed ? "justify-center" : "justify-between")}>
          <NavLink to="/" aria-label="FLO home"><Logo collapsed={collapsed} /></NavLink>
          {!collapsed && <Button size="icon" variant="ghost" onClick={toggle} aria-label="Collapse sidebar" title="Collapse sidebar"><PanelLeftClose className="h-4 w-4" /></Button>}
        </div>
        {collapsed && <Button size="icon" variant="ghost" className="mx-auto mb-2" onClick={toggle} aria-label="Expand sidebar" title="Expand sidebar"><PanelLeftOpen className="h-4 w-4" /></Button>}
        <div className="flex-1 space-y-0.5 overflow-y-auto scroll-thin px-2">
          <NavLink to="/" end title={t("flo", lang)} className={({ isActive }) => cn("mb-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium",
            collapsed && "justify-center px-0", isActive ? "bg-gold/10 text-gold ring-1 ring-gold/50" : "text-ink hover:bg-card/60")}>
            <Sparkles className="h-4 w-4 shrink-0 text-gold" />{!collapsed && t("flo", lang)}
          </NavLink>
          {!collapsed && can("ask:use") && (
            <div className="mb-3">
              <button onClick={() => nav("/?new=1")} className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-card/60 hover:text-ink">
                <Plus className="h-3.5 w-3.5" />New conversation</button>
              {(recents.data?.conversations ?? []).slice(0, 5).map((c) => (
                <button key={c.id} onClick={() => nav(`/?c=${c.id}`)} title={c.title}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-xs text-muted hover:bg-card/60 hover:text-ink">
                  <MessageSquare className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{c.title}</span></button>
              ))}
            </div>
          )}
          {!collapsed && <div className="px-3 pb-1 pt-2 text-[10px] font-medium uppercase tracking-[0.16em] text-muted/80">Enterprise modules</div>}
          {me?.navigation.map((n) => {
            const Icon = ICONS[n.id] ?? Gauge;
            return (
              <NavLink key={n.id} to={`/${n.id}`} title={t(n.id, lang)} aria-label={collapsed ? t(n.id, lang) : undefined}
                className={({ isActive }) => cn("flex items-center gap-2 rounded-lg px-3 py-2 text-sm", collapsed && "justify-center px-0",
                  isActive ? "bg-card text-ink ring-1 ring-gold/40" : "text-muted hover:bg-card/60 hover:text-ink")}>
                <Icon className="h-4 w-4 shrink-0" />{!collapsed && t(n.id, lang)}
                {n.id === "approvals" && pendingCount > 0 && !collapsed && <span className="ml-auto rounded-full bg-gold px-1.5 text-[10px] font-semibold text-bg">{pendingCount}</span>}
              </NavLink>
            );
          })}
        </div>
        {!collapsed && (
          <div className="space-y-1 border-t border-line p-3 text-[11px] text-muted">
            <div className="flex items-center gap-1"><ShieldCheck className="h-3 w-3 text-pos" />Policy {gov.data?.policy_version ?? "…"}</div>
            <div>PDP: {gov.data?.pdp ?? "…"}</div>
            <div>Model: {gov.data?.model?.provider === "mock" ? "in-process deterministic" : gov.data?.model?.model ?? "…"}</div>
            <div>Integrations: mock adapters</div>
            <Badge tone="gold">{t("synthetic", lang)} · independent demo</Badge>
          </div>
        )}
      </nav>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-line bg-side/60 px-4 py-2">
          <form className="flex-1 min-w-[180px] max-w-md" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) nav(`/knowledge?q=${encodeURIComponent(q)}`); }}>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search", lang)} aria-label="Global search" />
          </form>
          {!onFlo && <Select aria-label="Date range" value={filters.months} onChange={(e) => setFilters({ months: Number(e.target.value) as 12 | 24 })}>
            <option value={12}>Trailing 12 months</option><option value={24}>Trailing 24 months</option>
          </Select>}
          {!onFlo && (can("finance:read") || can("investment:read")) && (
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
            {!onFlo && <Button variant="primary" size="sm" onClick={() => nav("/")}><Bot className="h-4 w-4" />{t("ask", lang)}</Button>}
            <div className="ml-2 hidden text-right text-xs sm:block"><div className="font-medium">{me?.display_name}</div><div className="text-muted">{me?.title}</div></div>
            <Button size="icon" variant="ghost" onClick={() => { logout(); nav("/"); }} aria-label="Sign out" title="Switch user"><LogOut className="h-4 w-4" /></Button>
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-line px-2 py-1 md:hidden" aria-label="Primary mobile">
          <NavLink to="/" end className="whitespace-nowrap rounded px-2 py-1 text-xs text-gold">{t("flo", lang)}</NavLink>
          {me?.navigation.map((n) => <NavLink key={n.id} to={`/${n.id}`} className="whitespace-nowrap rounded px-2 py-1 text-xs text-muted">{t(n.id, lang)}</NavLink>)}
        </nav>
        <main id="main" className={cn("min-h-0 flex-1", onFlo ? "overflow-hidden" : "overflow-y-auto scroll-thin p-4 md:p-6")}>{children}</main>
      </div>
    </div>
  );
}
