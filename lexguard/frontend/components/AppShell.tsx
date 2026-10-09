"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppState } from "@/hooks/useAppState";
import { Badge } from "@/components/ui";
import { humanize } from "@/lib/format";

const NAV: { section: string; items: [string, string][] }[] = [
  { section: "Work", items: [["/", "Copilot"], ["/matters", "Matters"], ["/matterguard", "MatterGuard"], ["/assurance", "WorkProduct Assurance"],
    ["/knowledge", "Knowledge"], ["/playbooks", "Playbooks"]] },
  { section: "Govern", items: [["/control-tower", "Control Tower"], ["/valueiq", "ValueIQ"], ["/evaluation", "Evaluation Lab"],
    ["/changeops", "ChangeOps"], ["/inventory", "AI Inventory"], ["/audit", "Audit"]] },
  { section: "Reference", items: [["/use-cases", "Use Cases"], ["/admin", "Admin / Configuration"]] },
];

export function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5 4 5.5v6.1c0 4.6 3.3 8.6 8 9.9 4.7-1.3 8-5.3 8-9.9V5.5l-8-3Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="m8.5 12 2.4 2.4 4.6-4.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { users, userId, setUserId, user, apiStatus, demoMode } = useAppState();
  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <div className="brand-mark"><Logo />LexGuard Copilot</div>
          <div className="brand-tag">Govern AI. Protect matters. Prove value.</div>
        </div>
        <nav className="nav">
          {NAV.map((g) => (
            <div key={g.section} style={{ display: "contents" }}>
              <div className="nav-section">{g.section}</div>
              {g.items.map(([href, label]) => (
                <Link key={href} href={href} className={path === href ? "active" : ""} aria-current={path === href ? "page" : undefined}>{label}</Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">Sterling &amp; Hamilton LLP (fictional)<br />All data is synthetic.</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <span className="small muted">Legal AI Control Tower + Enterprise Legal Copilot</span>
          <span className="spacer" />
          {apiStatus === "offline" && <Badge tone="bad">API offline</Badge>}
          {apiStatus === "online" && demoMode && <Badge tone="info" title="No API key required. Zero paid LLM calls.">DEMO MODE · 0 paid LLM calls</Badge>}
          <label htmlFor="user-switch">Signed in as</label>
          <select id="user-switch" className="select" value={userId} onChange={(e) => setUserId(e.target.value)}
            title="Demo identity switcher (production uses SSO)">
            {users.length === 0 && <option value={userId}>{userId}</option>}
            {users.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} — {humanize(u.role)}</option>)}
          </select>
          {user && <Badge tone="neutral">{user.practice ?? "Firm-wide"}</Badge>}
        </header>
        {apiStatus === "offline" && (
          <div className="error-box" role="alert" style={{ margin: "12px 20px 0" }}>
            The LexGuard API is not reachable. Start the backend with <code>uvicorn app.main:app --port 8000</code> (see README).
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
