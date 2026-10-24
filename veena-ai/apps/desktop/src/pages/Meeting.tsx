import { ClipboardList, Download, Monitor, NotebookPen, Plus, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { MessageList } from "../components/Conversation";
import { MicControl } from "../components/Composer";
import { Markdown } from "../components/Markdown";
import { ContextPanel, TopBar } from "../components/Shell";
import { Button, Card, Input, Section } from "../components/ui";
import { useApp } from "../stores/app";
import { useScreen } from "../stores/media";
import { DetectedQuestions, exportSession } from "./Workspace";

export function Meeting({ onShare }: { onShare: () => void }) {
  const { currentSession, newSession, api, toast, reloadMessages, messages, appInfo } = useApp();
  const screen = useScreen();
  const [consent, setConsent] = useState(false);
  const [notes, setNotes] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [line, setLine] = useState("");
  const inMeeting = currentSession?.mode === "meeting";
  const transcriptCount = messages.filter((m) => m.role === "transcript").length;

  const summarize = async () => {
    if (!api || !currentSession) return;
    setBusy(true);
    try {
      const r = await api.post<{ markdown: string }>(`/api/meeting/${currentSession.id}/summarize`);
      setNotes(r.markdown);
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
        <div className="mx-auto max-w-2xl px-6 py-10">
          <Card className="p-6">
            <ShieldCheck size={24} className="text-caramel" />
            <h2 className="mt-3 text-lg font-semibold text-espresso">Before you record</h2>
            <p className="mt-2 text-sm leading-relaxed text-mocha">
              Only transcribe meetings where you are allowed to, and tell participants that a transcript is being taken where the law or your organisation requires it. Audio is
              transcribed on this computer and is not stored; only the text transcript is saved, and you can delete it at any time.
            </p>
            <label className="mt-4 flex items-start gap-2 text-sm text-bark">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 accent-[#99613E]" />I am authorised to transcribe this meeting.
            </label>
            <Button variant="primary" className="mt-5" disabled={!consent} onClick={() => void newSession("meeting", `Meeting ${new Date().toLocaleString()}`)}>
              <Plus size={15} /> Start meeting session
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={currentSession.title}
          subtitle="Meeting transcript"
          actions={
            <>
              <Button size="sm" variant="primary" disabled={busy || transcriptCount === 0} onClick={() => void summarize()}>
                <ClipboardList size={15} /> {busy ? "Writing notes…" : "Generate notes"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => void exportSession(currentSession.id, currentSession.title)}>
                <Download size={15} /> Export
              </Button>
            </>
          }
        />
        <div className="flex items-center gap-3 border-b border-cream bg-white px-6 py-2">
          <MicControl sessionMode="meeting" />
          {appInfo?.systemAudioSupported && !screen.sharing && (
            <Button size="sm" variant="ghost" onClick={onShare}>
              <Monitor size={15} /> Capture meeting app audio
            </Button>
          )}
          <span className="ml-auto text-xs text-caramel">{transcriptCount} transcript lines</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-6">
            {notes && (
              <Card className="mb-6 p-5">
                <Markdown text={notes} />
              </Card>
            )}
            <MessageList empty={<p className="py-16 text-center text-sm text-caramel">Start the microphone to transcribe, or add notes by hand below.</p>} />
          </div>
        </div>
        <div className="border-t border-cream bg-warm px-6 py-3">
          <div className="mx-auto flex max-w-3xl gap-2">
            <Input value={line} onChange={(e) => setLine(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void addLine()} placeholder="Add a note or paste a transcript line" aria-label="Add transcript line" />
            <Button onClick={() => void addLine()} disabled={!line.trim()}>
              <NotebookPen size={15} /> Add
            </Button>
          </div>
        </div>
      </div>
      <ContextPanel>
        <Section title="Questions raised">
          <DetectedQuestions />
        </Section>
      </ContextPanel>
    </div>
  );
}
