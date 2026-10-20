import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Activity, BarChart3, ClipboardCheck, Database, Gauge, Globe2, Lightbulb, MessageSquare, Network, Search, TrendingUp } from "lucide-react";
import { useApp, type Mode } from "../lib/state";
import { fmtDate, fmtInt } from "../lib/format";
import { FloPanel } from "../assistant/Flo";
import { Badge, Button, Monogram } from "./ui";

const NAV = [
  { to: "/", label: "Executive overview", icon: Gauge },
  { to: "/ask", label: "Ask Flo", icon: MessageSquare },
  { to: "/explorer", label: "Conversation explorer", icon: Search },
  { to: "/maps", label: "Insight maps", icon: Network },
  { to: "/opportunities", label: "Opportunity portfolio", icon: Lightbulb },
  { to: "/decisions", label: "Decisions and actions", icon: ClipboardCheck },
  { to: "/impact", label: "Impact review", icon: TrendingUp },
  { to: "/languages", label: "Language intelligence", icon: Globe2 },
  { to: "/quality", label: "Data quality and imports", icon: Database },
  { to: "/observability", label: "Observability and evaluation", icon: Activity },
];

function Sidebar() {
  return (
    <nav aria-label="Main" className="flex w-60 shrink-0 flex-col bg-sidebar text-white">
      <div className="flex items-center gap-2 px-4 py-4">
        <BarChart3 className="h-5 w-5 text-[#7fc4cb]" aria-hidden />
        <div>
          <div className="text-[15px] font-semibold leading-tight">ConvoLens AI</div>
          <div className="text-[11px] text-white/60">Customer Conversation Intelligence</div>
        </div>
      </div>
      <ul className="flex-1 space-y-0.5 px-2">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink to={to} end={to === "/"}
              className={({ isActive }) => `flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] ${isActive ? "bg-sidebar-sel font-medium text-white" : "text-white/75 hover:bg-sidebar-sel/60 hover:text-white"}`}>
              {({ isActive }) => (<><Icon className="h-4 w-4" aria-hidden />{label}{isActive && <span className="sr-only">(current page)</span>}</>)}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="px-4 py-3 text-[10px] leading-snug text-white/50">Local application. No SSO or role-based access control is implemented.</div>
    </nav>
  );
}

function TopBar() {
  const { datasets, dataset, setDatasetId, mode, setMode, floOpen, setFloOpen, status } = useApp();
  const path = useLocation().pathname;
  const options = datasets.filter((d) => d.status === "ready" && (mode === "demo" ? d.synthetic : !d.synthetic));
  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-line bg-white px-5 py-2.5">
      <div role="radiogroup" aria-label="Operating mode" className="inline-flex rounded-md border border-line p-0.5">
        {(["demo", "connected"] as Mode[]).map((m) => (
          <button key={m} role="radio" aria-checked={mode === m} type="button" onClick={() => setMode(m)}
            className={`rounded px-2.5 py-1 text-xs font-medium ${mode === m ? (m === "demo" ? "bg-amber-light text-amber" : "bg-teal-light text-teal") : "text-muted hover:text-ink"}`}>
            {m === "demo" ? "Demonstration" : "Connected analysis"}
          </button>
        ))}
      </div>
      <label className="flex items-center gap-2 text-xs text-muted">
        Dataset
        <select className="max-w-[300px] rounded-md border border-line bg-white px-2 py-1 text-sm text-ink" value={dataset?.id ?? ""} onChange={(e) => setDatasetId(e.target.value)} disabled={!options.length}>
          {!options.length && <option value="">{mode === "connected" ? "No imported dataset yet" : "No demonstration data"}</option>}
          {options.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </label>
      {dataset && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {dataset.synthetic ? <Badge tone="amber">Synthetic fixtures</Badge> : <Badge tone="teal">Imported data</Badge>}
          <span className="tnum">{fmtInt(dataset.conversations)} conversations selected</span>
          <span aria-label="Data freshness">Data {fmtDate(dataset.data_from)} – {fmtDate(dataset.data_to)} · imported {fmtDate(dataset.imported_at)}</span>
          <span>Analysis: {dataset.active_analysis.startsWith("rules") ? "rules-based" : dataset.active_analysis}</span>
        </div>
      )}
      <div className="ml-auto flex items-center gap-2">
        {mode === "connected" && status && <Badge tone={status.model?.configured ? "green" : "red"}>{status.model?.configured ? `Model: ${status.model.model_id}` : "Model not configured"}</Badge>}
        {!floOpen && path !== "/ask" && <Button size="sm" onClick={() => setFloOpen(true)}><Monogram size={18} />Open Flo</Button>}
      </div>
    </header>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { mode, datasets, loadError } = useApp();
  const onAskPage = useLocation().pathname === "/ask";
  const noImported = mode === "connected" && !datasets.some((d) => !d.synthetic && d.status === "ready");
  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2">Skip to content</a>
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <div className="flex min-h-0 flex-1">
          <main id="main" className="min-w-0 flex-1 overflow-y-auto px-6 py-5">
            {loadError && <div role="alert" className="mb-4 rounded-md border border-[#e8c3c6] bg-red-light px-3 py-2 text-sm text-red">Cannot load datasets: {loadError}</div>}
            {mode === "demo" && <div className="mb-4 rounded-md border border-[#ecd3ad] bg-amber-light px-3 py-1.5 text-xs text-[#7a4805]">Demonstration mode: synthetic fixture conversations, rules-based analysis, no model calls. Figures describe the fixtures only.</div>}
            {noImported && <div className="mb-4 rounded-md border border-line bg-white px-3 py-2 text-sm text-muted">Connected analysis needs an imported dataset. Import the Kaggle file on <NavLink className="text-teal underline" to="/quality">Data quality and imports</NavLink>.</div>}
            {children}
          </main>
          {!onAskPage && <FloPanel />}
        </div>
      </div>
    </div>
  );
}
