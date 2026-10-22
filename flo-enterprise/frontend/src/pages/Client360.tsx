import { useMutation, useQuery } from "@tanstack/react-query";
import { Eye, Mail, MessageSquareText, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "@/components/ChartCard";
import { Badge, Button, Card, ErrorState, Input, Label, PageHeader, Progress, Select, Spinner, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { LANGS } from "@/lib/i18n";
import { cad, compact, pct } from "@/lib/format";
import { PortfolioDetail } from "./Investment";

type Tab = "overview" | "portfolio" | "planning" | "meeting" | "comms";

export default function Client360() {
  const { id = "" } = useParams();
  const [tab, setTab] = useState<Tab>("overview");
  const q = useQuery({ queryKey: ["c360", id], queryFn: () => api(`/api/wealth/clients/${id}`) });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const c = q.data;
  return (
    <div className="space-y-4">
      <PageHeader title={`${c.profile.full_name} · ${c.profile.id}`} subtitle={`${c.profile.segment} · ${c.profile.risk_profile} · age ${c.profile.age} · ${c.profile.province} · prefers ${c.profile.language}`} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Client 360" }, { id: "portfolio", label: "Portfolio health" }, { id: "planning", label: "Goals & retirement" },
        { id: "meeting", label: "Meeting preparation" }, { id: "comms", label: "Communication drafting" }]} />
      {tab === "overview" && <Overview c={c} />}
      {tab === "portfolio" && <Portfolios c={c} />}
      {tab === "planning" && <Planning id={id} c={c} />}
      {tab === "meeting" && <Meeting id={id} />}
      {tab === "comms" && <Comms id={id} language={c.profile.language} />}
    </div>
  );
}

function Reveal({ id, field, masked }: { id: string; field: string; masked: string }) {
  const r = useMutation({ mutationFn: () => api(`/api/privacy/reveal/${id}/${field}`) });
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span className="text-muted">{field.replace("_", " ")}</span>
      <span className="font-mono">{r.data?.value ?? masked}</span>
      {!r.data && <Button size="sm" variant="ghost" onClick={() => r.mutate()} aria-label={`Reveal ${field} (audited)`}><Eye className="h-3.5 w-3.5" />Reveal</Button>}
      {r.error && <span className="text-xs text-crit">denied</span>}
    </div>
  );
}

function Overview({ c }: { c: any }) {
  const tk = tokens();
  const tl = useMemo(() => ({ ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => `${p.data[2]}<br/>${p.data[0].slice(0, 10)} · ${p.data[3]}` },
    xAxis: axis({ type: "time" }), yAxis: axis({ type: "category", data: ["negative", "neutral", "positive"] }),
    series: [{ type: "scatter", symbolSize: 12, itemStyle: { borderColor: tk.surface, borderWidth: 2 },
      data: c.timeline.map((i: any) => ({ value: [i.ts, i.sentiment, i.topic, i.channel], itemStyle: { color: i.sentiment === "negative" ? tk.series[1] : i.sentiment === "positive" ? tk.series[2] : tk.series[0] } })) }] }), [c, tk]);
  const funds = c.profile.fund_positions.reduce((a: number, p: any) => a + p.market_value, 0);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Stat label="Fund positions" value={cad(funds)} sub={`${c.profile.fund_positions.length} funds`} />
        <Stat label="Managed portfolios" value={c.portfolios.length} sub={c.portfolios.map((p: any) => p.id).join(", ")} />
        <Stat label="Suitability screen" value={c.suitability.status.replace("_", " ")} tone={c.suitability.findings.length ? "warn" : "good"} sub={`rules ${c.suitability.rules_version}`} />
        <Stat label="KYC last review" value={c.profile.kyc_last_review} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="space-y-2 p-4"><h3 className="text-sm font-semibold">Contact (masked)</h3>
          {["email", "phone", "account_number"].map((f) => <Reveal key={f} id={c.profile.id} field={f} masked={c.contact_masked[f]} />)}
          <div className="text-xs text-muted">SIN: {c.contact_masked.sin} (never revealed in UI)</div><p className="text-[11px] text-muted">{c.note}</p></Card>
        <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Suitability findings</h3>
          {c.suitability.findings.length === 0 ? <p className="text-sm text-pos">No exceptions under approved rules.</p> :
            <ul className="space-y-1 text-xs">{c.suitability.findings.map((f: any, i: number) => <li key={i}><Badge tone={f.severity === "high" ? "crit" : "warn"}>{f.rule}</Badge> {JSON.stringify(f.detail)}</li>)}</ul>}
          <p className="mt-2 text-[11px] text-muted">{c.suitability.disclaimer}</p></Card>
        <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Fund positions</h3><ul className="space-y-1 text-xs">
          {c.profile.fund_positions.map((p: any) => <li key={p.product_id} className="flex justify-between gap-2"><span className="truncate">{p.name}</span><span>{cad(p.market_value)} · {p.fee_bps} bps</span></li>)}</ul></Card>
      </div>
      <ChartCard id="timeline" title="Client service timeline" subtitle="Interactions by sentiment" option={tl} height={220} rows={c.interactions.map((i: any) => ({ ts: i.ts, channel: i.channel, type: i.type, topic: i.topic, sentiment: i.sentiment }))} askContext={{ client_id: c.profile.id }} />
    </div>
  );
}

function Portfolios({ c }: { c: any }) {
  const [sel, setSel] = useState<string | null>(c.portfolios[0]?.id ?? null);
  if (!c.portfolios.length) return <p className="text-sm text-muted">This client holds fund positions only (no managed portfolio).</p>;
  return (
    <div className="space-y-3">
      <div className="flex gap-2">{c.portfolios.map((p: any) => <Button key={p.id} size="sm" variant={sel === p.id ? "primary" : "secondary"} onClick={() => setSel(p.id)}>{p.id} · {p.mandate}</Button>)}</div>
      {sel && <PortfolioDetail id={sel} />}
    </div>
  );
}

function Planning({ id, c }: { id: string; c: any }) {
  const [er, setEr] = useState<string>("");
  const [mc, setMc] = useState<string>("");
  const [age, setAge] = useState("65");
  const qs = new URLSearchParams({ retirement_age: age, ...(er ? { expected_return: String(Number(er) / 100) } : {}), ...(mc ? { monthly_contribution: mc } : {}) });
  const r = useQuery({ queryKey: ["ret", id, qs.toString()], queryFn: () => api(`/api/wealth/clients/${id}/retirement?${qs}`) });
  const tk = tokens();
  return (
    <div className="space-y-4">
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Goal progress</h3>
        <div className="grid gap-3 md:grid-cols-2">{c.goals.goals.map((g: any) => (
          <div key={g.goal_id} className="text-xs space-y-1"><div className="flex justify-between"><span className="capitalize">{g.goal_type.replace("_", " ")} · target {cad(g.target_amount)} by {g.target_date}</span>
            <Badge tone={g.on_track ? "good" : "warn"}>{g.on_track ? "on track" : "gap"}</Badge></div>
            <Progress value={g.funded_pct * 100} /><div className="text-muted">funded {pct(g.funded_pct, 0)} · projected {pct(g.projected_funded_pct, 0)} at target date</div></div>))}</div>
        <p className="mt-2 text-[11px] text-muted">Expected return assumption {pct(c.goals.expected_return_assumption, 1)} from approved planning rules (illustrative).</p></Card>
      <Card className="grid gap-3 p-4 md:grid-cols-4">
        <div><Label>Expected return % (blank = approved default)</Label><Input inputMode="decimal" value={er} onChange={(e) => setEr(e.target.value)} placeholder="e.g. 5" /></div>
        <div><Label>Monthly contribution CAD</Label><Input inputMode="decimal" value={mc} onChange={(e) => setMc(e.target.value)} placeholder="plan default" /></div>
        <div><Label>Retirement age</Label><Input type="number" min={40} max={80} value={age} onChange={(e) => setAge(e.target.value)} /></div>
        <div className="text-xs text-muted self-end">Deterministic projection; not a guarantee. What-if inputs are labelled as advisor overrides.</div>
      </Card>
      {r.isLoading ? <Spinner /> : r.error ? <ErrorState error={r.error} /> : (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard id="retirement_projection" title="Retirement projection (nominal vs today's dollars)" askContext={{ client_id: id }}
            subtitle={`At retirement ${cad(r.data.balance_at_retirement)} · sustainable first-year withdrawal ${cad(r.data.sustainable_first_year_withdrawal)} (${r.data.inputs.source})`}
            rows={r.data.path.map((p: any) => ({ year: p.year, phase: p.phase, balance: p.balance, real_balance: p.real_balance, withdrawal: p.withdrawal ?? "" }))}>
            <div style={{ height: 280 }} role="img" aria-label="Retirement projection chart">
              <ResponsiveContainer><AreaChart data={r.data.path.map((p: any) => ({ ...p, balance: Number(p.balance), real: Number(p.real_balance) }))}>
                <CartesianGrid stroke={tk.grid} vertical={false} /><XAxis dataKey="year" stroke={tk.muted} fontSize={11} />
                <YAxis stroke={tk.muted} fontSize={11} tickFormatter={compact} width={50} />
                <Tooltip contentStyle={{ background: tk.surface, border: "none" }} formatter={(v: number) => cad(v)} />
                <Legend /><Area dataKey="balance" name="Nominal" stroke={tk.series[0]} fill={tk.series[0]} fillOpacity={0.25} strokeWidth={2} />
                <Area dataKey="real" name="Today's dollars" stroke={tk.series[2]} fill={tk.series[2]} fillOpacity={0.15} strokeWidth={2} />
              </AreaChart></ResponsiveContainer></div>
          </ChartCard>
          <ChartCard id="cash_flow" title="12-month cash-flow forecast" subtitle={r.data.cash_flow_forecast.basis} rows={r.data.cash_flow_forecast.months}>
            <div style={{ height: 280 }} role="img" aria-label="Cash flow forecast chart">
              <ResponsiveContainer><BarChart data={r.data.cash_flow_forecast.months.map((m: any) => ({ month: `M${m.month}`, contributions: Number(m.planned_goal_contributions) + Number(m.expected_portfolio_contributions), withdrawals: Number(m.expected_withdrawals) }))}>
                <CartesianGrid stroke={tk.grid} vertical={false} /><XAxis dataKey="month" stroke={tk.muted} fontSize={11} /><YAxis stroke={tk.muted} fontSize={11} tickFormatter={compact} width={50} />
                <Tooltip contentStyle={{ background: tk.surface, border: "none" }} formatter={(v: number) => cad(v)} /><Legend />
                <Bar dataKey="contributions" fill={tk.series[2]} radius={[4, 4, 0, 0]} /><Bar dataKey="withdrawals" fill={tk.series[1]} radius={[0, 0, 4, 4]} />
              </BarChart></ResponsiveContainer></div>
          </ChartCard>
        </div>
      )}
    </div>
  );
}

function Meeting({ id }: { id: string }) {
  const m = useMutation({ mutationFn: () => api("/api/ask", { method: "POST", json: { question: `Prepare a portfolio review for client ${id}`, context: { client_id: id } } }) });
  const { ask } = useApp();
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap gap-2"><Button variant="primary" onClick={() => m.mutate()} disabled={m.isPending}><MessageSquareText className="h-4 w-4" />Generate meeting preparation</Button>
        <Button onClick={() => ask({ client_id: id, question: `What should I discuss with client ${id}?` })}>Open in Ask Flo</Button></div>
      {m.isPending && <Spinner label="Client intelligence, wealth, retirement and meeting agents running" />}
      {m.error && <ErrorState error={m.error} />}
      {m.data && <div className="space-y-2"><div className="flex flex-wrap gap-1">{m.data.agents.map((a: string) => <Badge key={a}>{a}</Badge>)}</div>
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{m.data.text}</div>
        {m.data.warnings.map((w: string, i: number) => <p key={i} className="text-xs text-warn">{w}</p>)}</div>}
    </Card>
  );
}

function Comms({ id, language }: { id: string; language: string }) {
  const [lang, setLang] = useState(language);
  const start = useMutation({ mutationFn: () => api("/api/workflows/communication", { method: "POST", json: { client_id: id, language: lang } }) });
  const appr = useQuery({ queryKey: ["apr", start.data?.approval_id], queryFn: () => api(`/api/approvals/${start.data.approval_id}`), enabled: !!start.data?.approval_id, refetchInterval: 5000 });
  const resume = useMutation({ mutationFn: () => api(`/api/workflows/communication/${start.data.thread_id}/resume`, { method: "POST", json: {} }) });
  const d = start.data?.draft;
  return (
    <Card className="space-y-3 p-4">
      <p className="text-xs text-muted">Drafts use compliance-approved templates with figures from deterministic tools. Sending requires a compliance officer to approve the exact payload (SHA-256 bound); edits after approval invalidate it. Delivery is to a mock outbox only.</p>
      <div className="flex flex-wrap items-end gap-2">
        <div><Label>Language</Label><Select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Draft language">{LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}</Select></div>
        <Button variant="primary" onClick={() => start.mutate()} disabled={start.isPending}><Mail className="h-4 w-4" />Draft &amp; submit for approval</Button>
      </div>
      {start.isPending && <Spinner label="Drafting" />}
      {start.error && <ErrorState error={start.error} />}
      {d && (
        <div className="grid gap-4 xl:grid-cols-2">
          <div><div className="mb-1 text-sm font-semibold">{d.subject}</div><pre className="whitespace-pre-wrap rounded-md border border-line bg-bg p-3 text-sm font-sans">{d.body}</pre></div>
          <div className="space-y-2 text-sm">
            <div>Translation validation: <Badge tone={d.translation_validation.valid ? "good" : "crit"}>{d.translation_validation.valid ? "numbers & terms preserved" : "FAILED"}</Badge></div>
            <div>Compliance pre-check: <Badge tone={d.compliance_precheck.passed ? "good" : "crit"}>{d.compliance_precheck.passed ? "passed" : "failed"}</Badge></div>
            <div>Workflow status: <Badge tone="gold">{resume.data?.status ?? start.data.status}</Badge></div>
            {appr.data && <div className="text-xs">Approval {appr.data.id}: <b>{appr.data.status}</b> · hash {appr.data.payload_hash.slice(0, 16)}… · expires {appr.data.expires_at.slice(0, 16)} · approver role {appr.data.approver_role}</div>}
            <Button variant="blue" disabled={appr.data?.status !== "approved" || resume.isPending} onClick={() => resume.mutate()}><Send className="h-4 w-4" />Send approved message (mock outbox)</Button>
            {resume.data && <div className="text-xs">Result: {JSON.stringify(resume.data.result)}</div>}
          </div>
        </div>
      )}
    </Card>
  );
}
