import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { AlertTriangle, CheckCircle2, Download } from "lucide-react";
import { GraphA, GraphB, GraphC, GraphD, GraphE, GraphF, GraphG, GraphH, KpiRow } from "../components/charts";
import { ChatPanel } from "../components/ChatPanel";
import { InvestmentGraph } from "../components/InvestmentGraph";
import { AgentGraph } from "../components/AgentGraph";
import { SherinAvatar } from "../components/SherinAvatar";
import { Badge, Card, StatusBadge } from "../components/ui";
import { reportUrl, useApi } from "../lib/api";
import { periodParams, useApp } from "../lib/store";
import { money, monthLabel } from "../lib/format";

function useWide() {
  const q = "(min-width: 1280px)";
  const [wide, setWide] = useState(() => typeof window !== "undefined" && window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const f = () => setWide(m.matches);
    m.addEventListener?.("change", f);
    return () => m.removeEventListener?.("change", f);
  }, []);
  return wide;
}

function Hero() {
  const s = useApp();
  const k = useApi<any>("/finance/kpis", periodParams(s));
  const net = k.data?.net_benefit;
  return (
    <div className="hero-gradient relative mb-4 overflow-hidden rounded-[22px] p-5 text-white shadow-lg">
      <div className="flex flex-wrap items-center gap-5">
        <SherinAvatar size="xl" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-flo-200">Financial Command Center · {s.periodKind === "month" ? monthLabel(s.month) : k.data?.period?.label}</p>
          <h1 className="mt-1 font-display text-3xl font-semibold leading-tight md:text-4xl">Here is what FLO Bank earned, what it spent, and what I was worth.</h1>
          <p className="mt-2 max-w-3xl text-sm text-flo-100">
            Net AI economic benefit this period: <strong className="text-white">{money(net, s.currency)}</strong>. Every figure below comes from the same validated engine; estimates and forecasts are labelled, and demo data is marked synthetic.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <a href={reportUrl({ ...periodParams(s), format: "md" })} className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-sm font-semibold text-flo-900 shadow hover:bg-flo-50"><Download className="h-4 w-4" />Executive report</a>
          <a href={reportUrl({ ...periodParams(s), format: "csv" })} className="inline-flex items-center gap-1.5 rounded-full border border-flo-200/60 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"><Download className="h-4 w-4" />CSV</a>
        </div>
      </div>
    </div>
  );
}

function ContextPanel() {
  const s = useApp();
  const alerts = useApi<any[]>("/metrics/alerts", { currency: s.currency, dc: s.dc }, 30000);
  const rec = useApi<any>("/finance/reconciliation", periodParams(s));
  const agents = useApi<any>("/harness/agents", periodParams(s), 4000);
  const runs = useApi<any[]>("/harness/runs", undefined, 4000);
  const latest = runs.data?.[0];
  return (
    <div className="space-y-3 p-3">
      <section>
        <h2 className="mb-1.5 flex items-center justify-between font-display text-base font-semibold text-flo-900">Investment web graph <Link to="/guardian" className="text-xs font-sans text-flo-700">Guardian →</Link></h2>
        <InvestmentGraph height={420} compact />
      </section>
      <section>
        <h2 className="mb-1.5 flex items-center justify-between font-display text-base font-semibold text-flo-900">Agent harness <Link to="/harness" className="text-xs font-sans text-flo-700">Open →</Link></h2>
        <AgentGraph agents={agents.data?.agents ?? []} run={latest} cur={s.currency} height={90} mini />
        {latest && <p className="mt-1 flex items-center gap-1.5 text-xs text-muted">Latest run <code>{latest.id}</code> <StatusBadge s={latest.status} /></p>}
        <ul className="mt-2 space-y-1">
          {(agents.data?.agents ?? []).slice().sort((a: any, b: any) => (b.economic_contribution ?? -1e12) - (a.economic_contribution ?? -1e12)).slice(0, 6).map((a: any) => (
            <li key={a.id} className="flex items-center justify-between rounded-lg bg-flo-50 px-2 py-1 text-xs">
              <span className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${a.status === "running" ? "bg-flo-500 pulse-dot" : a.status === "waiting" ? "bg-gold" : "bg-[#C9D9D1]"}`} />{a.label.replace(" Agent", "")}</span>
              <span className="font-semibold text-flo-800 tnum">{money(a.economic_contribution, s.currency)}</span>
            </li>))}
        </ul>
      </section>
      <section>
        <h2 className="mb-1.5 font-display text-base font-semibold text-flo-900">Contextual intelligence</h2>
        <ul className="space-y-1.5">
          {(alerts.data ?? []).map((a) => (
            <li key={a.id} className={`flex items-start gap-1.5 rounded-lg border px-2 py-1.5 text-xs ${a.level === "ok" ? "border-line" : a.level === "breach" ? "border-[#EFC9C6] bg-red-light" : "border-[#EED9B5] bg-amber-light"}`}>
              {a.level === "ok" ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-flo-700" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 text-amber" />}
              <span><strong>{a.title}</strong> — {a.detail}</span>
            </li>))}
        </ul>
        {rec.data && (
          <div className="mt-2 rounded-lg border border-line p-2 text-xs">
            <div className="mb-1 flex items-center justify-between font-semibold text-flo-900">Books reconcile <Badge tone={rec.data.checks.every((c: any) => c.ok) ? "green" : "red"}>{rec.data.checks.filter((c: any) => c.ok).length}/{rec.data.checks.length}</Badge></div>
            <ul className="space-y-0.5 text-muted">{rec.data.checks.map((c: any) => <li key={c.name}>{c.ok ? "✓" : "✗"} {c.name}</li>)}</ul>
          </div>
        )}
      </section>
    </div>
  );
}

function Charts() {
  return (
    <div className="space-y-4 p-1">
      <GraphA /><GraphB /><GraphC /><GraphD /><GraphE /><GraphF /><GraphG /><GraphH />
    </div>
  );
}

export default function CommandCenter() {
  const wide = useWide();
  return (
    <div>
      <Hero />
      <KpiRow />
      <div className="mt-4">
        {wide ? (
          <PanelGroup direction="horizontal" autoSaveId="sherin-command-center" className="!overflow-visible" style={{ height: "calc(100vh - 120px)" }}>
            <Panel defaultSize={55} minSize={35} className="!overflow-y-auto scroll-thin pr-1"><Charts /></Panel>
            <PanelResizeHandle className="resize-handle mx-1" aria-label="Resize charts and chat" />
            <Panel defaultSize={25} minSize={18}><Card className="flex h-full flex-col overflow-hidden"><ChatPanel compact /></Card></Panel>
            <PanelResizeHandle className="resize-handle mx-1" aria-label="Resize chat and context" />
            <Panel defaultSize={20} minSize={14}><Card className="h-full overflow-y-auto scroll-thin"><ContextPanel /></Card></Panel>
          </PanelGroup>
        ) : (
          <div className="space-y-4">
            <Charts />
            <Card className="flex h-[640px] flex-col overflow-hidden"><ChatPanel compact /></Card>
            <Card><ContextPanel /></Card>
          </div>
        )}
      </div>
    </div>
  );
}
