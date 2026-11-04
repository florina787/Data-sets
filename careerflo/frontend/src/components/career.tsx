import { motion } from "framer-motion";
import { Bookmark, BookmarkCheck, Briefcase, Building2, CircleDollarSign, MapPin } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ago, cn, salaryRange } from "@/lib/utils";
import { useFeature } from "@/lib/hooks";
import { Bust } from "./art/Avatar";
import { Pill } from "./ui";

export type Job = {
  id: string; title: string; company: string; location?: string; city?: string; work_arrangement?: string; employment_type?: string;
  industry?: string; salary_min?: number; salary_max?: number; salary_currency?: string; salary_verified?: boolean; posted_at?: string;
  apply_url?: string; source: string; origin_publisher?: string; is_synthetic?: boolean; required_skills?: string[];
};

export function PageHeader({ eyebrow, title, sub, children }: { eyebrow: string; title: ReactNode; sub?: string; children?: ReactNode }) {
  return (
    <div className="mx-auto mb-10 max-w-2xl pt-6 text-center">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="display mt-2">{title}</h1>
      {sub && <p className="muted mx-auto mt-3 max-w-lg text-[15px]">{sub}</p>}
      {children && <div className="mt-6 flex flex-wrap justify-center gap-2">{children}</div>}
    </div>
  );
}

/** Job card in the "search and apply" style: title, bookmark, meta grid, black Apply, posted strip. */
export function JobCard({ job, selected, saved, onSave, onSelect, footer }: {
  job: Job; selected?: boolean; saved?: boolean; onSave?: () => void; onSelect?: () => void; footer?: ReactNode;
}) {
  const meta = [
    [MapPin, [job.city || job.location, job.work_arrangement && job.work_arrangement[0].toUpperCase() + job.work_arrangement.slice(1)].filter(Boolean).join(" · ") || "—"], [Briefcase, job.employment_type || "—"],
    [Building2, job.industry || job.origin_publisher || job.source], [CircleDollarSign, salaryRange(job)],
  ] as const;
  return (
    <motion.div layout className={cn("overflow-hidden rounded-[22px] transition", selected ? "bg-sky/15 p-1 ring-1 ring-sky/50" : "bg-slate-100/70 p-1 dark:bg-white/5")}>
      <div className="card cursor-pointer rounded-[18px] p-5 shadow-none" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-[16px] font-semibold leading-snug">{job.title}</h3>
            <p className="muted text-[13px]">{job.company}</p>
          </div>
          <button aria-label={saved ? "Saved" : "Save job"} onClick={(e) => { e.stopPropagation(); onSave?.(); }}
            className="grid h-8 w-8 place-items-center rounded-lg ring-1 ring-black/10 hover:bg-slate-50 dark:ring-white/15">
            {saved ? <BookmarkCheck className="h-4 w-4 text-violet" /> : <Bookmark className="h-4 w-4" />}
          </button>
        </div>
        <div className="my-4 h-px bg-black/5 dark:bg-white/10" />
        <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-[12.5px] text-slate-600 dark:text-slate-300">
          {meta.map(([Icon, text], i) => (
            <span key={i} className="flex items-center gap-1.5 truncate"><Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />{text}</span>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2">
          <a href={job.apply_url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}
            className="flex h-9 flex-1 items-center justify-center rounded-full bg-ink text-[13px] font-medium text-white dark:bg-white dark:text-ink">
            {job.is_synthetic ? "View demo posting" : "Apply on employer site"}
          </a>
        </div>
      </div>
      <div className="flex items-center justify-center gap-2 py-2 text-[10.5px] font-medium uppercase tracking-[.12em] text-slate-500">
        {ago(job.posted_at) || "Date not published"}
        {job.is_synthetic ? <Pill tone="amber" className="normal-case tracking-normal">Synthetic demo</Pill>
          : <><span>·</span>{job.origin_publisher && job.source === "jsearch" ? `via ${job.origin_publisher}` : job.source}</>}
        {footer}
      </div>
    </motion.div>
  );
}

const LEVELS = ["Junior", "Mid-level", "Senior", "Staff", "Principal"];

/** Career progression row: past and future roles are monochrome; the current role is in colour. */
export function CareerProgression({ name, current, title }: { name: string; current: number; title: string }) {
  const base = title.replace(/^(Senior|Junior|Staff|Principal|Lead)\s+/i, "") || "Engineer";
  return (
    <div className="relative -mx-4 flex snap-x items-end gap-4 overflow-x-auto px-4 pb-4 pt-6 sm:justify-center">
      {LEVELS.map((lvl, i) => {
        const now = i === current;
        return (
          <motion.div key={lvl} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: now ? -10 : 0 }} transition={{ delay: i * 0.06 }}
            className={cn("relative w-36 shrink-0 snap-center overflow-hidden rounded-2xl ring-1 ring-black/5 sm:w-40", now ? "shadow-lift" : "opacity-90")}>
            <Bust seed={`${name}${i}`} className={cn("aspect-[4/5] w-full bg-white dark:bg-white/5", !now && "grayscale-soft")} />
            <div className={cn("absolute inset-x-2 bottom-2 rounded-xl px-3 py-2 text-left backdrop-blur", now ? "bg-white/85 dark:bg-ink/80" : "bg-white/70 dark:bg-ink/60")}>
              <p className="text-[12.5px] font-semibold leading-tight">{lvl === "Mid-level" ? base : `${lvl} ${base}`}</p>
              <p className="muted text-[11px]">{i < current ? "Completed" : now ? "You are here" : `Step ${i - current} ahead`}</p>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

export function levelIndex(years?: number | null, title = "") {
  const t = title.toLowerCase();
  if (t.includes("principal")) return 4;
  if (t.includes("staff")) return 3;
  if (t.includes("senior") || t.includes("lead")) return 2;
  if (years == null) return 1;
  return years >= 10 ? 3 : years >= 5 ? 2 : years >= 2 ? 1 : 0;
}

/** Contribution-style heatmap of activity per day (applications, interviews, runs). */
export function ActivityHeatmap({ dates, weeks = 14 }: { dates: string[]; weeks?: number }) {
  const counts = new Map<string, number>();
  dates.forEach((d) => counts.set(d.slice(0, 10), (counts.get(d.slice(0, 10)) || 0) + 1));
  const start = new Date();
  start.setDate(start.getDate() - weeks * 7 + 1);
  const cols = Array.from({ length: weeks }, (_, w) => Array.from({ length: 7 }, (_, d) => {
    const day = new Date(start);
    day.setDate(start.getDate() + w * 7 + d);
    return { key: day.toISOString().slice(0, 10), n: counts.get(day.toISOString().slice(0, 10)) || 0, month: day.getDate() <= 7 && d === 0 ? day.toLocaleString("en", { month: "short" }) : "" };
  }));
  const shade = (n: number) => (n === 0 ? "bg-slate-200/70 dark:bg-white/10" : n === 1 ? "bg-[#f5b9a8]" : n === 2 ? "bg-[#ec8d75]" : "bg-[#d9614a]");
  return (
    <div className="inline-block">
      <div className="ml-9 flex gap-[3px] text-[11px] text-slate-500">{cols.map((c, i) => <span key={i} className="w-3">{c[0].month}</span>)}</div>
      <div className="mt-1 flex gap-2">
        <div className="flex flex-col justify-between py-[2px] text-[11px] text-slate-500"><span>Mon</span><span>Wed</span><span>Fri</span></div>
        <div className="flex gap-[3px]">
          {cols.map((c, i) => <div key={i} className="flex flex-col gap-[3px]">{c.map((d) => <span key={d.key} title={`${d.key}: ${d.n}`} className={cn("h-3 w-3 rounded-[3px]", shade(d.n))} />)}</div>)}
        </div>
      </div>
    </div>
  );
}

/** "Resume Optimization — 1 of 2 free uses remaining." */
export function TrialMeter({ feature, className }: { feature: string; className?: string }) {
  const f = useFeature(feature);
  if (!f) return null;
  const onPlan = f.plan_limit > 0;
  return (
    <div className={cn("inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-[12px] ring-1 ring-black/5 dark:bg-white/5 dark:ring-white/10", className)}>
      <span className="flex gap-1">{Array.from({ length: f.trial_limit }).map((_, i) => <span key={i} className={cn("h-1.5 w-4 rounded-full", i < f.trial_remaining ? "bg-violet" : "bg-slate-200 dark:bg-white/15")} />)}</span>
      <span>
        {f.name} — {f.trial_remaining} of {f.trial_limit} free uses remaining
        {onPlan && <span className="muted"> · {f.plan_remaining}/{f.plan_limit} this month</span>}
      </span>
      {f.available === 0 && <Link to="/pricing" className="font-medium text-violet">Upgrade</Link>}
      {f.final_free_use && <span className="font-medium text-amber-600">Last free use</span>}
    </div>
  );
}
