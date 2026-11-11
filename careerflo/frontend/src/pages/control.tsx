import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AgentCursor } from "@/components/art/AgentCursor";
import { PageHeader } from "@/components/career";
import { TransactionsCard } from "@/components/Transactions";
import { Button, Card, Empty, ErrorNote, Input, Label, Pill } from "@/components/ui";
import { api } from "@/lib/api";
import { useUsage } from "@/lib/hooks";
import { money } from "@/lib/utils";

function Stat({ k, v }: { k: string; v: any }) {
  return <Card className="p-4 text-center"><p className="muted text-[11.5px]">{k}</p><p className="font-serif text-3xl">{v ?? "—"}</p></Card>;
}

export function MissionControl() {
  const m = useQuery({ queryKey: ["metrics"], queryFn: () => api<any>("/api/agents/metrics"), refetchInterval: 10000 });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<{ runs: any[] }>("/api/agents/runs") });
  const llm = useQuery({ queryKey: ["llm"], queryFn: () => api<any>("/api/system/llm") });
  const d = m.data;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Agent Mission Control" title="Watch the agents work" />
      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
            <Stat k="Qwen model" v={<span className="text-xl">{llm.data?.model}</span>} /><Stat k="TTFT (ms)" v={d.inference.avg_ttft_ms} /><Stat k="Tokens/s" v={d.inference.avg_tokens_per_second} />
            <Stat k="Tool calls" v={d.tools.calls} /><Stat k="Tool error rate" v={`${Math.round(d.tools.error_rate * 100)}%`} /><Stat k="CPU / RAM" v={<span className="text-xl">{d.system.cpu_percent}% / {d.system.memory_percent}%</span>} />
          </div>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <Card><p className="text-[13px] font-semibold">Qwen latency (recent)</p><div className="h-44"><ResponsiveContainer><AreaChart data={d.inference.recent}><XAxis dataKey="purpose" fontSize={10} /><YAxis fontSize={10} /><Tooltip /><Area dataKey="total_ms" stroke="#7357FF" fill="#7357FF22" /></AreaChart></ResponsiveContainer></div>
              <p className="muted text-[11.5px]">{llm.data?.ok ? "Inference server reachable" : `Inference server unavailable: ${llm.data?.error ?? ""}`} · queue {d.system.llm_queue_depth} · {d.inference.tokens.toLocaleString()} tokens used</p></Card>
            <Card><p className="text-[13px] font-semibold">MCP tools invoked</p><div className="h-44"><ResponsiveContainer><BarChart layout="vertical" data={d.tools.by_tool.map(([t, n]: any) => ({ t, n }))}><XAxis type="number" fontSize={10} /><YAxis type="category" dataKey="t" width={150} fontSize={10} /><Tooltip /><Bar dataKey="n" fill="#38BDF8" radius={4} /></BarChart></ResponsiveContainer></div></Card>
          </div>
        </>
      )}
      <Card className="relative mt-5">
        <AgentCursor label="Supervisor" tone="sky" className="-top-6 right-10" />
        <p className="text-[13px] font-semibold">Workflow runs</p>
        {!runs.data?.runs.length ? <Empty title="No runs yet" body="Ask the assistant something to see the supervisor at work." /> : (
          <ul className="mt-3 divide-y divide-black/5 text-[13px] dark:divide-white/10">
            {runs.data.runs.map((r) => (
              <li key={r.id} className="py-3">
                <div className="flex items-center gap-2"><Pill tone={r.status === "completed" ? "emerald" : r.status === "failed" ? "coral" : "amber"}>{r.status}</Pill><b>{r.intent}</b><span className="muted">{r.agents.join(" → ")}</span><span className="muted ml-auto">{r.duration_ms} ms</span></div>
                <p className="muted mt-1 text-[11.5px]">{r.steps.filter((s: any) => s.tool).map((s: any) => `${s.tool} (${s.ms}ms)`).join(" · ")}{r.error && ` · ${r.error}`}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function McpRegistry() {
  const t = useQuery({ queryKey: ["mcp"], queryFn: () => api<any>("/api/mcp/tools") });
  const calls = useQuery({ queryKey: ["mcp-calls"], queryFn: () => api<any>("/api/mcp/calls") });
  const agents = useQuery({ queryKey: ["agents-cat"], queryFn: () => api<any>("/api/agents/catalog") });
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="MCP Tool Registry" title="Seven servers, one gateway" sub={t.data?.transport} />
      <div className="grid gap-4 md:grid-cols-2">
        {t.data?.servers.map((s: any) => (
          <Card key={s.id}>
            <div className="flex items-center justify-between"><p className="font-semibold">{s.label}</p><Pill>v{s.version}</Pill></div>
            <ul className="mt-3 space-y-1.5 text-[12.5px]">{s.tools.map((x: any) => <li key={x.name}><code className="text-violet">{x.name}</code> <span className="muted">— {x.description}</span></li>)}</ul>
          </Card>
        ))}
      </div>
      <Card className="mt-5"><p className="text-[13px] font-semibold">Agent allowlists</p>
        <ul className="mt-2 space-y-1 text-[12px]">{agents.data?.agents.filter((a: any) => a.tools.length).map((a: any) => <li key={a.id}><b>{a.label}:</b> <span className="muted">{a.tools.join(", ")}</span></li>)}</ul></Card>
      <Card className="mt-5 overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-[12.5px]"><thead><tr className="text-left text-slate-500"><th className="p-3">When</th><th>Agent</th><th>Tool</th><th>Status</th><th>ms</th></tr></thead>
          <tbody>{calls.data?.calls.map((c: any) => <tr key={c.id} className="border-t border-black/5 dark:border-white/10"><td className="p-3">{new Date(c.at).toLocaleTimeString()}</td><td>{c.agent}</td><td>{c.server}.{c.tool}</td><td><Pill tone={c.status === "ok" ? "emerald" : "coral"}>{c.status}</Pill></td><td>{c.duration_ms}</td></tr>)}</tbody></table>
      </Card>
    </div>
  );
}

export function Governance() {
  const qc = useQueryClient();
  const s = useQuery({ queryKey: ["gov"], queryFn: () => api<any>("/api/governance/summary") });
  const a = useQuery({ queryKey: ["approvals"], queryFn: () => api<any>("/api/approvals") });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api<any>("/api/governance/audit") });
  const [err, setErr] = useState<unknown>(null);
  async function decide(id: string, approve: boolean) {
    setErr(null);
    try { await api(`/api/approvals/${id}/decision`, { method: "POST", json: { approve } }); qc.invalidateQueries(); } catch (x) { setErr(x); }
  }
  const pending = a.data?.requests.filter((r: any) => r.status === "pending") ?? [];
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Governance Center" title="Nothing happens without you" sub="Agents can propose consequential actions. Only you can approve them." />
      <div className="grid grid-cols-3 gap-3"><Stat k="Pending approvals" v={s.data?.pending_approvals} /><Stat k="Tool calls" v={s.data?.tool_calls} /><Stat k="Denied by policy" v={s.data?.denied_tool_calls} /></div>
      <ErrorNote error={err} />
      <Card className="mt-5">
        <p className="text-[13px] font-semibold">Waiting for your decision</p>
        {!pending.length ? <p className="muted mt-2 text-sm">Nothing waiting.</p> : pending.map((r: any) => (
          <div key={r.id} className="mt-3 flex flex-wrap items-center gap-3 rounded-2xl bg-slate-50 p-4 dark:bg-white/5">
            <div className="min-w-0 flex-1"><p className="text-[13.5px] font-medium">{r.summary}</p><p className="muted text-[11.5px]">{a.data.actions[r.action]} · requested by {r.requested_by}</p></div>
            <Button size="sm" variant="outline" onClick={() => decide(r.id, false)}>Reject</Button>
            <Button size="sm" variant="violet" onClick={() => decide(r.id, true)}>Approve</Button>
          </div>
        ))}
      </Card>
      <Card className="mt-5"><p className="text-[13px] font-semibold">Controls in force</p><ul className="mt-2 grid gap-1 text-[12.5px] sm:grid-cols-2">{s.data?.controls.map((c: string) => <li key={c}>✓ {c}</li>)}</ul></Card>
      <Card className="mt-5"><p className="text-[13px] font-semibold">Audit log</p>
        <ul className="mt-2 max-h-80 divide-y divide-black/5 overflow-auto text-[12px] dark:divide-white/10">{audit.data?.events.map((e: any, i: number) => <li key={i} className="py-2"><span className="muted">{new Date(e.at).toLocaleString()}</span> · <b>{e.actor}</b> · {e.action}</li>)}</ul></Card>
    </div>
  );
}

export function Billing() {
  const sub = useQuery({ queryKey: ["sub"], queryFn: () => api<any>("/api/billing/subscription") });
  const inv = useQuery({ queryKey: ["invoices"], queryFn: () => api<any>("/api/billing/invoices") });
  const usage = useUsage();
  const [err, setErr] = useState<unknown>(null);
  const qc = useQueryClient();
  async function go(path: string) {
    setErr(null);
    try { const r = await api<any>(path, { method: "POST" }); if (r.url) location.href = r.url; else qc.invalidateQueries(); } catch (x) { setErr(x); }
  }
  const s = sub.data;
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Billing and Subscription" title={s ? `${s.plan.name} plan` : "Billing"} sub={s?.stripe_mode === "test" ? "Stripe test mode — no real charges." : undefined}>
        <a href="/pricing"><Button variant="outline">Compare / change plans</Button></a>
        {s?.subscription && <Button variant="outline" onClick={() => go("/api/billing/portal")}>Manage payment methods</Button>}
        {s?.subscription && (s.subscription.cancel_at_period_end ? <Button onClick={() => go("/api/billing/resume")}>Resume subscription</Button>
          : <Button variant="ghost" onClick={() => confirm("Cancel at the end of the current period?") && go("/api/billing/cancel")}>Cancel subscription</Button>)}
      </PageHeader>
      <ErrorNote error={err} />
      {s?.subscription && <p className="mb-6 text-center text-[13px]">Status <Pill tone={s.subscription.status === "active" ? "emerald" : "amber"}>{s.subscription.status}</Pill> · {s.subscription.cancel_at_period_end ? "ends" : "renews"} {s.subscription.current_period_end ? new Date(s.subscription.current_period_end).toLocaleDateString() : ""}</p>}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[560px] text-[13px]"><thead><tr className="text-left text-slate-500"><th className="p-4">Feature</th><th>Free uses</th><th>This month</th></tr></thead>
          <tbody>{usage.data?.features.map((f) => (
            <tr key={f.id} className="border-t border-black/5 dark:border-white/10">
              <td className="p-4">{f.name}<p className="muted text-[11.5px]">{f.description}</p></td>
              <td>{f.trial_remaining} of {f.trial_limit} remaining</td><td>{f.plan_limit ? `${f.plan_remaining} of ${f.plan_limit}` : "—"}</td>
            </tr>))}</tbody></table>
      </Card>
      <div className="mt-5">
        <TransactionsCard
          txns={(inv.data?.invoices ?? []).map((i: any) => ({ ...i, refunded_cents: i.refunded_cents }))}
          sub={s?.subscription ?? null}
          mode={s?.stripe_mode === "not_configured" ? undefined : s?.stripe_mode}
          title={s ? `${s.plan.name} plan` : "Billing"}
        />
      </div>
      {s && <div className="muted mt-6 space-y-1 text-center text-[11.5px]">{Object.values(s.terms).map((t: any) => <p key={t}>{t}</p>)}</div>}
    </div>
  );
}

export function SettingsPage() {
  const qc = useQueryClient();
  const p = useQuery({ queryKey: ["profile"], queryFn: () => api<any>("/api/profile") });
  const [f, setF] = useState<any>(null);
  const [skill, setSkill] = useState("");
  const [saved, setSaved] = useState(false);
  const form = f ?? p.data?.profile ?? {};
  const set = (k: string, v: any) => setF({ ...form, [k]: v });
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader eyebrow="Account Settings" title="About you" sub="Facts you add here count as verified for matching and tailoring." />
      <Card className="space-y-3">
        {[["full_name", "Full name"], ["headline", "Headline"], ["location", "Location (e.g. Toronto, ON)"], ["github_username", "GitHub username"]].map(([k, l]) => (
          <div key={k}><Label>{l}</Label><Input value={form[k] ?? ""} onChange={(e) => set(k, e.target.value || null)} /></div>
        ))}
        <div className="grid grid-cols-3 gap-2">
          <div><Label>Target salary</Label><Input inputMode="numeric" value={form.target_salary_min ?? ""} onChange={(e) => set("target_salary_min", e.target.value ? Number(e.target.value.replace(/\D/g, "")) : null)} /></div>
          <div><Label>Currency</Label><Input maxLength={3} value={form.target_currency ?? ""} onChange={(e) => set("target_currency", e.target.value.toUpperCase() || null)} /></div>
          <div><Label>Years experience</Label><Input inputMode="decimal" value={form.years_experience ?? ""} onChange={(e) => set("years_experience", e.target.value ? Number(e.target.value) : null)} /></div>
        </div>
        <Button onClick={async () => { const { target_titles, ...rest } = form; await api("/api/profile", { method: "PUT", json: rest }); setSaved(true); qc.invalidateQueries({ queryKey: ["profile"] }); }}>Save</Button>
        {saved && <span className="ml-3 text-sm text-emerald-700">Saved</span>}
      </Card>
      <Card className="mt-5">
        <p className="text-[13px] font-semibold">Verified skills</p>
        <div className="mt-3 flex flex-wrap gap-1.5">{p.data?.skills.map((s: any) => <Pill key={s.id} tone={s.source === "user" ? "violet" : "neutral"}>{s.name}</Pill>)}</div>
        <div className="mt-3 flex gap-2"><Input placeholder="Add a skill you have used" value={skill} onChange={(e) => setSkill(e.target.value)} />
          <Button variant="outline" disabled={!skill} onClick={async () => { await api("/api/profile/skills", { method: "POST", json: { name: skill } }); setSkill(""); qc.invalidateQueries({ queryKey: ["profile"] }); }}>Add</Button></div>
      </Card>
    </div>
  );
}

export function Admin() {
  const m = useQuery({ queryKey: ["admin"], queryFn: () => api<any>("/api/admin/metrics") });
  const d = m.data;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Administrator" title="Subscription analytics" sub={d?.note} />
      <ErrorNote error={m.error} />
      {d && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat k="Registered users" v={d.registered_users} /><Stat k="Trial users" v={d.trial_users} />
            <Stat k="Pro / Premium" v={`${d.active_pro} / ${d.active_premium}`} /><Stat k="MRR" v={money(d.mrr_cents / 100, d.currency)} />
            <Stat k="Trial → paid" v={d.trial_to_paid_conversion == null ? "—" : `${Math.round(d.trial_to_paid_conversion * 100)}%`} />
            <Stat k="Cancellations" v={d.cancellations} /><Stat k="Failed payments" v={d.failed_payments} />
            <Stat k="Est. gross margin" v={d.estimated_gross_margin == null ? "—" : `${Math.round(d.estimated_gross_margin * 100)}%`} />
          </div>
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <Card><p className="text-[13px] font-semibold">Net revenue by month</p><div className="h-48"><ResponsiveContainer><AreaChart data={d.revenue_trend.map((r: any) => ({ ...r, cad: r.net_cents / 100 }))}><XAxis dataKey="month" fontSize={10} /><YAxis fontSize={10} /><Tooltip /><Area dataKey="cad" stroke="#10B981" fill="#10B98122" /></AreaChart></ResponsiveContainer></div></Card>
            <Card><p className="text-[13px] font-semibold">Trial usage by feature</p><div className="h-48"><ResponsiveContainer><BarChart data={Object.entries(d.trial_usage_by_feature).map(([f, n]) => ({ f, n }))}><XAxis dataKey="f" fontSize={9} /><Tooltip /><Bar dataKey="n" fill="#7357FF" radius={4} /></BarChart></ResponsiveContainer></div></Card>
          </div>
        </>
      )}
    </div>
  );
}
