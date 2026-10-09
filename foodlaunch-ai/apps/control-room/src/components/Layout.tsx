import { ReactNode, useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api, login, logout, post, waitForJob } from "../api";
import { can, useApp } from "../context";
import { useAction } from "../hooks";
import { Short, Status } from "./ui";

const NAV = [
  ["/", "Portfolio overview"],
  ["/brief", "Brief intake"],
  ["/board", "Delivery board"],
  ["/requirements", "Requirements"],
  ["/engineering", "Engineering"],
  ["/quality", "Quality"],
  ["/releases", "Release center"],
  ["/incidents", "Incidents"],
  ["/templates", "Scenario templates"],
  ["/evidence", "Evidence & audit"],
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
      <label htmlFor="account" className="text-xs text-cream-200">Signed in as</label>
      <select
        id="account"
        className="rounded-md border border-navy-600 bg-navy-800 px-2 py-1 text-sm text-cream-50"
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
    <div className={`flex flex-wrap items-center gap-2 ${compact ? "" : "rounded-lg bg-navy-800 p-2"}`}>
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
      <button className="btn border border-cream-300/40 text-cream-50 hover:bg-navy-700" disabled={!allowed || action.busy || status === "running"} onClick={reset}>
        Reset Demo
      </button>
      {!allowed && <span className="text-xs text-cream-200">Sign in with a demo account (not the viewer) to control the demo</span>}
      {action.message && <span className={`text-xs ${action.message.kind === "error" ? "text-brick-100" : "text-leaf-100"}`}>{action.message.text}</span>}
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
      <div className="bg-amber-100 px-4 py-1 text-center text-xs font-semibold text-amber-700" role="note">
        DEMO ENVIRONMENT: fictional company, synthetic data, mock payments. No real charges, messages, ad spend or external deployments.
      </div>
      <header className="bg-navy-900 px-4 py-3 text-cream-50">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#1a2d52" /><path d="M9 22c6-1 11-6 13-13-6 1-12 5-13 13z" fill="#3f9563" /></svg>
            <div>
              <div className="text-lg font-semibold leading-tight">FoodLaunch AI</div>
              <div className="text-xs text-cream-200">Food Beverage Food Care Pvt Ltd (fictional) · delivery control room</div>
            </div>
          </div>
          <AccountSwitcher />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <DemoControls compact />
          <div className="flex items-center gap-2">
            <label htmlFor="run" className="text-xs text-cream-200">Run</label>
            <select id="run" className="max-w-[300px] rounded-md border border-navy-600 bg-navy-800 px-2 py-1 text-sm" value={runId ?? ""} onChange={(e) => setRunId(e.target.value || null)}>
              {runs.length === 0 && <option value="">No runs yet</option>}
              {runs.map((r) => (<option key={r.id} value={r.id}>{r.id} · {r.status}</option>))}
            </select>
          </div>
          <span className="text-xs text-cream-200">Live storefront:</span>
          <a className="text-xs font-semibold text-leaf-100 underline" href={system?.storefront?.url ?? "#"} target="_blank" rel="noreferrer">
            {system?.storefront?.url ?? "-"}
          </a>
          <span className="text-xs text-cream-200">
            {process ? <>release {process.release_id} @ <Short value={process.revision} n={8} /></> : "not running"}
          </span>
          {fault && <span className="rounded bg-brick-700 px-2 py-0.5 text-xs font-semibold">Injected fault active: inventory timeout</span>}
          <span className="text-xs text-cream-200">Mode: {system?.live_mode?.available ? "DEMO (LIVE available)" : "DEMO (LIVE not configured)"}</span>
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav aria-label="Primary" className="border-b border-cream-300 bg-cream-50 md:w-56 md:border-b-0 md:border-r">
          <ul className="flex flex-row flex-wrap gap-1 p-2 md:flex-col">
            {NAV.map(([to, label]) => (
              <li key={to}>
                <NavLink to={to} end={to === "/"} className={({ isActive }) => `block rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-navy-900 font-semibold text-cream-50" : "text-navy-800 hover:bg-cream-200"}`}>
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
