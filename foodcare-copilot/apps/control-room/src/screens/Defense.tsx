import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, post } from "../api";
import { can, useApp } from "../context";
import { ProvenanceChip, SignInPrompt, Skeleton } from "../components/pulse/shared";
import { VisualList } from "../components/visuals/VisualRenderer";
import { openCopilot } from "./Copilot";

const TABS = { threats: "Threats", availability: "Availability", alerts: "Alerts", containment: "Containment", licenses: "Licence savings" };
type Tab = keyof typeof TABS;
const cad = (c: number) => `CAD ${(c / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/** Defense Command: threats, availability, alerts, guarded containment and licence savings. */
export default function Defense() {
  const { user } = useApp();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) in TABS ? (params.get("tab") as Tab) : "threats";
  if (!user) return <SignInPrompt what="Defense Command" />;
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow">Technology · Defense Command</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Security, availability &amp; savings</h1>
          <p className="mt-1 text-ink-muted">Simulated security and licence telemetry for the fictional company — no SIEM, EDR, scanner or billing system is connected. The storefront health check and its incidents are real records.</p>
        </div>
        <button className="btn-primary" onClick={() => openCopilot("Jerry, tell me where our threats are, whether malware or server downtime is affecting the business, and how much we can save on unused licenses")}><span aria-hidden>✦</span> Brief me</button>
      </header>
      <div role="tablist" aria-label="Defense Command" className="flex flex-wrap gap-1 border-b border-surface-line">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setParams({ tab: t })}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === t ? "border-champagne font-medium text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}>{TABS[t]}</button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "threats" && <Threats />}
        {tab === "availability" && <Availability />}
        {tab === "alerts" && <Alerts />}
        {tab === "containment" && <Containment />}
        {tab === "licenses" && <Licenses />}
      </div>
    </div>
  );
}

function Threats() {
  const [t, setT] = useState<any>(null);
  useEffect(() => { api("/api/defense/threats").then(setT); }, []);
  if (!t) return <Skeleton lines={6} />;
  const active = t.threats.filter((x: any) => x.status !== "resolved");
  const sevAxis = (k: string) => Math.max(0, ...active.filter((x: any) => x.type === k).map((x: any) => ({ critical: 100, high: 75, medium: 50, low: 25 } as any)[x.severity]));
  return (
    <div className="space-y-4">
      <div className="panel"><p className="text-lg font-semibold text-ink">{t.under_attack}</p>
        <p className="mt-1 text-sm text-ink-muted">{t.summary.confirmed_active} confirmed · {t.summary.suspected} suspected · {t.summary.alerts} alert(s) · {t.summary.malware_active} malware detection group(s). Alerts are detections, not proof of compromise.</p></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <VisualList visuals={[{ kind: "radar", title: "Enterprise threat radar", provenance: "synthetic", caption: "Highest active severity per category (critical = 100).",
          axes: [["malware", "Malware"], ["suspicious_auth", "Identity"], ["vulnerability", "Vulnerabilities"], ["misconfiguration", "Misconfiguration"], ["network_anomaly", "Network"]].map(([k, l]) => ({ label: l, value: sevAxis(k) })) }]} />
        <VisualList visuals={[{ kind: "kpis", title: "Active items by severity", provenance: "synthetic", items: ["critical", "high", "medium", "low"].map((s) => ({ label: s, value: String(t.summary.by_severity[s]), status: s === "critical" || s === "high" ? (t.summary.by_severity[s] ? "attention" : "good") : "unknown" })) }]} />
      </div>
      <VisualList visuals={[{ kind: "flow", title: "Exposure graph: detections → assets → business services", provenance: "synthetic", nodes: t.attack_paths.nodes, edges: t.attack_paths.edges, caption: t.attack_paths.note }]} />
      <section className="panel">
        <h2 className="text-lg font-semibold text-ink">Detections (grouped)</h2>
        <table className="table mt-2"><thead><tr><th>Severity</th><th>Classification</th><th>Type</th><th>Asset</th><th>Grouped</th><th>Services</th><th>Owner</th></tr></thead>
          <tbody>{t.threats.map((x: any) => (
            <tr key={x.dedup} className={x.status === "resolved" ? "opacity-50" : ""}><td>{x.severity}</td><td>{x.classification.replace(/_/g, " ")}</td><td>{x.type.replace(/_/g, " ")}</td><td>{x.asset_name}{x.protected && <span className="ml-1 chip border-[#B48CF0]/60 text-[#CDB4F7]">protected</span>}</td><td>{x.count}</td><td>{x.services.join(", ")}</td><td>{x.owner}</td></tr>
          ))}</tbody></table>
      </section>
    </div>
  );
}

function Availability() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api("/api/defense/downtime").then(setD); }, []);
  if (!d) return <Skeleton lines={6} />;
  return (
    <div className="space-y-4">
      <div className="panel text-sm"><b className="text-ink">Storefront health check:</b> <span className={d.live.storefront_reachable ? "text-leaf-700" : "text-brick-700"}>{d.live.storefront_reachable ? "answering" : "not answering"}</span> <ProvenanceChip kind="operational_record" />
        {d.correlations.map((c: any) => <p key={c.service} className="mt-2 text-ink-muted">{c.service}: {c.co_occurring_events.join(", ")} nearby in time. {c.statement}</p>)}</div>
      <VisualList visuals={[
        { kind: "timeline", title: "Incident timeline", events: [...d.outages.map((o: any) => ({ date: o.start.slice(0, 16).replace("T", " "), label: `${o.service} down ${o.minutes} min (${o.within_rto ? "within" : "exceeded"} RTO ${o.rto_min} min) — cause: ${o.cause_recorded ?? "not recorded"}`, provenance: "synthetic" })), ...d.live.incidents.map((i: any) => ({ date: (i.opened_at ?? "").slice(0, 16).replace("T", " "), label: `Incident ${i.id}: ${i.title} (${i.status})`, provenance: "operational_record" }))] },
        { kind: "bar", title: "Outage minutes vs RTO", unit: "minutes", provenance: "synthetic", items: d.outages.map((o: any) => ({ label: o.service, value: o.minutes, note: `RTO ${o.rto_min}` })) },
        { kind: "flow", title: "Business dependency graph", provenance: "synthetic", nodes: d.dependencies.flatMap((x: any) => [{ id: `svc:${x.service}`, label: x.service, group: "service", state: `RTO ${x.rto_min} min` }, ...x.depends_on.map((y: string) => ({ id: y, label: y, group: "dependency" }))]).filter((n: any, i: number, a: any[]) => a.findIndex((m) => m.id === n.id) === i), edges: d.dependencies.flatMap((x: any) => x.depends_on.map((y: string) => ({ source: y, target: `svc:${x.service}` }))) },
      ]} />
    </div>
  );
}

function Alerts() {
  const { user } = useApp();
  const [al, setAl] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api<{ alerts: any[] }>("/api/defense/alerts").then((d) => setAl(d.alerts));
  useEffect(() => { load(); }, []);
  const act = (id: string, state: string) => post(`/api/defense/alerts/${id}`, { state }).then(load).catch((e) => setErr((e as Error).message));
  const allowed = can(user, "alert.manage");
  if (!al) return <Skeleton lines={6} />;
  return (
    <section className="panel">
      <h2 className="text-lg font-semibold text-ink">Alerts (grouped and deduplicated)</h2>
      <p className="text-sm text-ink-muted">No notification channel is configured; alerts appear here only.{!allowed && " Your role can view alerts but not acknowledge them."}</p>
      {err && <p className="mt-2 text-sm text-brick-700" role="alert">{err}</p>}
      <ul className="mt-3 space-y-2" data-testid="alerts">{al.map((a) => (
        <li key={a.id} className={`rounded-xl border px-4 py-3 ${a.severity === "critical" ? "border-risk/60" : "border-surface-line"} bg-midnight/40`}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-medium text-ink">{a.title}</span>
            <span className="flex items-center gap-2 text-xs"><span className={a.severity === "critical" || a.severity === "high" ? "text-brick-700" : "text-amber-700"}>{a.severity}</span><span className="text-ink-faint">{a.state}{a.escalated ? " · escalated" : ""}</span><ProvenanceChip kind={a.provenance} /></span>
          </div>
          <p className="mt-1 text-xs text-ink-muted">{a.category} · owner {a.owner}{a.count > 1 ? ` · ${a.count} related events grouped` : ""}{a.evidence ? ` · ${a.evidence}` : ""}</p>
          {allowed && a.state !== "resolved" && <div className="mt-2 flex gap-2">{["acknowledged", "suppressed", "resolved"].map((s) => <button key={s} className="btn-ghost text-xs" onClick={() => act(a.id, s)}>{s === "acknowledged" ? "Acknowledge" : s === "suppressed" ? "Suppress" : "Resolve"}</button>)}</div>}
        </li>
      ))}</ul>
    </section>
  );
}

const ACTIONS: Record<string, string> = { isolate_endpoint: "Isolate endpoint", revoke_credential: "Revoke credential", disable_service_account: "Disable service account", block_indicator: "Block network indicator", pause_workload: "Pause noncritical workload", trigger_ir_workflow: "Trigger incident-response workflow" };
const ASSETS = [["WS-QA-014", "QA laptop 14 (endpoint)"], ["svc-reporting", "Reporting service account"], ["k8s/analytics/batch-reports", "Batch reports workload (low criticality)"], ["k8s/foodcare/storefront", "Storefront workload (customer-facing)"], ["SRV-ERP-01", "ERP server"], ["OT-REFRIG-03", "Cold store 3 refrigeration (protected OT)"], ["OT-LINE2-PLC", "Fry line 2 PLC (protected OT)"]];

function Containment() {
  const { user } = useApp();
  const [form, setForm] = useState({ action: "isolate_endpoint", asset_id: "WS-QA-014", indicator: "" });
  const [plan, setPlan] = useState<any>(null);
  const [list, setList] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [pw, setPw] = useState<Record<string, string>>({});
  const load = () => api("/api/defense/containment").then(setList);
  useEffect(() => { load(); }, []);
  const body = { action: form.action, asset_id: form.asset_id, indicator: form.indicator || null };
  const previewIt = (e: FormEvent) => { e.preventDefault(); setMsg(null); post("/api/defense/containment/preview", body).then(setPlan).catch((err) => setMsg((err as Error).message)); };
  const propose = () => post("/api/defense/containment", body).then(() => { setMsg("Proposed. It now needs approval by other people."); load(); }).catch((err) => setMsg((err as Error).message));
  const approve = (id: string) => post(`/api/defense/containment/${id}/approve`, { password: pw[id] ?? "" }).then(() => { setMsg("Approval recorded (step-up verified)."); load(); }).catch((err) => setMsg((err as Error).message));
  const execute = (id: string) => post(`/api/defense/containment/${id}/execute`, { idempotency_key: `ui-${id}` }).then((r: any) => { setMsg(r.result?.message ?? "Done"); load(); }).catch((err) => setMsg((err as Error).message));
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-risk/40 bg-brick-100/40 p-4 text-sm text-ink" role="note">
        <b>Controlled containment.</b> Preview first; proposing needs the engineer role; approval needs other people (two for high-impact actions) with step-up authentication, within 15 minutes. Protected OT, refrigeration, production-line and safety systems are refused. <b>Demo mode: execution is always a dry run — nothing is changed.</b>
      </div>
      <form className="panel grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={previewIt}>
        <label className="text-xs text-ink-muted">Action<select className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>{Object.entries(ACTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-xs text-ink-muted">Asset (explicit scope)<select className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" value={form.asset_id} onChange={(e) => setForm({ ...form, asset_id: e.target.value })}>{ASSETS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label className="text-xs text-ink-muted">Indicator (block only)<input className="mt-1 w-full rounded-lg border px-2 py-1.5 text-sm" value={form.indicator} onChange={(e) => setForm({ ...form, indicator: e.target.value })} placeholder="e.g. bad-domain.example" /></label>
        <button className="btn-ghost self-end" type="submit">Preview (dry run)</button>
      </form>
      {msg && <p className="text-sm text-champagne" role="status">{msg}</p>}
      {plan && (
        <section className="panel space-y-2 text-sm" data-testid="containment-plan">
          <h2 className="text-lg font-semibold text-ink">{plan.label} — {plan.asset.name}</h2>
          <p className="text-ink-muted">{plan.note} Impacted services: {plan.impacted_services.join(", ") || "none recorded"} · impact {plan.impact} · approvals needed {plan.required_approvals}.</p>
          <ul className="space-y-1">{plan.checks.map((c: any) => <li key={c.check} className={c.ok ? "text-leaf-700" : "text-brick-700"}>{c.ok ? "✓" : "✕"} {c.check}: {c.detail}</li>)}</ul>
          <p className="text-ink-muted"><b className="text-ink">Rollback:</b> {plan.rollback}</p>
          <p className="text-ink-muted"><b className="text-ink">Escalation:</b> {plan.escalation}</p>
          {plan.allowed && can(user, "containment.propose") && <button className="btn-primary" onClick={propose}>Propose for approval</button>}
          {plan.allowed && !can(user, "containment.propose") && <p className="text-xs text-ink-faint">Your role can preview but not propose containment.</p>}
        </section>
      )}
      <section className="panel">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold text-ink">Proposals</h2>
          {list && <span className={`chip ${list.chain.intact ? "border-teal/60 text-teal-soft" : "border-risk text-brick-700"}`}>{list.chain.intact ? `Tamper-evident log intact (${list.chain.entries} entries)` : "Log integrity check FAILED"}</span>}</div>
        {!list ? <Skeleton /> : list.proposals.length === 0 ? <p className="mt-2 text-sm text-ink-muted">No containment proposals.</p> : (
          <ul className="mt-3 space-y-2">{list.proposals.map((p: any) => (
            <li key={p.id} className="rounded-xl border border-surface-line bg-midnight/40 px-4 py-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2"><span className="text-ink">{ACTIONS[p.action]} · {p.asset_id}</span><span className="text-xs text-ink-faint">{p.status.replace(/_/g, " ")} · approvals {p.approvals.length}/{p.required_approvals} · proposed by {p.proposed_by}</span></div>
              {p.result && <p className="mt-1 text-xs text-champagne">{p.result.message}</p>}
              {p.status === "awaiting_approval" && can(user, "containment.approve") && user?.username !== p.proposed_by && (
                <div className="mt-2 flex flex-wrap items-center gap-2"><label className="sr-only" htmlFor={`pw-${p.id}`}>Re-enter your password</label>
                  <input id={`pw-${p.id}`} type="password" autoComplete="current-password" placeholder="Re-enter password (step-up)" className="rounded-lg border px-2 py-1 text-xs" value={pw[p.id] ?? ""} onChange={(e) => setPw({ ...pw, [p.id]: e.target.value })} />
                  <button className="btn-ghost text-xs" onClick={() => approve(p.id)}>Approve</button></div>
              )}
              {p.status === "approved" && can(user, "containment.propose") && <button className="btn-primary mt-2 text-xs" onClick={() => execute(p.id)}>Execute (dry run)</button>}
            </li>
          ))}</ul>
        )}
      </section>
    </div>
  );
}

function Licenses() {
  const [s, setS] = useState<any>(null);
  useEffect(() => { api("/api/defense/licenses").then(setS); }, []);
  if (!s) return <Skeleton lines={6} />;
  const t = s.totals;
  return (
    <div className="space-y-4">
      <VisualList visuals={[
        { kind: "kpis", title: "Licence waste and savings (estimated avoided expenditure)", provenance: "synthetic", items: [
          { label: "Unused units", value: t.unused.toLocaleString(), status: "watch" }, { label: "Unused spend / year", value: cad(t.unused_spend_annual_cents), status: "watch" },
          { label: "Renewal reduction / year", value: cad(t.renewal_reduction_annual_cents), status: "good" }, { label: "Realisable this quarter", value: cad(t.realizable_this_quarter_cents), status: "good" }] },
        { kind: "waterfall", title: "From unused spend to realisable savings", unit: "CAD", provenance: "synthetic", missing: [], steps: [
          { label: "Unused spend", value: t.unused_spend_annual_cents / 100 }, { label: "Downgrade", value: t.downgrade_annual_cents / 100 },
          { label: "Renewal reduction", value: t.renewal_reduction_annual_cents / 100 }, { label: "This quarter", value: t.realizable_this_quarter_cents / 100 }] },
      ]} />
      <section className="panel overflow-x-auto">
        <table className="table"><thead><tr><th>Product</th><th>Paid</th><th>Assigned</th><th>Active 30 d</th><th>Unused</th><th>Reassign</th><th>Billing</th><th>Min</th><th>Renewal</th><th>Notice by</th><th>What is realisable</th></tr></thead>
          <tbody>{s.licenses.map((x: any) => <tr key={x.id}><td>{x.product}</td><td>{x.paid}</td><td>{x.assigned}</td><td>{x.active_30d}</td><td>{x.unused}</td><td>{x.reassign}</td><td>{x.billing}</td><td>{x.min_seats}</td><td>{x.renewal}</td><td className={x.notice_open ? "" : "text-brick-700"}>{x.notice_deadline}</td><td>{x.realizable_note}</td></tr>)}</tbody></table>
        <p className="mt-2 text-xs text-ink-muted">{s.terms} {s.note}</p>
      </section>
    </div>
  );
}
