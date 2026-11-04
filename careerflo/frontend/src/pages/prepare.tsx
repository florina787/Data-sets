import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Award, BookOpen, Download, FolderGit2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { AgentCursor } from "@/components/art/AgentCursor";
import { BookStairs, PATH_ART } from "@/components/art/Paths";
import { ScoreRing } from "@/components/Cards";
import { CareerProgression, levelIndex, PageHeader, TrialMeter, type Job } from "@/components/career";
import { Button, Card, Chip, Empty, ErrorNote, Input, Label, Pill, Textarea } from "@/components/ui";
import { api, download } from "@/lib/api";
import { useMetered } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const useResumes = () => useQuery({ queryKey: ["resumes"], queryFn: () => api<{ resumes: any[] }>("/api/resumes") });
const useSaved = () => useQuery({ queryKey: ["saved"], queryFn: () => api<{ jobs: Job[] }>("/api/jobs/saved") });

function JobPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const saved = useSaved();
  if (!saved.data?.jobs.length) return <p className="muted text-[12.5px]">Save a job in Job Discovery to target it here.</p>;
  return (
    <select className="h-10 w-full rounded-full bg-white px-4 text-sm ring-1 ring-black/10 dark:bg-white/5" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Target job">
      <option value="">Choose a saved job…</option>
      {saved.data.jobs.map((j) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}
    </select>
  );
}

export function ResumeStudio() {
  const qc = useQueryClient();
  const resumes = useResumes();
  const file = useRef<HTMLInputElement>(null);
  const [upErr, setUpErr] = useState<unknown>(null);
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState("");
  const tailor = useMetered("/api/resumes/tailor");
  const primary = resumes.data?.resumes.find((r) => r.is_primary) ?? resumes.data?.resumes[0];
  const detail = useQuery({ queryKey: ["resume", primary?.id], enabled: !!primary, queryFn: () => api<any>(`/api/resumes/${primary.id}`) });
  const versions = useQuery({ queryKey: ["versions", primary?.id], enabled: !!primary, queryFn: () => api<any>(`/api/resumes/${primary.id}/versions`) });
  const [cmp, setCmp] = useState<string[]>([]);
  const diff = useQuery({ queryKey: ["diff", ...cmp], enabled: cmp.length === 2, queryFn: () => api<any>(`/api/resumes/versions/${cmp[0]}/compare/${cmp[1]}`) });

  async function upload(f: File) {
    setUploading(true); setUpErr(null);
    const fd = new FormData(); fd.append("file", f);
    try { await api("/api/resumes", { method: "POST", body: fd }); qc.invalidateQueries({ queryKey: ["resumes"] }); } catch (x) { setUpErr(x); } finally { setUploading(false); }
  }
  const latestTitle = detail.data?.parsed?.experience?.[0]?.title ?? "AI Engineer";
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Resume Studio" title="Your story, tailored honestly" sub="We re-order and emphasise what's already true. Anything a job wants that you haven't shown becomes a question, never an invented line.">
        <input ref={file} type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        <Button onClick={() => file.current?.click()} loading={uploading}><Upload className="h-4 w-4" />Upload PDF or DOCX</Button>
      </PageHeader>
      <ErrorNote error={upErr} />
      {!primary ? <Empty art={<BookStairs className="h-20" />} title="No resume yet" body="Upload once; your original is kept unchanged forever." /> : (
        <>
          {detail.data && <CareerProgression name={detail.data.parsed?.contact?.name ?? "You"} current={levelIndex(detail.data.years_experience, latestTitle)} title={latestTitle} />}
          <div className="mt-8 grid gap-5 md:grid-cols-5">
            <Card className="md:col-span-2">
              <p className="text-[13px] font-semibold">{primary.title}</p>
              <p className="muted text-[12px]">{primary.years_experience ? `${primary.years_experience} verified years` : "Experience dates not detected"}</p>
              <div className="mt-3 flex flex-wrap gap-1.5">{primary.skills.slice(0, 18).map((s: string) => <Pill key={s}>{s}</Pill>)}</div>
              {detail.data?.analysis?.issues?.length > 0 && <ul className="mt-4 list-disc space-y-1 pl-4 text-[12.5px]">{detail.data.analysis.issues.map((i: string) => <li key={i}>{i}</li>)}</ul>}
            </Card>
            <Card className="relative md:col-span-3">
              <AgentCursor label="Resume Agent" tone="coral" className="-top-6 right-8" />
              <p className="text-[13px] font-semibold">Tailor for a job</p>
              <div className="mt-3"><JobPicker value={job} onChange={setJob} /></div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <Button disabled={!job} loading={tailor.isPending} onClick={() => tailor.mutate({ job_id: job, resume_id: primary.id })}>Optimize resume</Button>
                <TrialMeter feature="resume_optimization" />
              </div>
              <ErrorNote error={tailor.error} />
              {tailor.data && (
                <div className="mt-4 space-y-3">
                  <div className="flex items-center gap-3"><ScoreRing score={tailor.data.match.score} /><p className="text-[12.5px]">Match {tailor.data.match.grade} · summary: {tailor.data.summary_source}</p></div>
                  <Pill tone={tailor.data.validation.final.valid ? "emerald" : "coral"}>{tailor.data.validation.final.valid ? "Fact check passed" : `${tailor.data.validation.final.issues.length} unsupported statements flagged`}</Pill>
                  <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl bg-slate-50 p-4 text-[12px] dark:bg-white/5">{tailor.data.text}</pre>
                  {tailor.data.tailored.clarifying_questions.map((q: string) => <p key={q} className="text-[12.5px] text-amber-700">{q}</p>)}
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => download(tailor.data.downloads.pdf, "resume.pdf")}><Download className="h-3.5 w-3.5" />PDF</Button>
                    <Button size="sm" variant="outline" onClick={() => download(tailor.data.downloads.docx, "resume.docx")}><Download className="h-3.5 w-3.5" />DOCX</Button>
                  </div>
                </div>
              )}
            </Card>
          </div>
          {versions.data?.versions.length > 0 && (
            <Card className="mt-5">
              <p className="text-[13px] font-semibold">Version history <span className="muted font-normal">· pick two to compare</span></p>
              <div className="mt-3 flex flex-wrap gap-2">{versions.data.versions.map((v: any) => <Chip key={v.id} active={cmp.includes(v.id)} onClick={() => setCmp((c) => c.includes(v.id) ? c.filter((x) => x !== v.id) : [...c, v.id].slice(-2))}>{v.label}</Chip>)}</div>
              {diff.data && <pre className="mt-3 max-h-64 overflow-auto rounded-2xl bg-slate-50 p-3 text-[11.5px] dark:bg-white/5">{diff.data.diff.map((l: string, i: number) => <div key={i} className={cn(l.startsWith("+") && "text-emerald-700", l.startsWith("-") && "text-red-600")}>{l}</div>)}</pre>}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export function Ats() {
  const [job, setJob] = useState("");
  const [desc, setDesc] = useState("");
  const ats = useMetered("/api/ats/analyze");
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="ATS Intelligence" title="Will a parser read you right?" sub="Simulates keyword coverage, structure and parse-ability. Real ATS products differ." />
      <Card>
        <Label>Saved job</Label><JobPicker value={job} onChange={setJob} />
        <p className="muted my-3 text-center text-[12px]">or paste a description</p>
        <Textarea rows={4} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Paste a job description…" />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button disabled={!job && desc.length < 30} loading={ats.isPending} onClick={() => ats.mutate(job ? { job_id: job } : { job_description: desc })}>Run ATS check</Button>
          <TrialMeter feature="ats_intelligence" />
        </div>
      </Card>
      <ErrorNote error={ats.error} />
      {ats.data && (
        <Card className="mt-5">
          <div className="flex items-center gap-4"><ScoreRing score={ats.data.score} size={64} /><div><p className="font-semibold">ATS score</p><p className="muted text-[12.5px]">Keyword coverage {ats.data.keyword_coverage ?? "—"}%</p></div></div>
          <ul className="mt-4 space-y-2 text-[13px]">{ats.data.checks.map((c: any) => <li key={c.check} className="flex gap-2"><span>{c.passed ? "✓" : "○"}</span><span><b>{c.check}.</b> <span className="muted">{c.detail}</span></span></li>)}</ul>
          {ats.data.missing_keywords.length > 0 && <p className="mt-3 text-[12.5px]">Missing: {ats.data.missing_keywords.join(", ")}</p>}
          <p className="muted mt-2 text-[11.5px]">{ats.data.note}</p>
        </Card>
      )}
    </div>
  );
}

export function CoverLetters() {
  const [job, setJob] = useState("");
  const [tone, setTone] = useState("professional");
  const cl = useMetered("/api/cover-letters");
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Cover Letter Studio" title="A letter that sounds like you" sub="Drafted from verified facts, polished by Qwen, and fact-checked before you see it." />
      <Card>
        <JobPicker value={job} onChange={setJob} />
        <div className="mt-3 flex gap-2">{["professional", "warm", "concise"].map((t) => <Chip key={t} active={tone === t} onClick={() => setTone(t)}>{t}</Chip>)}</div>
        <div className="mt-4 flex flex-wrap items-center gap-3"><Button disabled={!job} loading={cl.isPending} onClick={() => cl.mutate({ job_id: job, tone })}>Write letter</Button><TrialMeter feature="cover_letter" /></div>
      </Card>
      <ErrorNote error={cl.error} />
      {cl.data && (
        <div className="mt-5 grid gap-5">
          <Card><Pill tone="violet">{cl.data.source}</Pill><pre className="mt-3 whitespace-pre-wrap font-serif text-[16px] leading-relaxed">{cl.data.letter}</pre>
            <Button size="sm" variant="outline" className="mt-3" onClick={() => navigator.clipboard.writeText(cl.data.letter)}>Copy</Button></Card>
          <Card><p className="text-[13px] font-semibold">Recruiter message</p><pre className="mt-2 whitespace-pre-wrap text-[13px]">{cl.data.recruiter_message}</pre></Card>
        </div>
      )}
    </div>
  );
}

export function InterviewPage() {
  const qc = useQueryClient();
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => api<{ topics: string[] }>("/api/interviews/topics") });
  const history = useQuery({ queryKey: ["interviews"], queryFn: () => api<{ interviews: any[] }>("/api/interviews") });
  const [role, setRole] = useState("Senior Forward Deployed AI Engineer");
  const [chosen, setChosen] = useState<string[]>([]);
  const start = useMetered("/api/interviews/mock");
  const [session, setSession] = useState<any>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  async function submit() {
    setBusy(true); setErr(null);
    try {
      const r = await api<any>(`/api/interviews/${session.interview_id}/answer`, { method: "POST", json: { answer } });
      setFeedback((f) => [...f, { q: session.question.question, ...r.evaluation }]);
      setAnswer("");
      setSession((s: any) => ({ ...s, question: r.next, done: r.completed, score: r.score }));
      if (r.completed) qc.invalidateQueries({ queryKey: ["interviews"] });
    } catch (x) { setErr(x); } finally { setBusy(false); }
  }
  const mock = history.data?.interviews.filter((i) => i.kind === "mock" && i.score != null) ?? [];
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Interview Intelligence" title="Practise out loud, improve fast" sub="General practice questions with rubric scoring. We never claim to know an employer's confidential questions." />
      {!session ? (
        <Card>
          <Label>Role</Label><Input value={role} onChange={(e) => setRole(e.target.value)} />
          <p className="mb-2 mt-4 text-[12.5px] font-medium">Topics (optional)</p>
          <div className="flex flex-wrap gap-1.5">{topics.data?.topics.map((t) => <Chip key={t} active={chosen.includes(t)} onClick={() => setChosen((c) => c.includes(t) ? c.filter((x) => x !== t) : [...c, t])}>{t.replace(/_/g, " ")}</Chip>)}</div>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button loading={start.isPending} onClick={() => start.mutate({ role, topics: chosen.length ? chosen : undefined, questions: 5 }, { onSuccess: (d) => { setSession(d); setFeedback([]); } })}>Start mock interview</Button>
            <TrialMeter feature="mock_interview" />
          </div>
          <ErrorNote error={start.error} />
        </Card>
      ) : (
        <div className="space-y-4">
          {feedback.map((f, i) => (
            <Card key={i} className="p-5">
              <p className="text-[13px] font-semibold">{f.q}</p>
              <div className="mt-2 flex items-center gap-3"><ScoreRing score={f.score * 10} size={40} /><p className="muted text-[12px]">coverage {f.rubric.coverage} · depth {f.rubric.depth} · structure {f.rubric.structure}</p></div>
              {f.suggestions.map((s: string) => <p key={s} className="mt-1 text-[12.5px]">→ {s}</p>)}
              {f.ai_feedback && <p className="mt-2 text-[12.5px] italic">Qwen: {f.ai_feedback}</p>}
              {f.followup && <p className="muted mt-1 text-[12px]">Follow-up to consider: {f.followup}</p>}
            </Card>
          ))}
          {session.done ? (
            <Card className="text-center"><p className="font-serif text-3xl">Session complete</p><p className="muted mt-1">Average score {session.score}/10</p><Button className="mt-4" onClick={() => setSession(null)}>New session</Button></Card>
          ) : session.question && (
            <Card className="relative">
              <AgentCursor label="Interviewer" tone="sky" className="-top-6 right-6" />
              <Pill>{session.question.topic}</Pill>
              <p className="mt-2 font-serif text-2xl leading-snug">{session.question.question}</p>
              <Textarea className="mt-4" rows={6} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Answer as you would in the interview…" />
              <Button className="mt-3" disabled={!answer.trim()} loading={busy} onClick={submit}>Submit answer</Button>
              <ErrorNote error={err} />
            </Card>
          )}
        </div>
      )}
      {mock.length > 0 && <p className="muted mt-8 text-center text-[12px]">Progress: {mock.length} completed sessions · latest {mock[0].score}/10</p>}
    </div>
  );
}

export function Coding() {
  const ex = useQuery({ queryKey: ["exercises"], queryFn: () => api<{ exercises: any[] }>("/api/coding/exercises") });
  const start = useMetered("/api/coding/sessions");
  const [session, setSession] = useState<any>(null);
  const [code, setCode] = useState("");
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Live Coding Coach" title="One problem, done well" sub="Your code runs in an isolated sandbox with strict time and memory limits." />
      {!session ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {ex.data?.exercises.map((e) => (
            <button key={e.id} className="card p-5 text-left transition hover:shadow-lift" onClick={() => start.mutate({ exercise_id: e.id }, { onSuccess: (d) => { setSession(d); setCode(d.exercise.signature + "\n    pass\n"); setResult(null); } })}>
              <Pill tone={e.difficulty === "easy" ? "emerald" : "amber"}>{e.difficulty}</Pill>
              <p className="mt-2 font-semibold">{e.title}</p><p className="muted mt-1 text-[12.5px]">{e.prompt}</p>
            </button>
          ))}
          <div className="sm:col-span-2"><TrialMeter feature="coding_coach" /><ErrorNote error={start.error} /></div>
        </div>
      ) : (
        <Card>
          <p className="font-semibold">{session.exercise.title}</p><p className="muted text-[13px]">{session.exercise.prompt}</p>
          <textarea value={code} onChange={(e) => setCode(e.target.value)} rows={12} spellCheck={false} aria-label="Code editor"
            className="mt-4 w-full rounded-2xl bg-ink p-4 font-mono text-[12.5px] text-slate-100 outline-none" />
          <div className="mt-3 flex gap-2">
            <Button loading={busy} onClick={async () => { setBusy(true); try { setResult(await api(`/api/coding/sessions/${session.session_id}/run`, { method: "POST", json: { code } })); } finally { setBusy(false); } }}>Run tests</Button>
            <Button variant="outline" onClick={() => setSession(null)}>Choose another</Button>
          </div>
          {result && (
            <div className="mt-4 text-[13px]">
              <p className="font-semibold">{result.passed}/{result.total} tests passed</p>
              {result.error && <p className="text-red-600">{result.error}</p>}
              {result.results?.map((r: any, i: number) => <p key={i} className={r.passed ? "text-emerald-700" : "text-red-600"}>Test {i + 1}: {r.passed ? "pass" : r.error ?? `got ${r.got}, expected ${r.expected}`}</p>)}
              {result.feedback && <p className="muted mt-1">{result.feedback}</p>}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

const PATH_LABEL: Record<string, string> = { ladder: "Ladder", lattice: "Lattice", wave: "Wave", portfolio: "Portfolio" };

export function Learning() {
  const cat = useQuery({ queryKey: ["learning"], queryFn: () => api<any>("/api/learning/catalog") });
  const roadmap = useMetered(() => "/api/analytics/roadmap");
  const [path, setPath] = useState<string | null>(null);
  const items = roadmap.data?.learning ?? cat.data?.skills ?? [];
  const shown = path ? items.filter((x: any) => (path === "portfolio" ? true : x.path === path)) : items;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="Skills & Learning" title="Four ways to grow" sub="Climb, move sideways, ride what's next, and prove it. Books and certifications are matched to the skills postings ask for.">
        <Button variant="violet" loading={roadmap.isPending} onClick={() => roadmap.mutate({})}>Build my personal plan</Button>
      </PageHeader>
      <div className="mb-4 flex justify-center"><TrialMeter feature="career_analytics" /></div>
      <ErrorNote error={roadmap.error} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(cat.data?.paths ?? {}).map(([k, desc]) => {
          const Art = PATH_ART[k as keyof typeof PATH_ART];
          return (
            <motion.button key={k} whileHover={{ y: -3 }} onClick={() => setPath(path === k ? null : k)}
              className={cn("card p-4 text-center", path === k && "ring-2 ring-violet/50")}>
              <Art className="mx-auto h-28 w-full" />
              <p className="mt-1 text-[14px] font-semibold">{PATH_LABEL[k]}</p>
              <p className="muted mt-1 text-[12px]">{desc as string}</p>
            </motion.button>
          );
        })}
      </div>
      <div className="mt-10 grid gap-4 md:grid-cols-2">
        {shown.map((x: any) => (
          <Card key={x.skill} className="p-5">
            <div className="flex items-center justify-between">
              <p className="font-semibold">{x.skill}</p>
              <Pill tone={x.path === "wave" ? "sky" : x.path === "lattice" ? "amber" : "violet"}>{PATH_LABEL[x.path]}{x.demand ? ` · in ${x.demand} postings` : ""}</Pill>
            </div>
            <ul className="mt-3 space-y-1.5 text-[13px]">
              {x.books.map((b: any) => <li key={b.title} className="flex gap-2"><BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-violet" /><span><i>{b.title}</i> <span className="muted">— {b.author}</span></span></li>)}
              {x.certifications.map((c: any) => <li key={c.name} className="flex gap-2"><Award className="mt-0.5 h-4 w-4 shrink-0 text-amber" /><span>{c.name} <span className="muted">— {c.issuer}</span></span></li>)}
              {x.portfolio_project && <li className="flex gap-2"><FolderGit2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald" />{x.portfolio_project}</li>}
            </ul>
          </Card>
        ))}
      </div>
      {!roadmap.data && <p className="muted mt-6 text-center text-[12px]">Showing the catalogue. Build your plan to rank it by your skill gaps. Career_flo is not affiliated with these publishers or certification bodies.</p>}
    </div>
  );
}
