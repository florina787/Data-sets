import { motion } from "framer-motion";
import { BookOpen, BriefcaseBusiness, MessagesSquare, Monitor } from "lucide-react";
import { CatMark, Wordmark } from "../components/CatMark";
import { Composer } from "../components/Composer";
import { TopBar } from "../components/Shell";
import { Card } from "../components/ui";
import { useApp } from "../stores/app";

export function Welcome({ onShare }: { onShare: () => void }) {
  const { newSession, setPage, ask, sessions, openSession, status } = useApp();
  const actions = [
    {
      icon: MessagesSquare,
      title: "Start Conversation",
      text: "Talk or type. VEENA listens, detects questions and answers locally.",
      go: async () => {
        await newSession("conversation");
        setPage("workspace");
      },
    },
    { icon: BriefcaseBusiness, title: "Practice Interview", text: "Rehearse with a mock interviewer and get scored feedback.", go: async () => setPage("interview") },
    { icon: Monitor, title: "Share Screen", text: "Pick a screen or window and ask about code, errors or diagrams.", go: async () => onShare() },
    { icon: BookOpen, title: "Upload Knowledge", text: "Ground answers in your resume, docs and notes with citations.", go: async () => setPage("knowledge") },
  ];
  const noModel = status && status.ollama.running && status.models.length === 0;
  return (
    <div className="flex h-full flex-col">
      <TopBar title="Welcome" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col items-center px-6 pt-12 pb-16">
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center text-center">
            <CatMark size={112} mood="idle" label="VEENA.AI mascot" />
            <div className="mt-4">
              <Wordmark size="lg" />
            </div>
            <p className="mt-2 text-base text-caramel">Your intelligent conversation companion.</p>
          </motion.div>

          {status && !status.ollama.running && (
            <Card className="mt-6 w-full border-ginger bg-cream/60 p-4 text-sm text-bark">
              Ollama is not running, so VEENA cannot answer yet. Start Ollama, then open{" "}
              <button type="button" className="font-medium underline" onClick={() => setPage("setup")}>
                Setup
              </button>
              .
            </Card>
          )}
          {noModel && (
            <Card className="mt-6 w-full border-ginger bg-cream/60 p-4 text-sm text-bark">
              No local model is installed.{" "}
              <button type="button" className="font-medium underline" onClick={() => setPage("setup")}>
                Download one in Setup
              </button>{" "}
              (free).
            </Card>
          )}

          <div className="mt-8 w-full">
            <Composer
              big
              placeholder="Ask VEENA anything…"
              onSend={async (text, style) => {
                await newSession("conversation");
                setPage("workspace");
                await ask({ text, answer_style: style });
              }}
            />
          </div>

          <div className="mt-8 grid w-full grid-cols-2 gap-3">
            {actions.map((a) => (
              <button key={a.title} type="button" onClick={() => void a.go()} className="text-left">
                <Card className="h-full p-4 transition-shadow hover:shadow-[var(--shadow-lift)]">
                  <a.icon size={20} className="text-caramel" />
                  <h3 className="mt-2 text-sm font-semibold text-espresso">{a.title}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-mocha">{a.text}</p>
                </Card>
              </button>
            ))}
          </div>

          <div className="mt-10 w-full">
            <h2 className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-caramel uppercase">Recent sessions</h2>
            {sessions.length === 0 ? (
              <p className="text-sm text-caramel">Your conversations will appear here. They stay on this computer.</p>
            ) : (
              <ul className="divide-y divide-cream rounded-xl border border-cream bg-white">
                {sessions.slice(0, 6).map((s) => (
                  <li key={s.id}>
                    <button type="button" onClick={() => void openSession(s.id)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-warm">
                      <span className="truncate text-bark">{s.title}</span>
                      <span className="ml-auto shrink-0 text-xs text-caramel capitalize">{s.mode}</span>
                      <span className="shrink-0 text-xs text-sand">{new Date(s.updated_at + (s.updated_at.endsWith("Z") ? "" : "Z")).toLocaleDateString()}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
