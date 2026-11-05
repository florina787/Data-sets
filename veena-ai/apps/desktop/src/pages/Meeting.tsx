import { ChevronDown, CircleCheck, ClipboardList, Download, Flag, Lightbulb, ListChecks, MessageCircleQuestion, Mic, Monitor, NotebookPen, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { MicControl } from "../components/Composer";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, cn, Input } from "../components/ui";
import type { Message } from "../services/api";
import { useApp } from "../stores/app";
import { useAudio, useScreen } from "../stores/media";
import { DetectedQuestions, exportSession } from "./Workspace";

interface Notes {
  summary: string;
  key_points: string[];
  decisions: string[];
  action_items: { owner: string | null; task: string; due: string | null }[];
  open_questions: string[];
}

function clock(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return [h, m, s % 60].map((n) => String(n).padStart(2, "0")).join(":");
}

function parse(iso: string) {
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
}

/** The listening card: glowing orb, live waveform from the mic level, timer and controls. */
function ListeningCard() {
  const audio = useAudio();
  const state = audio.state.mic ?? audio.state.system;
  const live = audio.isActive();
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (live && startedAt === null) setStartedAt(Date.now());
    if (!live) setStartedAt(null);
  }, [live, startedAt]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, []);
  const bars = 36;
  const level = Math.min(1, Math.sqrt(audio.level) * 3);
  return (
    <Card className="relative overflow-hidden p-5">
      <div className="veena-glow pointer-events-none absolute inset-0 opacity-70" aria-hidden />
      <div className="relative flex items-center justify-between">
        <Badge tone={live ? "strong" : "outline"}>{live ? "● Live" : "Not recording"}</Badge>
        <span className="font-mono text-sm text-mocha tabular-nums">{startedAt ? clock(now - startedAt) : "00:00:00"}</span>
      </div>
      <div className="relative mt-4 flex h-28 items-center justify-center gap-[3px]" aria-hidden>
        {Array.from({ length: bars }, (_, i) => {
          const center = 1 - Math.abs(i - bars / 2) / (bars / 2);
          const h = live ? 18 + center * 70 * (0.35 + level) : 10 + center * 14;
          return <span key={i} className={cn("w-1.5 rounded-full bg-ginger", live && state === "listening" && "veena-wave-bar")} style={{ height: `${h}%`, animationDelay: `${(i % 9) * 0.09}s`, opacity: 0.45 + center * 0.55 }} />;
        })}
        <span className="absolute flex h-16 w-16 items-center justify-center rounded-full bg-caramel text-white shadow-[0_0_40px_rgb(184_120_72/0.6)]">
          <Mic size={24} />
        </span>
      </div>
      <p className="relative mt-3 text-center text-sm font-medium text-espresso">{live ? (state === "paused" ? "Paused" : "Listening…") : "Press Listen to start transcribing"}</p>
      <p className="relative text-center text-xs text-caramel">{live ? "AI is capturing key points on this computer" : "Audio is transcribed locally and never stored"}</p>
      <div className="relative mt-4 flex justify-center">
        <MicControl sessionMode="meeting" />
      </div>
    </Card>
  );
}

/** Colour-coded timeline of the transcript, one segment per line, by source. */
function Timeline({ lines }: { lines: Message[] }) {
  if (lines.length < 2) return null;
  const t0 = parse(lines[0].created_at).getTime();
  const t1 = parse(lines[lines.length - 1].created_at).getTime();
  const total = Math.max(1, t1 - t0);
  return (
    <Card className="p-4">
      <div className="flex h-2.5 overflow-hidden rounded-full bg-ivory">
        {lines.map((m, i) => {
          const next = i + 1 < lines.length ? parse(lines[i + 1].created_at).getTime() : t1 + total * 0.03;
          const w = ((next - parse(m.created_at).getTime()) / (total * 1.03)) * 100;
          const src = (m.meta.source as string) ?? "mic";
          return <span key={m.id} title={m.content} className={cn("h-full border-r-2 border-white", src === "system" ? "bg-sand" : src === "typed" ? "bg-mocha" : "bg-ginger")} style={{ width: `${Math.max(1.5, w)}%` }} />;
        })}
      </div>
      <div className="mt-2 flex items-center gap-4 font-mono text-[11px] text-caramel">
        <span>00:00:00</span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-ginger" /> microphone
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-sand" /> system audio
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-mocha" /> typed
        </span>
        <span className="ml-auto">{clock(total)}</span>
      </div>
    </Card>
  );
}

function Section({ icon: Icon, title, count, children, open: initial = true }: { icon: typeof Mic; title: string; count?: number; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(initial);
  return (
    <div className="rounded-2xl border border-cream bg-white">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-4 py-3 text-left" aria-expanded={open}>
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-ivory">
          <Icon size={15} className="text-ginger" />
        </span>
        <span className="flex-1">
          <h3 className="text-sm font-semibold text-espresso">{title}</h3>
          {count !== undefined && <span className="text-[11px] text-caramel">{count} item{count === 1 ? "" : "s"}</span>}
        </span>
        <ChevronDown size={16} className={cn("text-caramel transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="px-4 pb-4 text-sm leading-relaxed text-bark">{children}</div>}
    </div>
  );
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-xs text-caramel">{empty}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((x) => (
        <li key={x} className="flex gap-2">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-ginger" />
          {x}
        </li>
      ))}
    </ul>
  );
}

function SummaryPanel({ notes, busy, onGenerate, canGenerate }: { notes: Notes | null; busy: boolean; onGenerate: () => void; canGenerate: boolean }) {
  const [tab, setTab] = useState<"summary" | "actions" | "questions">("summary");
  const [done, setDone] = useState<Record<string, boolean>>({});
  return (
    <Card className="flex min-h-0 flex-col p-4">
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-ginger" />
        <h2 className="text-sm font-semibold text-espresso">AI Summary</h2>
        <Button size="sm" variant="primary" className="ml-auto" disabled={busy || !canGenerate} onClick={onGenerate}>
          <ClipboardList size={14} /> {busy ? "Writing notes…" : notes ? "Regenerate" : "Generate notes"}
        </Button>
      </div>
      <div className="mt-3 flex gap-1 rounded-xl bg-ivory p-1 text-xs" role="tablist">
        {(
          [
            ["summary", "Summary"],
            ["actions", `Actions${notes?.action_items.length ? ` ${notes.action_items.length}` : ""}`],
            ["questions", "Questions"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cn("flex-1 rounded-lg px-3 py-1.5 font-medium", tab === k ? "bg-white text-espresso shadow-[var(--shadow-soft)]" : "text-mocha")}>
            {label}
          </button>
        ))}
      </div>
      <div className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto">
        {tab === "summary" &&
          (notes ? (
            <>
              <Section icon={NotebookPen} title="Summary">
                <p>{notes.summary || "No summary."}</p>
              </Section>
              <Section icon={Lightbulb} title="Key takeaways" count={notes.key_points.length}>
                <List items={notes.key_points} empty="None recorded." />
              </Section>
              <Section icon={Flag} title="Decisions" count={notes.decisions.length}>
                <List items={notes.decisions} empty="No decisions in the transcript." />
              </Section>
              <Section icon={ListChecks} title="Action items" count={notes.action_items.length} open={false}>
                <List items={notes.action_items.map((a) => `${a.task}${a.owner ? ` — ${a.owner}` : ""}${a.due ? ` (due ${a.due})` : ""}`)} empty="No action items." />
              </Section>
              <Section icon={MessageCircleQuestion} title="Open questions" count={notes.open_questions.length} open={false}>
                <List items={notes.open_questions} empty="None." />
              </Section>
            </>
          ) : (
            <p className="py-8 text-center text-sm text-caramel">Notes appear here: summary, takeaways, decisions, action items and open questions.</p>
          ))}
        {tab === "actions" &&
          (notes?.action_items.length ? (
            <ul className="space-y-2">
              {notes.action_items.map((a) => (
                <li key={a.task} className="flex items-start gap-3 rounded-xl border border-cream bg-white p-3">
                  <button type="button" onClick={() => setDone({ ...done, [a.task]: !done[a.task] })} aria-label={done[a.task] ? "Mark not done" : "Mark done"} className="mt-0.5 text-ginger">
                    <CircleCheck size={18} className={done[a.task] ? "fill-ginger text-white" : ""} />
                  </button>
                  <div className="min-w-0 flex-1">
                    <p className={cn("text-sm text-bark", done[a.task] && "line-through opacity-60")}>{a.task}</p>
                    <p className="text-xs text-caramel">
                      {a.owner ?? "No owner"} · {a.due ?? "no due date"}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-caramel">No action items yet.</p>
          ))}
        {tab === "questions" && <DetectedQuestions />}
      </div>
    </Card>
  );
}

export function Meeting({ onShare }: { onShare: () => void }) {
  const { currentSession, newSession, api, toast, reloadMessages, messages, appInfo, partials, questions } = useApp();
  const screen = useScreen();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState("");
  const inMeeting = currentSession?.mode === "meeting";
  const lines = messages.filter((m) => m.role === "transcript");
  const notes = useMemo(() => {
    const last = [...messages].reverse().find((m) => m.role === "assistant" && m.meta.notes_json);
    return (last?.meta.notes_json as Notes | undefined) ?? null;
  }, [messages]);
  const questionTexts = new Set(questions.map((q) => q.text.trim()));

  const summarize = async () => {
    if (!api || !currentSession) return;
    setBusy(true);
    try {
      await api.post(`/api/meeting/${currentSession.id}/summarize`);
      await reloadMessages();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addLine = async () => {
    if (!api || !currentSession || !line.trim()) return;
    await api.post(`/api/sessions/${currentSession.id}/transcript`, { text: line, source: "typed" });
    setLine("");
    await reloadMessages();
  };

  if (!inMeeting) {
    return (
      <div className="flex h-full flex-col">
        <TopBar title="Meeting Copilot" subtitle="Transcribe an authorised meeting and produce notes, decisions and action items" />
        <div className="mx-auto w-full max-w-2xl px-6 py-10">
          <Card className="relative overflow-hidden p-8">
            <div className="veena-glow pointer-events-none absolute inset-0 opacity-60" aria-hidden />
            <div className="relative">
              <ShieldCheck size={26} className="text-ginger" />
              <h2 className="mt-3 text-xl font-semibold text-espresso">Before you record</h2>
              <p className="mt-2 text-sm leading-relaxed text-mocha">
                Only transcribe meetings where you are allowed to, and tell participants that a transcript is being taken where the law or your organisation requires it. Audio is
                transcribed on this computer and is not stored; only the text transcript is saved, and you can delete it at any time.
              </p>
              <label className="mt-4 flex items-start gap-2 text-sm text-bark">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 accent-[#B87848]" />I am authorised to transcribe this meeting.
              </label>
              <Button variant="primary" size="lg" className="mt-6" disabled={!consent} onClick={() => void newSession("meeting", `Meeting ${new Date().toLocaleString()}`)}>
                <Plus size={16} /> Start meeting session
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-w-0 flex-col">
      <TopBar
        title={currentSession.title}
        subtitle="Meeting room"
        actions={
          <>
            {appInfo?.systemAudioSupported && !screen.sharing && (
              <Button size="sm" variant="ghost" onClick={onShare}>
                <Monitor size={15} /> Capture meeting app audio
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => void exportSession(currentSession.id, currentSession.title)}>
              <Download size={15} /> Export
            </Button>
          </>
        }
      />
      <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-5 lg:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)] lg:overflow-hidden">
        <div className="flex min-h-0 flex-col gap-4 lg:overflow-y-auto">
          <ListeningCard />
          <Timeline lines={lines} />
          <Card className="flex min-h-64 flex-col p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-espresso">Live transcript</h2>
              <span className="text-xs text-caramel">{lines.length} lines</span>
            </div>
            <ul className="mt-3 flex-1 space-y-3 overflow-y-auto">
              {lines.length === 0 && !Object.keys(partials).length && <li className="py-10 text-center text-sm text-caramel">Start the microphone to transcribe, or add notes by hand below.</li>}
              {lines.map((m) => {
                const isQ = questionTexts.has(m.content.trim());
                return (
                  <li key={m.id} className="flex gap-3">
                    <span className="w-14 shrink-0 pt-0.5 font-mono text-[11px] text-sand">{parse(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                    <p className={cn("text-sm leading-relaxed text-bark", isQ && "rounded-md bg-ginger/25 px-1.5")}>
                      {m.meta.source === "system" && <span className="mr-1 text-xs text-caramel">[system]</span>}
                      {m.content}
                    </p>
                  </li>
                );
              })}
              {Object.entries(partials).map(([k, p]) => (
                <li key={k} className="flex gap-3 text-sm text-sand italic">
                  <span className="w-14 shrink-0" />
                  {p.text}
                </li>
              ))}
            </ul>
            <div className="mt-3 flex gap-2 border-t border-cream pt-3">
              <Input value={line} onChange={(e) => setLine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void addLine()} placeholder="Add a note or paste a transcript line" aria-label="Add transcript line" />
              <Button onClick={() => void addLine()} disabled={!line.trim()}>
                <NotebookPen size={15} /> Add
              </Button>
            </div>
          </Card>
        </div>
        <SummaryPanel notes={notes} busy={busy} onGenerate={() => void summarize()} canGenerate={lines.length > 0} />
      </div>
    </div>
  );
}
