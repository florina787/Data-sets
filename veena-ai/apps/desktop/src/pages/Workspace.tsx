import { Download, Lightbulb, ListChecks, MessageCircleQuestion } from "lucide-react";
import { useState } from "react";
import { CatMark } from "../components/CatMark";
import { Composer } from "../components/Composer";
import { MessageList } from "../components/Conversation";
import { Markdown } from "../components/Markdown";
import { ContextPanel, TopBar } from "../components/Shell";
import { Badge, Button, Section, Switch } from "../components/ui";
import { useApp } from "../stores/app";
import { useAudio } from "../stores/media";

export async function exportSession(sessionId: string, title: string) {
  const app = useApp.getState();
  try {
    const md = await app.api!.get<string>(`/api/sessions/${sessionId}/export?fmt=markdown`);
    const safe = title.replace(/[^\w\- ]+/g, "").trim().slice(0, 60) || "veena-session";
    const r = await window.veena!.saveFile(`${safe}.md`, md);
    if (r.saved) app.toast("success", `Exported to ${r.path}`);
  } catch (e) {
    app.toast("error", `Export failed: ${(e as Error).message}`);
  }
}

export function DetectedQuestions() {
  const { questions, ask, messages, currentSession } = useApp();
  if (!questions.length) return <p className="text-xs text-caramel">Questions VEENA hears will appear here.</p>;
  return (
    <ul className="space-y-2">
      {questions.slice(0, 8).map((q) => (
        <li key={q.timestamp + q.text} className="rounded-xl border border-cream bg-warm p-2.5">
          <p className="text-sm text-bark">{q.text}</p>
          <div className="mt-1.5 flex items-center gap-1.5">
            <Badge>{q.intent.replace("_", " ")}</Badge>
            <span className="text-[11px] text-caramel">{Math.round(q.confidence * 100)}%</span>
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto h-7 px-2 text-xs"
              onClick={() =>
                void ask({
                  text: q.text,
                  source: "speech",
                  intent: q.intent,
                  mode: currentSession?.mode ?? "conversation",
                  transcript_context: messages.filter((m) => m.role === "transcript").slice(-12).map((m) => m.content),
                })
              }
            >
              Answer
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Workspace() {
  const { currentSession, ask, followups, loadFollowups, api, toast, reloadMessages, messages, live } = useApp();
  const audio = useAudio();
  const [summary, setSummary] = useState<string | null>(null);
  const [summarising, setSummarising] = useState(false);

  const summarise = async () => {
    if (!currentSession || !api) return;
    setSummarising(true);
    try {
      const r = await api.post<{ summary: string }>(`/api/sessions/${currentSession.id}/summary`);
      setSummary(r.summary);
      await reloadMessages();
    } catch (e) {
      toast("error", (e as Error).message);
    } finally {
      setSummarising(false);
    }
  };

  const canAct = !!currentSession && messages.length > 0;
  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={currentSession?.title ?? "New conversation"}
          subtitle="Live transcript, detected questions and local AI answers"
          actions={
            <>
              <Button size="sm" variant="ghost" disabled={!canAct || summarising} onClick={() => void summarise()}>
                <ListChecks size={15} /> {summarising ? "Summarising…" : "Summary"}
              </Button>
              <Button size="sm" variant="ghost" disabled={!canAct} onClick={() => currentSession && void exportSession(currentSession.id, currentSession.title)}>
                <Download size={15} /> Export
              </Button>
            </>
          }
        />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-6">
            {summary && (
              <div className="mb-6 rounded-2xl border border-sand bg-ivory p-4">
                <div className="mb-1 flex items-center justify-between text-xs font-semibold tracking-wide text-caramel uppercase">
                  Session summary
                  <button type="button" className="text-caramel normal-case" onClick={() => setSummary(null)}>
                    Hide
                  </button>
                </div>
                <Markdown text={summary} />
              </div>
            )}
            <MessageList
              empty={
                <div className="flex flex-col items-center py-20 text-center">
                  <CatMark size={72} mood={audio.isActive("mic") ? "listening" : "idle"} />
                  <p className="mt-4 text-sm text-mocha">{audio.isActive("mic") ? "Listening. Ask a question out loud." : "Type a question, or press Listen to talk."}</p>
                  <p className="mt-1 text-xs text-caramel">Everything runs on this computer.</p>
                </div>
              }
            />
            {!live && canAct && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {followups.length ? (
                  followups.map((f) => (
                    <button key={f} type="button" onClick={() => void ask({ text: f })} className="rounded-full border border-cream bg-white px-3 py-1.5 text-xs text-mocha hover:border-sand hover:text-bark">
                      {f}
                    </button>
                  ))
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => void loadFollowups()}>
                    <Lightbulb size={14} /> Suggest follow-ups
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="border-t border-cream bg-warm px-6 py-4">
          <div className="mx-auto max-w-3xl">
            <Composer onSend={(text, style) => void ask({ text, answer_style: style, mode: currentSession?.mode ?? "conversation", transcript_context: messages.filter((m) => m.role === "transcript").slice(-12).map((m) => m.content) })} />
          </div>
        </div>
      </div>
      <ContextPanel>
        <Section title="Detected questions">
          <div className="mb-2">
            <Switch checked={audio.autoAnswer} onChange={audio.setAutoAnswer} label="Auto-answer spoken questions" />
          </div>
          <DetectedQuestions />
        </Section>
        <Section title="Shortcuts">
          <p className="flex items-center gap-1 text-xs text-mocha">
            <MessageCircleQuestion size={12} /> Ctrl+Shift+M toggles the microphone; Ctrl+Shift+Space focuses VEENA.
          </p>
        </Section>
      </ContextPanel>
    </div>
  );
}
