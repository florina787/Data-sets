import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Code2, Cpu, Database, LineChart, Server, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { useState } from "react";
import { RankingList } from "@/components/Cards";
import { JobCard, PageHeader, TrialMeter, type Job } from "@/components/career";
import { AgentCursor } from "@/components/art/AgentCursor";
import { BookStairs } from "@/components/art/Paths";
import { Button, Card, Chip, Empty, ErrorNote, Input, Label, Pill } from "@/components/ui";
import { api } from "@/lib/api";
import { useMetered } from "@/lib/hooks";

const CATEGORIES = [["AI Engineer", Sparkles], ["Machine Learning", Cpu], ["Data Scientist", BarChart3], ["Backend", Server],
  ["Full-Stack", Code2], ["Data Engineer", Database], ["MLOps", Zap], ["Generative AI", LineChart], ["AI Governance", ShieldCheck]] as const;

function useSaved() {
  return useQuery({ queryKey: ["saved"], queryFn: () => api<{ jobs: Job[] }>("/api/jobs/saved") });
}

export function JobDiscovery({ origin }: { origin?: "indeed" | "linkedin" }) {
  const qc = useQueryClient();
  const [cat, setCat] = useState("AI Engineer");
  const [f, setF] = useState({ city: "Toronto", salary_min: "", currency: "CAD", work_arrangement: "", posted_within_days: "", seniority: "" });
  const [selected, setSelected] = useState<string | null>(null);
  const search = useMetered("/api/jobs/search");
  const saved = useSaved();
  const savedIds = new Set(saved.data?.jobs.map((j) => j.id));
  const feature = origin ? "job_board_search" : "job_discovery";
  function run(query = cat) {
    const body: any = { query, limit: 24, country: "ca" };
    if (f.city) body.city = f.city;
    if (f.salary_min) { body.salary_min = Number(f.salary_min); body.currency = f.currency; }
    if (f.work_arrangement) body.work_arrangement = f.work_arrangement;
    if (f.posted_within_days) body.posted_within_days = Number(f.posted_within_days);
    if (f.seniority) body.seniority = f.seniority;
    if (origin) body.origin = origin;
    search.mutate(body);
  }
  const jobs: Job[] = search.data?.jobs ?? [];
  const label = origin === "indeed" ? "Indeed Job Intelligence" : origin === "linkedin" ? "LinkedIn Job Intelligence" : "Your new career awaits";
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow={label} title={<>Search and apply for<br />jobs here</>}
        sub={origin ? `${origin === "indeed" ? "Indeed" : "LinkedIn"}-origin postings through the licensed JSearch aggregator — never scraped.` : undefined}>
        {CATEGORIES.map(([c, Icon]) => <Chip key={c} active={cat === c} icon={<Icon className="h-3.5 w-3.5" />} onClick={() => { setCat(c); run(c); }}>{c}</Chip>)}
      </PageHeader>
      <div className="mx-auto mb-8 flex max-w-3xl flex-wrap items-end justify-center gap-2">
        <div className="w-36"><Label>City</Label><Input value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></div>
        <div className="w-32"><Label>Min salary</Label><Input inputMode="numeric" placeholder="150000" value={f.salary_min} onChange={(e) => setF({ ...f, salary_min: e.target.value.replace(/\D/g, "") })} /></div>
        <div className="w-24"><Label>Currency</Label>
          <select className="h-10 w-full rounded-full bg-white px-3 text-sm ring-1 ring-black/10 dark:bg-white/5" value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })}>
            {["CAD", "USD", "GBP", "EUR"].map((c) => <option key={c}>{c}</option>)}</select></div>
        <div className="w-32"><Label>Arrangement</Label>
          <select className="h-10 w-full rounded-full bg-white px-3 text-sm ring-1 ring-black/10 dark:bg-white/5" value={f.work_arrangement} onChange={(e) => setF({ ...f, work_arrangement: e.target.value })}>
            <option value="">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select></div>
        <div className="w-28"><Label>Posted</Label>
          <select className="h-10 w-full rounded-full bg-white px-3 text-sm ring-1 ring-black/10 dark:bg-white/5" value={f.posted_within_days} onChange={(e) => setF({ ...f, posted_within_days: e.target.value })}>
            <option value="">Any time</option><option value="1">24h</option><option value="7">7 days</option><option value="30">30 days</option></select></div>
        <Button onClick={() => run()} loading={search.isPending}>Search</Button>
      </div>
      <div className="mb-6 flex justify-center"><TrialMeter feature={feature} /></div>
      <ErrorNote error={search.error} />
      {search.data && (
        <p className="muted mb-4 text-center text-[12px]">
          {search.data.total} results · de-duplicated from {search.data.deduplicated_from}
          {search.data.filter_stats?.excluded_no_salary ? ` · ${search.data.filter_stats.excluded_no_salary} hidden (no published salary)` : ""}
          {search.data.synthetic_included && <Pill tone="amber" className="ml-2">includes synthetic demo data</Pill>}
        </p>
      )}
      {jobs.length ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {jobs.map((j) => <JobCard key={j.id} job={j} selected={selected === j.id} onSelect={() => setSelected(j.id)} saved={savedIds.has(j.id)}
            onSave={async () => { if (savedIds.has(j.id)) await api(`/api/jobs/${j.id}/save`, { method: "DELETE" }); else await api(`/api/jobs/${j.id}/save`, { method: "POST" }); qc.invalidateQueries({ queryKey: ["saved"] }); }} />)}
        </div>
      ) : search.data ? <Empty title="No jobs matched every filter" body="Try widening salary or location. We never fill gaps with invented postings." />
        : <Empty art={<div className="relative"><BookStairs className="h-20 opacity-80" /><AgentCursor label="Job Discovery" tone="sky" className="-right-16 -top-4" /></div>}
            title="Pick a category to start" body="Results come from configured providers, with every source shown on the card." />}
      {saved.data && saved.data.jobs.length > 0 && <p className="muted mt-8 text-center text-[12px]">{saved.data.jobs.length} saved jobs — see them in Job Matching.</p>}
    </div>
  );
}

export function Radar() {
  const radar = useMetered(() => "/api/jobs/radar");
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Hidden Job Radar" title="Be an early applicant" sub="Fresh postings from employer boards and anything first published in the last 72 hours.">
        <Button onClick={() => radar.mutate({})} loading={radar.isPending}>Scan now</Button>
      </PageHeader>
      <div className="mb-6 flex justify-center"><TrialMeter feature="job_discovery" /></div>
      <ErrorNote error={radar.error} />
      {radar.data && (radar.data.jobs.length ? (
        <div className="grid gap-4 sm:grid-cols-2">{radar.data.jobs.map((j: any) => <JobCard key={j.id} job={j}
          footer={<>{j.early_applicant && <Pill tone="emerald">Early applicant · {j.hours_since_posted}h</Pill>}{j.direct_from_employer && <Pill tone="violet">Employer board</Pill>}</>} />)}</div>
      ) : <Empty title="Nothing new in the last 72 hours" body={radar.data.explanation} />)}
    </div>
  );
}

export function Matching() {
  const saved = useSaved();
  const [pick, setPick] = useState<string[]>([]);
  const match = useMetered("/api/match");
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Job Matching" title="Which roles fit you best?" sub="Explainable scores from your verified resume — nothing is guessed." />
      <div className="mb-6 flex justify-center"><TrialMeter feature="job_matching" /></div>
      {!saved.data?.jobs.length ? <Empty title="Save a few jobs first" body="Bookmark jobs in Job Discovery, then compare them here." /> : (
        <Card>
          <p className="mb-3 text-[13px] font-semibold">Choose up to 20 saved jobs</p>
          <div className="flex flex-wrap gap-2">
            {saved.data.jobs.map((j) => <Chip key={j.id} active={pick.includes(j.id)} onClick={() => setPick((p) => p.includes(j.id) ? p.filter((x) => x !== j.id) : [...p, j.id].slice(0, 20))}>{j.title} · {j.company}</Chip>)}
          </div>
          <Button className="mt-5" disabled={!pick.length} loading={match.isPending} onClick={() => match.mutate({ job_ids: pick })}>Rank {pick.length || ""} jobs</Button>
        </Card>
      )}
      <ErrorNote error={match.error} />
      {match.data && <div className="mt-6"><RankingList ranked={match.data.ranked.map((m: any) => ({ job: { ...m.job, id: m.job.id }, match: m }))} methodology={match.data.methodology} /></div>}
    </div>
  );
}
