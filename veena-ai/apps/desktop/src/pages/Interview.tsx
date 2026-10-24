import { ArrowRight, BriefcaseBusiness, Mic, MicOff, RotateCcw, Sparkles, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CatMark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, cn, Select, Textarea } from "../components/ui";
import { useApp } from "../stores/app";
import { onFinalTranscript, useAudio } from "../stores/media";

interface Turn {
  id: number;
  ordinal: number;
  category: string;
  question: string;
  answer: string | null;
  score: number | null;
  feedback: Feedback | null;
}
interface Feedback {
  score: number;
  strengths: string[];
  improvements: string[];
  model_answer_outline: string[];
  follow_up_question: string;
  model: string;
}
interface Review {
  answered: number;
  total: number;
  average_score: number | null;
  by_category: Record<string, number>;
  top_improvements: string[];
  turns: Turn[];
}

function speak(text: string) {
  // Local OS voices via the Web Speech API (SAPI on Windows, AVSpeech on macOS).
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

export function Interview() {
  const { api, collections, toast, settings, updateSettings, setPage } = useApp();
  const audio = useAudio();
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [role, setRole] = useState("senior_ai_engineer");
  const [focus, setFocus] = useState("mixed");
  const [resume, setResume] = useState("");
  const [jd, setJd] = useState("");
  const [interview, setInterview] = useState<{ id: string; session_id: string } | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [current, setCurrent] = useState(0);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const answerRef = useRef(answer);
  answerRef.current = answer;

  useEffect(() => {
    void api?.get<{ roles: Record<string, string> }>("/api/interview/roles").then((r) => setRoles(r.roles));
  }, [api]);

  // Spoken answers: final transcripts append to the answer box.
  useEffect(() => onFinalTranscript((text) => setAnswer((a) => (a ? a + " " : "") + text)), []);

  const turns = review?.turns ?? [];
  const turn = turns[current];

  useEffect(() => {
    if (turn && settings?.speak_interviewer && !turn.answer) speak(turn.question);
  }, [turn, settings?.speak_interviewer]);

  const refresh = async (id: string) => setReview(await api!.get<Review>(`/api/interview/${id}`));

  const start = async () => {
    if (!api) return;
    setBusy("Preparing questions…");
    try {
      const r = await api.post<{ interview: { id: string }; session: { id: string } }>("/api/interview", {
        role,
        focus,
        resume_collection_id: resume || null,
        job_description: jd || null,
      });
      setInterview({ id: r.interview.id, session_id: r.session.id });
      const q = await api.post<{ source: string }>(`/api/interview/${r.interview.id}/questions`, { count: 5 });
      setSource(q.source);
      await refresh(r.interview.id);
      setCurrent(0);
      setAnswer("");
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const submit = async () => {
    if (!api || !turn || !answer.trim() || !interview) return;
    setBusy("Evaluating your answer…");
    try {
      await api.post(`/api/interview/turns/${turn.id}/evaluate`, { answer });
      await refresh(interview.id);
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const more = async () => {
    if (!api || !interview) return;
    setBusy("Generating more questions…");
    try {
      await api.post(`/api/interview/${interview.id}/questions`, { count: 3 });
      await refresh(interview.id);
    } finally {
      setBusy(null);
    }
  };

  const micOn = audio.isActive("mic");
  const resumes = collections.filter((c) => c.kind === "resume" || c.kind === "general" || c.kind === "project");

  if (!interview || !review) {
    return (
      <div className="flex h-full flex-col">
        <TopBar title="Interview Practice" subtitle="Rehearse with a local mock interviewer" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-8">
            <div className="mb-6 flex items-center gap-4">
              <CatMark size={64} mood="idle" />
              <div>
                <h2 className="text-lg font-semibold text-espresso">Set up a practice session</h2>
                <p className="text-sm text-mocha">For rehearsal only. VEENA is not meant to be used covertly in assessments that prohibit AI.</p>
              </div>
            </div>
            <Card className="space-y-4 p-5">
              <div className="grid grid-cols-2 gap-4">
                <label className="text-sm text-bark">
                  Target role
                  <Select value={role} onChange={(e) => setRole(e.target.value)} className="mt-1">
                    {Object.entries(roles).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="text-sm text-bark">
                  Focus
                  <Select value={focus} onChange={(e) => setFocus(e.target.value)} className="mt-1">
                    {["mixed", "behavioral", "coding", "architecture", "leadership", "technical"].map((f) => (
                      <option key={f} value={f}>
                        {f[0].toUpperCase() + f.slice(1)}
                      </option>
                    ))}
                  </Select>
                </label>
              </div>
              <label className="block text-sm text-bark">
                Resume context
                <Select value={resume} onChange={(e) => setResume(e.target.value)} className="mt-1">
                  <option value="">No resume (feedback will not assume your experience)</option>
                  {resumes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
                <button type="button" onClick={() => setPage("knowledge")} className="mt-1 text-xs text-caramel underline">
                  Upload a resume in Knowledge
                </button>
              </label>
              <label className="block text-sm text-bark">
                Job description (optional)
                <Textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={5} className="mt-1" placeholder="Paste the job description to tailor questions" />
              </label>
              <Button variant="primary" size="lg" onClick={() => void start()} disabled={!!busy}>
                <BriefcaseBusiness size={17} /> {busy ?? "Start practice interview"}
              </Button>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  const fb = turn?.feedback;
  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={`Practice: ${roles[role] ?? role}`}
          subtitle={source === "bank" ? "Questions from the built-in bank (no model available to tailor them)" : "Questions tailored by your local model"}
          actions={
            <Button size="sm" variant="ghost" onClick={() => setInterview(null)}>
              <RotateCcw size={14} /> New session
            </Button>
          }
        />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-5 px-6 py-6">
            <div className="flex flex-wrap gap-1.5">
              {turns.map((t, i) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => {
                    setCurrent(i);
                    setAnswer(t.answer ?? "");
                  }}
                  className={cn("rounded-lg border px-2.5 py-1 text-xs", i === current ? "border-caramel bg-cream text-bark" : "border-cream bg-white text-mocha")}
                >
                  Q{i + 1} {t.score != null && `· ${t.score.toFixed(1)}`}
                </button>
              ))}
            </div>
            {turn && (
              <Card className="p-5">
                <div className="flex items-start gap-3">
                  <CatMark size={40} mood={busy ? "thinking" : micOn ? "listening" : "still"} />
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <Badge>{turn.category}</Badge>
                      <span className="text-xs text-caramel">Mock interviewer</span>
                      <button type="button" onClick={() => speak(turn.question)} className="ml-auto text-caramel hover:text-bark" aria-label="Read question aloud">
                        <Volume2 size={15} />
                      </button>
                    </div>
                    <p className="text-[15px] leading-relaxed text-espresso">{turn.question}</p>
                  </div>
                </div>
                <Textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={7} className="mt-4" placeholder="Type your answer, or press Speak and answer out loud." aria-label="Your answer" />
                <div className="mt-3 flex items-center gap-2">
                  {micOn ? (
                    <Button variant="secondary" onClick={() => void audio.stop("mic")}>
                      <MicOff size={15} /> Stop speaking
                    </Button>
                  ) : (
                    <Button variant="secondary" onClick={() => void audio.start("mic", interview.session_id)}>
                      <Mic size={15} /> Speak answer
                    </Button>
                  )}
                  <Button variant="primary" className="ml-auto" disabled={!answer.trim() || !!busy} onClick={() => void submit()}>
                    <Sparkles size={15} /> {busy ?? "Get feedback"}
                  </Button>
                  {current < turns.length - 1 && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setCurrent(current + 1);
                        setAnswer(turns[current + 1].answer ?? "");
                      }}
                    >
                      Next <ArrowRight size={15} />
                    </Button>
                  )}
                </div>
              </Card>
            )}
            {fb && (
              <Card className="p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-espresso">Feedback</h3>
                  <span className="text-2xl font-semibold text-bark tabular-nums">
                    {fb.score.toFixed(1)}
                    <span className="text-sm text-caramel">/10</span>
                  </span>
                </div>
                <div className="mt-3 grid gap-4 md:grid-cols-2">
                  <div>
                    <h4 className="text-xs font-semibold tracking-wide text-caramel uppercase">Strengths</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-bark">{fb.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold tracking-wide text-caramel uppercase">Improve</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-bark">{fb.improvements.map((s) => <li key={s}>{s}</li>)}</ul>
                  </div>
                </div>
                {fb.model_answer_outline.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-xs font-semibold tracking-wide text-caramel uppercase">A strong answer would cover</h4>
                    <ol className="mt-1 list-decimal space-y-1 pl-4 text-sm text-bark">{fb.model_answer_outline.map((s) => <li key={s}>{s}</li>)}</ol>
                  </div>
                )}
                {fb.follow_up_question && <p className="mt-4 rounded-xl bg-ivory p-3 text-sm text-bark">Follow-up: {fb.follow_up_question}</p>}
                <p className="mt-2 text-[11px] text-sand">Scored by {fb.model} on this computer.</p>
              </Card>
            )}
          </div>
        </div>
      </div>
      <aside className="w-80 shrink-0 space-y-5 overflow-y-auto border-l border-cream bg-white p-4">
        <Card className="p-4">
          <h3 className="text-xs font-semibold tracking-wide text-caramel uppercase">Practice score</h3>
          <p className="mt-1 text-3xl font-semibold text-bark tabular-nums">{review.average_score != null ? review.average_score.toFixed(1) : "–"}</p>
          <p className="text-xs text-mocha">
            {review.answered} of {review.total} answered
          </p>
          <div className="mt-3 space-y-1.5">
            {Object.entries(review.by_category).map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-xs text-mocha">
                  <span className="capitalize">{k}</span>
                  <span>{v.toFixed(1)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-cream">
                  <div className="h-1.5 rounded-full bg-caramel" style={{ width: `${v * 10}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
        {review.top_improvements.length > 0 && (
          <div>
            <h3 className="mb-2 text-xs font-semibold tracking-wide text-caramel uppercase">Improvement suggestions</h3>
            <ul className="space-y-1.5 text-sm text-bark">
              {review.top_improvements.map((s) => (
                <li key={s} className="rounded-lg bg-warm p-2">
                  {s}
                </li>
              ))}
            </ul>
          </div>
        )}
        <Button variant="secondary" className="w-full" onClick={() => void more()} disabled={!!busy}>
          More questions
        </Button>
        <label className="flex items-center gap-2 text-xs text-mocha">
          <input type="checkbox" checked={settings?.speak_interviewer ?? false} onChange={(e) => void updateSettings({ speak_interviewer: e.target.checked })} className="accent-[#99613E]" />
          Read questions aloud (local system voice)
        </label>
      </aside>
    </div>
  );
}
