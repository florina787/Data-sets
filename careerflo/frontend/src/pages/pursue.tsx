import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Funnel, FunnelChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AgentCursor } from "@/components/art/AgentCursor";
import { Avatar } from "@/components/art/Avatar";
import { PortfolioArt } from "@/components/art/Paths";
import { ActivityHeatmap, PageHeader, TrialMeter } from "@/components/career";
import { Button, Card, Chip, Empty, ErrorNote, Input, Label, Pill, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useMetered } from "@/lib/hooks";
import { money } from "@/lib/utils";

export function CompanyResearch() {
  const [name, setName] = useState("");
  const [compare, setCompare] = useState("");
  const r = useMetered("/api/company/research");
  const c = useMetered("/api/company/compare");
  const d = r.data;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Company Research" title="Know them before they know you" sub="Only verifiable sources, always cited." />
      <Card>
        <div className="flex gap-2"><Input placeholder="Company name" value={name} onChange={(e) => setName(e.target.value)} /><Button disabled={name.length < 2} loading={r.isPending} onClick={() => r.mutate({ company: name })}>Research</Button></div>
        <div className="mt-3 flex gap-2"><Input placeholder="Compare: Acme, Globex, Initech" value={compare} onChange={(e) => setCompare(e.target.value)} />
          <Button variant="outline" disabled={compare.split(",").filter((x) => x.trim()).length < 2} loading={c.isPending} onClick={() => c.mutate({ companies: compare.split(",").map((x) => x.trim()).filter(Boolean) })}>Compare</Button></div>
        <div className="mt-3"><TrialMeter feature="company_research" /></div>
      </Card>
      <ErrorNote error={r.error || c.error} />
      {d && (
        <Card className="mt-5 space-y-3">
          <h2 className="font-serif text-3xl">{d.company}</h2>
          {d.overview?.extract ? <p className="text-[14px]">{d.overview.extract}</p> : <p className="muted text-sm">No encyclopedic overview found.</p>}
          <p className="text-[13px]">Open roles indexed: <b>{d.hiring.open_roles}</b> · {Object.entries(d.hiring.work_arrangements).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
          <div className="flex flex-wrap gap-1.5">{d.hiring.top_skills.map(([s, n]: [string, number]) => <Pill key={s}>{s} · {n}</Pill>)}</div>
          {d.culture_signals.length > 0 && <p className="text-[13px]">Signals: {d.culture_signals.join(" · ")}</p>}
          <ul className="text-[12.5px]">{d.citations.map((x: any) => <li key={x.url}><a className="text-violet underline" href={x.url} target="_blank" rel="noreferrer">{x.label}</a></li>)}</ul>
          <p className="muted text-[11.5px]">{d.note}</p>
        </Card>
      )}
      {c.data && (
        <Card className="mt-5 overflow-x-auto p-0"><table className="w-full text-[13px]"><thead><tr className="text-left text-slate-500"><th className="p-3">Company</th><th>Roles</th><th>Remote share</th><th>Top skills</th></tr></thead>
          <tbody>{c.data.comparison.map((x: any) => <tr key={x.company} className="border-t border-black/5"><td className="p-3">{x.company}</td><td>{x.open_roles}</td><td>{Math.round(x.remote_share * 100)}%</td><td>{x.top_skills.join(", ")}</td></tr>)}</tbody></table></Card>
      )}
    </div>
  );
}

export function Recruiters() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["recruiters"], queryFn: () => api<{ recruiters: any[] }>("/api/recruiters") });
  const [form, setForm] = useState({ name: "", company: "", email: "" });
  const [sel, setSel] = useState<any>(null);
  const report = useMetered((b: any) => `/api/recruiters/${b.id}/report`);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Recruiter CRM" title="Relationships, not cold emails" sub="Track every conversation. Emails go out only after you approve them." />
      <div className="grid gap-5 md:grid-cols-5">
        <Card className="md:col-span-2">
          <p className="mb-3 text-[13px] font-semibold">Add recruiter</p>
          <div className="space-y-2">
            <Input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <Input placeholder="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            <Input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <Button disabled={!form.name} onClick={async () => { await api("/api/recruiters", { method: "POST", json: { ...form, email: form.email || null } }); setForm({ name: "", company: "", email: "" }); qc.invalidateQueries({ queryKey: ["recruiters"] }); }}>Add</Button>
          </div>
          <ul className="mt-5 space-y-1">{list.data?.recruiters.map((r) => (
            <li key={r.id}><button onClick={() => setSel(r)} className="flex w-full items-center gap-3 rounded-xl p-2 text-left hover:bg-black/[.03]">
              <Avatar name={r.name} size={32} /><span className="text-[13px]">{r.name}<br /><span className="muted text-[11.5px]">{r.company}</span></span>
              {r.is_synthetic && <Pill tone="amber" className="ml-auto">demo</Pill>}</button></li>))}</ul>
        </Card>
        <Card className="relative md:col-span-3">
          {!sel ? <Empty title="Select a recruiter" /> : (
            <div className="space-y-4">
              <div className="flex items-center gap-3"><Avatar name={sel.name} size={48} /><div><p className="font-semibold">{sel.name}</p><p className="muted text-[12.5px]">{sel.company} · {sel.email}</p></div></div>
              <div className="flex gap-2"><Input placeholder="Log an interaction…" value={note} onChange={(e) => setNote(e.target.value)} />
                <Button variant="outline" disabled={!note} onClick={async () => { await api(`/api/recruiters/${sel.id}/interactions`, { method: "POST", json: { channel: "email", direction: "outbound", summary: note } }); setNote(""); }}>Log</Button></div>
              <div className="flex flex-wrap items-center gap-3"><Button loading={report.isPending} onClick={() => report.mutate({ id: sel.id })}>Recruiter intelligence</Button><TrialMeter feature="recruiter_intelligence" /></div>
              <ErrorNote error={report.error} />
              {report.data && <div className="rounded-2xl bg-slate-50 p-4 text-[13px] dark:bg-white/5"><p><b>Next:</b> {report.data.next_action}</p><p className="muted mt-1">{report.data.interactions} interactions · last contact {report.data.days_since_last_contact ?? "never"} days ago</p>{report.data.referral_tip && <p className="mt-1">{report.data.referral_tip}</p>}</div>}
              <Textarea rows={4} placeholder="Draft an email…" value={msg} onChange={(e) => setMsg(e.target.value)} />
              <Button variant="violet" disabled={!msg} onClick={async () => { await api(`/api/recruiters/${sel.id}/email`, { method: "POST", json: { subject: "Following up", body: msg } }); setMsg(""); alert("Sent for your approval in the Governance Center."); }}>Request approval to send</Button>
            </div>
          )}
          <AgentCursor label="Recruiter CRM" tone="emerald" className="-top-6 right-6" />
        </Card>
      </div>
    </div>
  );
}

const COLUMNS = ["draft", "applied", "screening", "interviewing", "offer", "rejected"];

export function Applications() {
  const qc = useQueryClient();
  const apps = useQuery({ queryKey: ["applications"], queryFn: () => api<{ applications: any[] }>("/api/applications") });
  const [f, setF] = useState({ company: "", title: "" });
  const [auto, setAuto] = useState("");
  const automate = useMetered("/api/applications/automate");
  async function move(a: any, status: string) {
    const r = await api<any>(`/api/applications/${a.id}`, { method: "PATCH", json: { status } });
    if (r.approval_required) alert("Submitting needs your approval — see Governance Center.");
    qc.invalidateQueries({ queryKey: ["applications"] });
  }
  const list = apps.data?.applications ?? [];
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader eyebrow="Application Tracker" title="Every application, one board" />
      <div className="mb-8 flex justify-center"><Card className="p-5"><ActivityHeatmap dates={list.filter((a) => a.applied_at).map((a) => a.applied_at)} /></Card></div>
      <div className="mx-auto mb-6 flex max-w-2xl flex-wrap justify-center gap-2">
        <Input className="w-44" placeholder="Company" value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} />
        <Input className="w-56" placeholder="Title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
        <Button disabled={!f.company || !f.title} onClick={async () => { await api("/api/applications", { method: "POST", json: f }); setF({ company: "", title: "" }); qc.invalidateQueries({ queryKey: ["applications"] }); }}>Add</Button>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-4">
        {COLUMNS.map((col) => (
          <div key={col} className="w-60 shrink-0">
            <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[.12em] text-slate-500">{col} · {list.filter((a) => a.status === col).length}</p>
            <div className="space-y-2">
              {list.filter((a) => a.status === col).map((a) => (
                <div key={a.id} className="card p-3">
                  <p className="text-[13px] font-medium">{a.title}</p><p className="muted text-[12px]">{a.company}</p>
                  <select className="mt-2 w-full rounded-lg bg-slate-50 p-1 text-[12px] dark:bg-white/5" value={a.status} onChange={(e) => move(a, e.target.value)} aria-label="Status">
                    {["draft", "applied", "screening", "interviewing", "offer", "accepted", "rejected", "withdrawn"].map((s) => <option key={s}>{s}</option>)}
                  </select>
                  {a.is_synthetic && <Pill tone="amber" className="mt-1">demo</Pill>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <Card className="mx-auto mt-6 max-w-2xl">
        <p className="text-[13px] font-semibold">Application automation</p>
        <p className="muted text-[12.5px]">Search → score → tailor → draft. You approve before anything is marked submitted.</p>
        <div className="mt-3 flex gap-2"><Input placeholder="e.g. Senior AI Engineer jobs in Toronto over CAD 150,000" value={auto} onChange={(e) => setAuto(e.target.value)} />
          <Button loading={automate.isPending} disabled={auto.length < 5} onClick={() => automate.mutate({ request: auto }, { onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }) })}>Prepare</Button></div>
        <div className="mt-2"><TrialMeter feature="application_automation" /></div>
        <ErrorNote error={automate.error} />
        {automate.data && <p className="mt-3 text-[13px]">Prepared. {automate.data.approvals.length} approval(s) waiting in the <a className="text-violet" href="/app/governance">Governance Center</a>.</p>}
      </Card>
    </div>
  );
}

export function Portfolio() {
  const [user, setUser] = useState("");
  const [job, setJob] = useState("");
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<{ jobs: any[] }>("/api/jobs/saved") });
  const p = useMetered("/api/portfolio/analyze");
  const s = p.data?.summary;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="GitHub Portfolio Intelligence" title="Let your work speak" sub="Public repositories only. We map projects to the skills a job asks for." />
      <Card>
        <div className="flex flex-wrap gap-2">
          <Input className="flex-1" placeholder="GitHub username" value={user} onChange={(e) => setUser(e.target.value.trim())} />
          <select className="h-10 rounded-full bg-white px-3 text-sm ring-1 ring-black/10 dark:bg-white/5" value={job} onChange={(e) => setJob(e.target.value)}>
            <option value="">No target job</option>{saved.data?.jobs.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}</select>
          <Button disabled={!user} loading={p.isPending} onClick={() => p.mutate({ username: user, job_id: job || undefined })}>Analyze</Button>
        </div>
        <div className="mt-3"><TrialMeter feature="portfolio_analysis" /></div>
      </Card>
      <ErrorNote error={p.error} />
      {!s ? <Empty art={<PortfolioArt className="h-32" />} title="Your proof lives here" /> : (
        <div className="mt-5 grid gap-5">
          <Card>
            <p className="text-[13px] font-semibold">{s.repo_count} repositories · {s.total_stars} stars</p>
            <div className="mt-3 h-40"><ResponsiveContainer><BarChart data={s.languages.map((l: any) => ({ ...l, share: Math.round(l.share * 100) }))}><XAxis dataKey="language" fontSize={11} /><Tooltip /><Bar dataKey="share" fill="#7357FF" radius={6} /></BarChart></ResponsiveContainer></div>
          </Card>
          {p.data.matches?.projects?.length > 0 && <Card><p className="text-[13px] font-semibold">Talking points for {p.data.matches.job.title}</p>
            <ul className="mt-2 space-y-1.5 text-[13px]">{p.data.matches.projects.map((x: any) => <li key={x.name}><a className="text-violet" href={x.url} target="_blank" rel="noreferrer">{x.name}</a> — {x.matched_skills.join(", ")}</li>)}</ul></Card>}
        </div>
      )}
    </div>
  );
}

export function Salary() {
  const [f, setF] = useState({ title_keyword: "Engineer", currency: "CAD", city: "", offer: "" });
  const r = useMetered("/api/salary/report");
  const d = r.data?.distribution;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Salary Intelligence" title="Know your number" sub="Built only from salaries employers actually published." />
      <Card>
        <div className="grid gap-2 sm:grid-cols-4">
          <div><Label>Title keyword</Label><Input value={f.title_keyword} onChange={(e) => setF({ ...f, title_keyword: e.target.value })} /></div>
          <div><Label>City</Label><Input value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></div>
          <div><Label>Currency</Label><Input value={f.currency} maxLength={3} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} /></div>
          <div><Label>Your offer (optional)</Label><Input inputMode="numeric" value={f.offer} onChange={(e) => setF({ ...f, offer: e.target.value.replace(/\D/g, "") })} /></div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><Button loading={r.isPending} onClick={() => r.mutate({ ...f, city: f.city || null, offer: f.offer ? Number(f.offer) : null })}>Benchmark</Button><TrialMeter feature="salary_intelligence" /></div>
      </Card>
      <ErrorNote error={r.error} />
      {d && (d.count ? (
        <Card className="mt-5">
          <div className="grid grid-cols-4 gap-2 text-center">{["p25", "p50", "p75", "p90"].map((k) => <div key={k}><p className="muted text-[11px] uppercase">{k}</p><p className="font-serif text-2xl">{money(d[k], d.currency)}</p></div>)}</div>
          <div className="mt-4 h-44"><ResponsiveContainer><BarChart data={d.histogram}><XAxis dataKey="range" fontSize={10} /><Tooltip /><Bar dataKey="count" fill="#38BDF8" radius={6} /></BarChart></ResponsiveContainer></div>
          <p className="muted text-[11.5px]">n = {d.count} published salaries{d.synthetic_share > 0 && ` · ${Math.round(d.synthetic_share * 100)}% synthetic demo data`}</p>
          {r.data.negotiation?.scenarios && (
            <div className="mt-5 grid gap-2 sm:grid-cols-3">{r.data.negotiation.scenarios.map((s: any) => <div key={s.name} className="rounded-2xl bg-slate-50 p-4 dark:bg-white/5"><p className="text-[12px] font-semibold">{s.name}</p><p className="font-serif text-2xl">{money(s.ask, d.currency)}</p><p className="muted text-[11.5px]">{s.rationale}</p></div>)}</div>
          )}
          {r.data.negotiation?.disclaimer && <p className="muted mt-3 text-[11.5px]">{r.data.negotiation.disclaimer}</p>}
        </Card>
      ) : <Empty title="No published salaries match" body={d.message} />)}
    </div>
  );
}

export function Analytics() {
  const summary = useQuery({ queryKey: ["analytics-summary"], queryFn: () => api<any>("/api/analytics/summary") });
  const rep = useMetered(() => "/api/analytics/report");
  const d = rep.data;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Career Analytics" title="Your search, measured">
        <Button loading={rep.isPending} onClick={() => rep.mutate({})}>Generate full report</Button>
      </PageHeader>
      <div className="mb-6 flex justify-center"><TrialMeter feature="career_analytics" /></div>
      {summary.data && (
        <div className="mx-auto grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
          {[["Applications", summary.data.applications.submitted], ["Saved jobs", summary.data.saved_jobs], ["Interviews", summary.data.interviews],
            ["Response rate", `${Math.round(summary.data.applications.response_rate * 100)}%`]].map(([k, v]) => (
            <Card key={k as string} className="p-4 text-center"><p className="muted text-[11.5px]">{k}</p><p className="font-serif text-3xl">{v}</p></Card>))}
        </div>
      )}
      <ErrorNote error={rep.error} />
      {d && (
        <div className="mt-8 grid gap-5 md:grid-cols-2">
          <Card><p className="text-[13px] font-semibold">Funnel</p><div className="h-56"><ResponsiveContainer><FunnelChart><Tooltip /><Funnel dataKey="count" data={d.applications.funnel.map((x: any, i: number) => ({ ...x, fill: ["#7357FF", "#8b75ff", "#38BDF8", "#10B981", "#0e9f6e"][i] }))} isAnimationActive><LabelList position="right" dataKey="stage" fontSize={11} /></Funnel></FunnelChart></ResponsiveContainer></div></Card>
          <Card><p className="text-[13px] font-semibold">Applications per month</p><div className="h-56"><ResponsiveContainer><AreaChart data={d.application_timeline}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip /><Area dataKey="count" stroke="#7357FF" fill="#7357FF33" /></AreaChart></ResponsiveContainer></div></Card>
          <Card><p className="text-[13px] font-semibold">Match score distribution</p><div className="h-48"><ResponsiveContainer><BarChart data={d.match_distribution}><XAxis dataKey="bucket" fontSize={10} /><Tooltip /><Bar dataKey="count" fill="#38BDF8" radius={6} /></BarChart></ResponsiveContainer></div></Card>
          <Card><p className="text-[13px] font-semibold">Mock interview progress</p><div className="h-48"><ResponsiveContainer><AreaChart data={d.interviews.mock_trend}><XAxis dataKey="date" fontSize={10} /><YAxis domain={[0, 10]} fontSize={10} /><Tooltip /><Area dataKey="score" stroke="#10B981" fill="#10B98133" /></AreaChart></ResponsiveContainer></div></Card>
          <Card className="md:col-span-2"><p className="text-[13px] font-semibold">Skill gaps in demand</p><div className="mt-3 flex flex-wrap gap-2">{d.skill_gaps.map((g: any) => <Chip key={g.skill}>{g.skill} · {g.demand}</Chip>)}</div>
            <p className="muted mt-3 text-[12px]">Recruiter activity: {d.recruiter_activity.interactions} interactions with {d.recruiter_activity.recruiters} recruiters · Offers: {d.offers}{d.contains_synthetic && " · includes synthetic demo records"}</p></Card>
        </div>
      )}
    </div>
  );
}
