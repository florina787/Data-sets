import { ReactNode, useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api, login, logout, post, waitForJob } from "../api";
import { can, useApp } from "../context";
import { useAction } from "../hooks";
import { CopilotDrawer, openCopilot } from "../screens/Copilot";
import { FriesCarton } from "./Illustrations";
import { Short, Status } from "./ui";

const NAV: [string, [string, string][]][] = [
  ["Executive", [
    ["/", "Executive Command"],
    ["/copilot", "Ask Copilot"],
  ]],
  ["Quality & Inspection", [
    ["/quality-intel", "Quality Intelligence"],
    ["/inspection", "Potato Inspection"],
    ["/evaluation", "Model Evaluation Lab"],
  ]],
  ["Operations Intelligence", [
    ["/inventory", "Inventory"],
    ["/sales", "Sales & Promotions"],
  ]],
  ["Risk, Compliance & ESG", [
    ["/compliance", "Compliance & Food Safety"],
  ]],
  ["AI Platform", [
    ["/agents", "Agent Intelligence"],
    ["/observability", "System Observability"],
  ]],
  ["Digital Delivery", [
    ["/delivery", "Delivery overview"],
    ["/brief", "Brief intake"],
    ["/board", "Delivery board"],
    ["/requirements", "Requirements"],
    ["/engineering", "Engineering"],
    ["/quality", "Quality"],
    ["/releases", "Release center"],
    ["/incidents", "Incidents"],
    ["/templates", "Scenario templates"],
    ["/evidence", "Evidence & audit"],
  ]],
];

function AccountSwitcher() {
  const { user, refreshAll } = useApp();
  const [accounts, setAccounts] = useState<any>(null);
  const action = useAction();
  useEffect(() => {
    api("/api/auth/demo-accounts").then(setAccounts).catch(() => setAccounts(null));
  }, []);
  useEffect(() => {
    // Re-validate the server-side session; a 401 clears the local sign-in state.
    if (!user) return;
    const check = () => api("/api/auth/me").catch(() => undefined);
    check();
    const id = window.setInterval(check, 10000);
    return () => window.clearInterval(id);
  }, [user]);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <FloAvatar />
      <label htmlFor="account" className="sr-only">Signed in as</label>
      <select
        id="account"
        aria-label="Signed in as"
        className="rounded-lg border border-surface-line bg-surface-raised px-2 py-1.5 text-sm text-navy-800"
        value={user?.username ?? ""}
        disabled={action.busy || !accounts}
        onChange={(e) =>
          action.run(async () => {
            if (!e.target.value) await logout();
            else await login(e.target.value, accounts.password);
            refreshAll();
          })
        }
        title="Signs in with a local demo account. Permissions are checked by the server on every action. This is not enterprise SSO."
      >
        <option value="">Not signed in</option>
        {accounts?.accounts.map((a: any) => (
          <option key={a.username} value={a.username}>{a.display_name}</option>
        ))}
      </select>
      {action.message?.kind === "error" && <span className="text-xs text-brick-100">{action.message.text}</span>}
    </div>
  );
}

export function DemoControls({ compact = false }: { compact?: boolean }) {
  const { user, demo, refreshAll } = useApp();
  const action = useAction();
  const allowed = can(user, "demo.control");
  const status = demo?.status ?? "idle";
  const run = () =>
    action.run(async () => {
      await post("/api/demo/run");
      refreshAll();
    });
  const reset = () =>
    action.run(async () => {
      if (!window.confirm("Reset the demo? All runs, releases and storefront orders are wiped and the baseline is redeployed.")) return;
      const { job_id } = await post("/api/demo/reset");
      await waitForJob(job_id);
      await logout(); // the reset recreates accounts and sessions
      refreshAll();
    }, "Demo reset: baseline v1.0 redeployed. Sign in again.");
  return (
    <div className={`flex flex-wrap items-center gap-2 ${compact ? "" : "rounded-lg bg-surface-raised p-2"}`}>
      <span className="text-xs text-cream-200">Guided demo</span>
      <Status value={status} />
      {status === "running" ? (
        <button className="btn bg-amber-100 text-amber-700" disabled={!allowed || action.busy || demo?.pause_requested}
          onClick={() => action.run(async () => { await post("/api/demo/pause"); refreshAll(); })}>
          {demo?.pause_requested ? "Pausing after step…" : "Pause"}
        </button>
      ) : (
        <button className="btn-green" disabled={!allowed || action.busy || status === "done"} onClick={run}
          title={status === "done" ? "Finished. Reset Demo to run again." : undefined}>
          {status === "paused" || status === "failed" ? "Continue" : "Run Guided Demo"}
        </button>
      )}
      <button className="btn-ghost" disabled={!allowed || action.busy || status === "running"} onClick={reset}>
        Reset Demo
      </button>
      {!allowed && <span className="text-xs text-cream-200">Sign in with a demo account (not the viewer) to control the demo</span>}
      {action.message && <span className={`text-xs ${action.message.kind === "error" ? "text-brick-100" : "text-leaf-100"}`}>{action.message.text}</span>}
    </div>
  );
}

/** Jerry, the AI assistant mascot: a smiling fries carton (original illustration, not a person). */
export function Jerry({ size = 36 }: { size?: number }) {
  return <FriesCarton size={size} />;
}

/** Flo's portrait: served from /flo-portrait.jpg once supplied; a neutral monogram until then. */
function FloAvatar() {
  const [missing, setMissing] = useState(false);
  return missing ? (
    <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-royal-500 to-ice-400 text-sm font-semibold text-white ring-2 ring-surface-line"
      title="Flo — portrait not supplied yet (add apps/control-room/public/flo-portrait.jpg)" aria-label="Flo">F</span>
  ) : (
    <img src="/flo-portrait.jpg" alt="Flo" onError={() => setMissing(true)} className="h-8 w-8 rounded-full object-cover ring-2 ring-royal-500" />
  );
}

function Meter({ label, value, title }: { label: string; value: number | null; title: string }) {
  const tone = value === null ? "bg-navy-600" : value >= 85 ? "bg-red-500" : value >= 65 ? "bg-amber-500" : "bg-ice-400";
  return (
    <span className="pill" title={title}>
      <span className="text-navy-600">{label}</span>
      <span className="font-mono text-navy-900">{value === null ? "–" : `${value.toFixed(0)}%`}</span>
      <span className="h-1.5 w-10 overflow-hidden rounded-full bg-surface-line" aria-hidden>
        <span className={`block h-full ${tone}`} style={{ width: `${Math.min(100, value ?? 0)}%` }} />
      </span>
    </span>
  );
}

function SystemPills() {
  const { system } = useApp();
  const [r, setR] = useState<any>(null);
  useEffect(() => {
    let live = true;
    const tick = () => api("/api/system/resources").then((d) => live && setR(d)).catch(() => undefined);
    tick();
    const id = window.setInterval(tick, 5000);
    return () => { live = false; window.clearInterval(id); };
  }, []);
  const llm = r?.llm;
  const qwen = !system?.live_mode?.available ? { dot: "bg-navy-600", text: "Local model: not configured" }
    : llm?.stats?.errors && !llm?.stats?.ok ? { dot: "bg-amber-500", text: `Local model: ${llm.model} (errors)` }
      : { dot: "bg-emerald-500", text: `Local model: ${system.live_mode.model}` };
  return (
    <div className="flex flex-wrap items-center gap-2" aria-label="System status">
      <span className="pill" title={system?.live_mode?.reason ?? "Answers can be written by the local model server (LIVE)"}>
        <span className={`h-2 w-2 rounded-full ${qwen.dot}`} aria-hidden />{qwen.text}
      </span>
      <Meter label="CPU" value={r?.cpu_percent ?? null} title={r ? `Machine CPU, ${r.cpu_count} cores; backend process ${r.process.cpu_percent}% (${r.source})` : "Loading"} />
      <Meter label="RAM" value={r?.ram_percent ?? null} title={r ? `${r.ram_used_gb} of ${r.ram_total_gb} GB used; backend process ${r.process.rss_mb} MB` : "Loading"} />
    </div>
  );
}

function Notifications() {
  const { system } = useApp();
  const [items, setItems] = useState<{ text: string; to: string }[]>([]);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const load = () => api("/api/enterprise/overview").then((d) => {
      const out: { text: string; to: string }[] = [];
      d.campaign_stock_risk?.filter((x: any) => x.risk === "high").forEach((x: any) => out.push({ text: `${x.name}: high stock risk for the weekend campaign`, to: "/inventory" }));
      d.compliance?.issues?.filter((i: any) => i.severity === "critical").forEach((i: any) => out.push({ text: `${i.name} on ${i.channel}: ${i.detail}`, to: "/compliance" }));
      d.inventory_alerts?.filter((a: any) => a.status === "critical").forEach((a: any) => out.push({ text: `${a.name} at ${a.warehouse}: ${a.days_of_cover} days of cover`, to: "/inventory" }));
      setItems(out);
    }).catch(() => undefined);
    load();
    const id = window.setInterval(load, 60000);
    return () => window.clearInterval(id);
  }, []);
  const all = system?.fault?.active ? [{ text: "Injected demo fault active: inventory timeout", to: "/incidents" }, ...items] : items;
  return (
    <div className="relative">
      <button className="pill hover:border-royal-500" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={`Notifications: ${all.length}`}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
        {all.length > 0 && <span className="rounded-full bg-red-500 px-1.5 text-[10px] font-semibold text-white">{all.length}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-surface-line bg-surface-raised p-2 shadow-card" role="dialog" aria-label="Notifications">
          {all.length === 0 ? <p className="p-2 text-sm text-navy-600">Nothing needs attention.</p> : (
            <ul className="space-y-1 text-sm">{all.map((n) => (
              <li key={n.text}><NavLink to={n.to} onClick={() => setOpen(false)} className="block rounded-lg px-2 py-1.5 text-navy-800 hover:bg-surface-card">{n.text}</NavLink></li>
            ))}</ul>
          )}
          <p className="px-2 pt-1 text-[11px] text-navy-600">Derived from current stock, compliance and fault data.</p>
        </div>
      )}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { system, runs, runId, setRunId } = useApp();
  const fault = system?.fault?.active;
  const process = system?.storefront?.process;
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <div className="border-b border-gold-500/20 bg-[#0b1a2c] px-4 py-1 text-center text-[11px] font-medium tracking-wide text-gold-300" role="note">
        DEMO ENVIRONMENT: fictional company, synthetic data, mock payments. No real charges, messages, ad spend or external deployments.
      </div>
      <header className="border-b border-surface-line bg-surface-side/90 px-4 py-3 backdrop-blur md:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Jerry size={40} />
            <div>
              <div className="text-lg font-semibold leading-tight tracking-tight text-navy-900">Flo &amp; Jerry <span className="text-navy-600">—</span> <span className="bg-gradient-to-r from-royal-400 to-ice-400 bg-clip-text text-transparent">Food Copilot 2.0</span></div>
              <div className="text-xs text-navy-600">Agentic AI for End-to-End Food Manufacturing Excellence</div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SystemPills />
            <Notifications />
            <button className="btn-primary" onClick={() => openCopilot()}><span aria-hidden>✦</span> Ask Copilot</button>
            <AccountSwitcher />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-surface-line/70 pt-2.5 text-sm">
          <DemoControls compact />
          <div className="flex items-center gap-2">
            <label htmlFor="run" className="text-xs text-navy-600">Run</label>
            <select id="run" className="max-w-[300px] rounded-lg border border-surface-line bg-surface-raised px-2 py-1 text-xs" value={runId ?? ""} onChange={(e) => setRunId(e.target.value || null)}>
              {runs.length === 0 && <option value="">No runs yet</option>}
              {runs.map((r) => (<option key={r.id} value={r.id}>{r.id} · {r.status}</option>))}
            </select>
          </div>
          <span className="text-xs text-navy-600">Live storefront:</span>
          <a className="text-xs font-semibold text-ice-400 underline-offset-2 hover:underline" href={system?.storefront?.url ?? "#"} target="_blank" rel="noreferrer">
            {system?.storefront?.url ?? "-"}
          </a>
          <span className="text-xs text-navy-600">
            {process ? <>release {process.release_id} @ <Short value={process.revision} n={8} /></> : "not running"}
          </span>
          {fault && <span className="rounded bg-brick-700 px-2 py-0.5 text-xs font-semibold text-white">Injected fault active: inventory timeout</span>}
          <span className="text-xs text-navy-600">Mode: {system?.live_mode?.available ? "DEMO (LIVE available)" : "DEMO (LIVE not configured)"}</span>
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav aria-label="Primary" className="border-b border-surface-line bg-surface-side/70 md:w-60 md:shrink-0 md:border-b-0 md:border-r">
          {NAV.map(([group, items]) => (
            <div key={group} className="px-3 pt-4">
              <div className="label px-3 pb-1.5">{group}</div>
              <ul className="flex flex-row flex-wrap gap-0.5 md:flex-col">
                {items.map(([to, label]) => (
                  <li key={to}>
                    <NavLink to={to} end={to === "/"} className={({ isActive }) => `relative block rounded-lg px-3 py-1.5 text-sm transition-colors ${isActive ? "bg-royal-600/15 font-medium text-white before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-ice-400" : "text-navy-700 hover:bg-surface-raised hover:text-navy-900"}`}>
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <div className="m-3 mt-6 flex items-center gap-2 rounded-xl border border-surface-line bg-surface-card/70 p-3 text-xs text-navy-600">
            <Jerry size={28} />
            <span>Jerry answers from cited data and never takes actions.</span>
          </div>
        </nav>
        <main id="main" className="min-w-0 flex-1 p-4 md:p-6 lg:p-8">{children}</main>
      </div>
      <CopilotDrawer />
    </div>
  );
}
