import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Download } from "lucide-react";
import { Link } from "react-router-dom";
import { download } from "@/lib/api";
import { money } from "@/lib/utils";
import { JobCard, type Job } from "./career";
import { Button, Pill } from "./ui";

export function ScoreRing({ score, size = 44 }: { score: number; size?: number }) {
  const r = size / 2 - 4, c = 2 * Math.PI * r;
  const color = score >= 80 ? "#10B981" : score >= 60 ? "#7357FF" : score >= 45 ? "#F59E0B" : "#F97066";
  return (
    <svg width={size} height={size} role="img" aria-label={`Score ${score}`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="currentColor" className="text-slate-200 dark:text-white/10" strokeWidth="4" fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="4" fill="none" strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
        strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="54%" textAnchor="middle" fontSize={size * 0.3} fontWeight={600} fill="currentColor" dominantBaseline="middle">{Math.round(score)}</text>
    </svg>
  );
}

export function RankingList({ ranked, methodology }: { ranked: any[]; methodology?: string }) {
  return (
    <div className="space-y-2">
      {ranked.map((r: any) => {
        const job = r.job; const m = r.match ?? r;
        return (
          <div key={job.id} className="flex items-center gap-4 rounded-2xl bg-white p-3 ring-1 ring-black/5 dark:bg-white/5 dark:ring-white/10">
            <ScoreRing score={m.score} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px] font-medium">{job.title} · <span className="muted">{job.company}</span></p>
              <p className="muted truncate text-[12px]">Missing: {m.missing_required?.length ? m.missing_required.join(", ") : "nothing required"}</p>
            </div>
            <Pill tone={m.grade === "excellent" ? "emerald" : m.grade === "strong" ? "violet" : "amber"}>{m.grade}</Pill>
          </div>
        );
      })}
      {methodology && <details className="muted text-[12px]"><summary className="cursor-pointer">How is this scored?</summary><p className="mt-1">{methodology}</p></details>}
    </div>
  );
}

export function AgentCard({ card }: { card: any }) {
  const body = (() => {
    switch (card.type) {
      case "jobs":
        return (
          <>
            <div className="grid gap-3 sm:grid-cols-2">{card.jobs.slice(0, 6).map((j: Job) => <JobCard key={j.id} job={j} />)}</div>
            <p className="muted mt-2 text-[11.5px]">Sources: {Object.entries(card.providers ?? {}).map(([k, v]) => `${k} (${v})`).join(" · ")}</p>
          </>
        );
      case "ranking": return <RankingList ranked={card.ranked} methodology={card.methodology} />;
      case "resume":
        return (
          <div className="space-y-3">
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-50 p-4 text-[12px] dark:bg-white/5">{card.text}</pre>
            {card.gaps?.length > 0 && <p className="text-[12.5px]"><b>Gaps (not added):</b> {card.gaps.join(", ")}</p>}
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => download(card.downloads.pdf, "resume.pdf")}><Download className="h-3.5 w-3.5" />PDF</Button>
              <Button size="sm" variant="outline" onClick={() => download(card.downloads.docx, "resume.docx")}><Download className="h-3.5 w-3.5" />DOCX</Button>
            </div>
          </div>
        );
      case "interview":
        return (
          <ol className="list-decimal space-y-1.5 pl-5 text-[13px]">
            {card.questions.map((q: any, i: number) => <li key={i}>{q.question} <Pill className="ml-1">{q.topic}</Pill></li>)}
            <p className="muted list-none pt-2 text-[12px]">{card.cta} <Link to="/app/interview" className="text-violet">Open →</Link></p>
          </ol>
        );
      case "salary": {
        const d = card.distribution;
        return d?.count ? (
          <div>
            <p className="text-[13px]">Median {money(d.p50, d.currency)} · P75 {money(d.p75, d.currency)} · n={d.count}</p>
            <div className="h-32"><ResponsiveContainer><BarChart data={d.histogram}><XAxis dataKey="range" fontSize={10} /><Tooltip /><Bar dataKey="count" fill="#7357FF" radius={6} /></BarChart></ResponsiveContainer></div>
          </div>
        ) : <p className="muted text-sm">{d?.message}</p>;
      }
      case "workflow":
        return (
          <div className="space-y-2 text-[13px]">
            <ol className="list-decimal pl-5">{card.steps.map((s: string) => <li key={s}>{s}</li>)}</ol>
            <p>Top match: <b>{card.job.title}</b> at {card.job.company} (score {card.score})</p>
            <Link to="/app/governance"><Button size="sm" variant="violet">Review approval</Button></Link>
          </div>
        );
      case "company":
        return (
          <div className="space-y-2 text-[13px]">
            {card.overview?.extract && <p>{card.overview.extract}</p>}
            <p>Open roles in our index: {card.hiring.open_roles}</p>
            <ul className="text-[12px]">{card.citations.map((c: any) => <li key={c.url}><a className="text-violet underline" href={c.url} target="_blank" rel="noreferrer">{c.label}</a></li>)}</ul>
          </div>
        );
      case "resume_analysis":
        return (
          <div className="grid gap-3 text-[13px] sm:grid-cols-2">
            <div><p className="font-medium text-emerald-700">Strengths</p><ul className="mt-1 list-disc pl-4">{card.strengths.map((s: string) => <li key={s}>{s}</li>)}</ul></div>
            <div><p className="font-medium text-amber-700">To improve</p><ul className="mt-1 list-disc pl-4">{card.issues.length ? card.issues.map((s: string) => <li key={s}>{s}</li>) : <li>Nothing flagged</li>}</ul></div>
            <p className="muted sm:col-span-2">{card.years_experience ? `${card.years_experience} verified years · ` : ""}{card.skills?.length ?? 0} skills on file</p>
          </div>
        );
      case "letter": return <pre className="whitespace-pre-wrap text-[12.5px]">{card.letter}</pre>;
      default:
        return <pre className="max-h-56 overflow-auto rounded-2xl bg-slate-50 p-3 text-[11.5px] dark:bg-white/5">{JSON.stringify(card, null, 2).slice(0, 3000)}</pre>;
    }
  })();
  return (
    <div className="card p-5">
      <p className="mb-3 text-[13px] font-semibold">{card.title}</p>
      {body}
    </div>
  );
}
