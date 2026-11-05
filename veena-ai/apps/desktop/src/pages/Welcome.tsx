import { motion } from "framer-motion";
import { ArrowRight, BookOpen, BriefcaseBusiness, CalendarClock, FolderOpen, MessagesSquare, Monitor, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { CatMark, Wordmark } from "../components/CatMark";
import { Composer } from "../components/Composer";
import { TopBar } from "../components/Shell";
import { Button, Card } from "../components/ui";
import { useApp } from "../stores/app";

const ROLES = [
  { label: "Software Developer", className: "left-[4%] top-[28%]", delay: "0s" },
  { label: "Product Designer", className: "right-[2%] top-[18%]", delay: "1.2s" },
  { label: "Sales Manager", className: "right-[6%] top-[58%]", delay: "2.1s" },
  { label: "AI Architect", className: "left-[8%] top-[66%]", delay: "0.6s" },
];

function since(iso: string) {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d;
}

/** The founder photo is a local file; if it is missing the cat takes its place. */
function FounderPhoto() {
  const [ok, setOk] = useState(true);
  if (!ok) return <CatMark size={168} mood="idle" label="VEENA.AI mascot" />;
  return <img src="./founder.png" alt="The founder of VEENA.AI" onError={() => setOk(false)} className="h-44 w-44 rounded-full object-cover ring-4 ring-white/70" />;
}

function Hero({ onStart, onPractice }: { onStart: () => void; onPractice: () => void }) {
  return (
    <section className="veena-grid-lines relative overflow-hidden rounded-[28px] border border-cream bg-warm">
      <div className="veena-glow pointer-events-none absolute inset-0" aria-hidden />
      {/* Oversized outlined wordmark behind the phone, as on the reference poster. */}
      <div aria-hidden className="veena-outline-text pointer-events-none absolute inset-x-0 top-6 text-center text-[clamp(96px,17vw,220px)] leading-none font-black tracking-tight select-none">
        veena.ai
      </div>
      <div className="relative grid items-center gap-6 px-8 pt-10 pb-8 lg:grid-cols-[1fr_auto_1fr]">
        <p className="max-w-60 text-sm leading-relaxed text-mocha lg:justify-self-end lg:text-right">
          Listens to your conversation, reads the screen you choose, and answers from your own documents.
        </p>

        <div className="relative mx-auto h-[400px] w-[230px]">
          {ROLES.map((r) => (
            <span
              key={r.label}
              className={`veena-float absolute z-10 hidden rounded-xl border border-cream bg-white px-3 py-1.5 text-[11px] font-medium whitespace-nowrap text-bark shadow-[var(--shadow-lift)] md:block ${r.className}`}
              style={{ animationDelay: r.delay, translate: r.className.includes("right") ? "60%" : "-60%" }}
            >
              {r.label}
            </span>
          ))}
          {/* Phone frame */}
          <div className="tokens-original absolute inset-0 rounded-[44px] border-[7px] border-espresso bg-espresso p-1 shadow-[var(--shadow-lift)]">
            <div className="relative flex h-full flex-col items-center overflow-hidden rounded-[36px] bg-gradient-to-b from-ivory to-cream pt-10">
              <div className="absolute top-2 h-5 w-20 rounded-full bg-espresso" aria-hidden />
              <FounderPhoto />
              <div className="mt-5 flex items-center gap-1.5">
                <CatMark size={22} />
                <Wordmark size="sm" />
              </div>
              <p className="mt-1 text-[22px] font-semibold text-espresso">Hey 👋</p>
              <p className="px-5 text-center text-xs text-caramel">Your intelligent conversation companion.</p>
            </div>
          </div>
        </div>

        <p className="max-w-60 text-sm leading-relaxed text-mocha">
          Runs entirely on your computer. <span className="font-semibold text-bark">$0 a month</span>, no account, no API key.
        </p>
      </div>

      <div className="relative px-8 pb-10 text-center">
        <motion.h2 initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="text-[clamp(28px,3.6vw,46px)] leading-tight font-semibold tracking-tight text-espresso">
          Nail every conversation.
          <br />
          <span className="text-caramel">Own every meeting.</span>
        </motion.h2>
        <div className="mt-6 flex justify-center gap-3">
          <Button variant="primary" size="lg" onClick={onStart}>
            Start conversation <ArrowRight size={17} />
          </Button>
          <Button variant="secondary" size="lg" onClick={onPractice}>
            Practice interview
          </Button>
        </div>
      </div>
    </section>
  );
}

interface Metrics {
  live: Record<string, { p50?: number; count: number }>;
  history: { summary: Record<string, { p50?: number; count: number }> };
  counts: { messages: number; sessions_by_mode: Record<string, number> };
}

export function Welcome({ onShare }: { onShare: () => void }) {
  const { newSession, setPage, ask, sessions, openSession, status, api } = useApp();
  const [now, setNow] = useState(new Date());
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    void api?.get<Metrics>("/api/metrics?days=30").then(setMetrics).catch(() => undefined);
  }, [api, sessions.length]);

  const start = async () => {
    await newSession("conversation");
    setPage("workspace");
  };
  const today = sessions.filter((s) => since(s.updated_at).toDateString() === now.toDateString());
  const firstToken = metrics?.history.summary["llm.first_token_ms"]?.p50;
  const tools = [
    { icon: MessagesSquare, title: "Start Conversation", text: "Talk or type. VEENA detects questions and answers locally.", go: start },
    { icon: BriefcaseBusiness, title: "Practice Interview", text: "Rehearse with a mock interviewer and get scored feedback.", go: async () => setPage("interview") },
    { icon: Monitor, title: "Share Screen", text: "Pick a screen or window and ask about code, errors or diagrams.", go: async () => onShare() },
    { icon: BookOpen, title: "Upload Knowledge", text: "Ground answers in your resume, docs and notes, with citations.", go: async () => setPage("knowledge") },
    { icon: Users, title: "Meeting Copilot", text: "Live transcript, decisions and action items.", go: async () => setPage("meeting") },
    { icon: FolderOpen, title: "Library", text: "Every session, organised in folders.", go: async () => setPage("library") },
  ];
  const noModel = status && status.ollama.running && status.models.length === 0;

  return (
    <div className="flex h-full flex-col">
      <TopBar title="Home" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl space-y-8 px-6 py-6">
          <Hero onStart={() => void start()} onPractice={() => setPage("interview")} />

          {status && !status.ollama.running && (
            <Card className="border-ginger p-4 text-sm text-bark">
              Ollama is not running, so VEENA cannot answer yet. Start Ollama, then open{" "}
              <button type="button" className="font-medium underline" onClick={() => setPage("setup")}>
                Setup
              </button>
              .
            </Card>
          )}
          {noModel && (
            <Card className="border-ginger p-4 text-sm text-bark">
              No local model is installed.{" "}
              <button type="button" className="font-medium underline" onClick={() => setPage("setup")}>
                Download one in Setup
              </button>{" "}
              (free).
            </Card>
          )}

          <Composer
            big
            placeholder="Ask VEENA anything…"
            onSend={async (text, style) => {
              await newSession("conversation");
              setPage("workspace");
              await ask({ text, answer_style: style });
            }}
          />

          {/* Dashboard */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="flex flex-col justify-between p-5 lg:col-span-2">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold tracking-[0.08em] text-caramel uppercase">Today</p>
                  <h2 className="mt-1 text-2xl font-semibold text-espresso">Welcome back</h2>
                  <p className="mt-1 text-sm text-mocha">
                    {today.length === 0 ? "No sessions yet today." : `${today.length} session${today.length === 1 ? "" : "s"} today.`} Everything stays on this computer.
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[11px] tracking-wide text-caramel uppercase">Now</p>
                  <p className="text-2xl font-semibold text-espresso tabular-nums">{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
                </div>
              </div>
              <ul className="mt-4 divide-y divide-cream">
                {today.slice(0, 4).map((s) => (
                  <li key={s.id} className="flex items-center gap-3 py-2.5">
                    <span className="flex h-9 w-12 shrink-0 items-center justify-center rounded-xl bg-ivory text-xs font-semibold text-caramel tabular-nums">
                      {since(s.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-bark">{s.title}</p>
                      <p className="text-xs text-caramel capitalize">{s.mode} · {s.message_count ?? 0} messages</p>
                    </div>
                    <Button size="sm" variant="primary" onClick={() => void openSession(s.id)}>
                      Open
                    </Button>
                  </li>
                ))}
                {today.length === 0 && (
                  <li className="flex items-center gap-2 py-3 text-sm text-caramel">
                    <CalendarClock size={15} /> Start a conversation or a meeting to see it here.
                  </li>
                )}
              </ul>
            </Card>
            <Card className="p-5">
              <p className="text-xs font-semibold tracking-[0.08em] text-caramel uppercase">Stats</p>
              <dl className="mt-3 grid grid-cols-2 gap-3">
                {[
                  ["Sessions", String(sessions.length)],
                  ["Messages", String(metrics?.counts.messages ?? "–")],
                  ["First word", firstToken == null ? "–" : firstToken >= 1000 ? `${(firstToken / 1000).toFixed(1)} s` : `${Math.round(firstToken)} ms`],
                  ["Monthly cost", "$0"],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-ivory p-3">
                    <dt className="text-[11px] text-caramel">{k}</dt>
                    <dd className="text-xl font-semibold text-espresso tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
              <button type="button" onClick={() => setPage("analytics")} className="mt-3 text-xs text-caramel underline">
                Open analytics
              </button>
            </Card>
          </div>

          {/* Powerful tools */}
          <section>
            <h2 className="text-xl font-semibold text-espresso">Powerful tools that make conversations effortless</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {tools.map((a) => (
                <button key={a.title} type="button" onClick={() => void a.go()} className="text-left">
                  <Card className="h-full p-4 transition-shadow hover:shadow-[var(--shadow-lift)]">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ivory">
                      <a.icon size={18} className="text-ginger" />
                    </span>
                    <h3 className="mt-3 text-sm font-semibold text-espresso">{a.title}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-mocha">{a.text}</p>
                  </Card>
                </button>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-caramel uppercase">Recent sessions</h2>
            {sessions.length === 0 ? (
              <p className="text-sm text-caramel">Your conversations will appear here. They stay on this computer.</p>
            ) : (
              <ul className="divide-y divide-cream rounded-xl border border-cream bg-white">
                {sessions.slice(0, 6).map((s) => (
                  <li key={s.id}>
                    <button type="button" onClick={() => void openSession(s.id)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-ivory">
                      <span className="truncate text-bark">{s.title}</span>
                      <span className="ml-auto shrink-0 text-xs text-caramel capitalize">{s.mode}</span>
                      <span className="shrink-0 text-xs text-sand">{since(s.updated_at).toLocaleDateString()}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
