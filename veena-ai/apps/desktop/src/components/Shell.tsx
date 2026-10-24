import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3,
  BookOpen,
  BriefcaseBusiness,
  Info,
  MessagesSquare,
  Mic,
  Monitor,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Search,
  Settings as SettingsIcon,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { ScreenSource } from "../services/bridge";
import { type Page, useApp } from "../stores/app";
import { useAudio, useScreen } from "../stores/media";
import { CatMark, Wordmark } from "./CatMark";
import { Badge, Button, cn, Input, Section, StatusDot, Switch } from "./ui";

const NAV: { page: Page; label: string; icon: typeof MessagesSquare }[] = [
  { page: "workspace", label: "Conversation", icon: MessagesSquare },
  { page: "screen", label: "Screen Intelligence", icon: Monitor },
  { page: "meeting", label: "Meeting Copilot", icon: Users },
  { page: "interview", label: "Interview Practice", icon: BriefcaseBusiness },
  { page: "knowledge", label: "Knowledge", icon: BookOpen },
  { page: "analytics", label: "Analytics", icon: BarChart3 },
];

const MODE_ICON = { conversation: MessagesSquare, screen: Monitor, meeting: Users, interview: BriefcaseBusiness };

export function Sidebar() {
  const { page, setPage, sessions, loadSessions, openSession, deleteSession, currentSession, sidebarOpen, toggleSidebar, newSession, collections } = useApp();
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => void loadSessions(q), 250);
    return () => clearTimeout(t);
  }, [q, loadSessions]);

  if (!sidebarOpen) {
    return (
      <aside className="flex w-14 flex-col items-center gap-2 border-r border-cream bg-white py-3">
        <button type="button" onClick={() => setPage("welcome")} aria-label="Home">
          <CatMark size={32} />
        </button>
        <Button size="icon" variant="ghost" onClick={toggleSidebar} aria-label="Expand sidebar">
          <PanelLeftOpen size={17} />
        </Button>
        {NAV.map((n) => (
          <Button key={n.page} size="icon" variant={page === n.page ? "subtle" : "ghost"} onClick={() => setPage(n.page)} aria-label={n.label} title={n.label}>
            <n.icon size={17} />
          </Button>
        ))}
        <div className="mt-auto">
          <Button size="icon" variant="ghost" onClick={() => setPage("settings")} aria-label="Settings">
            <SettingsIcon size={17} />
          </Button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-cream bg-white">
      <div className="flex items-center gap-2 px-4 py-3">
        <button type="button" onClick={() => setPage("welcome")} className="flex items-center gap-2" aria-label="Home">
          <CatMark size={30} />
          <Wordmark size="sm" />
        </button>
        <Button size="icon" variant="ghost" className="ml-auto" onClick={toggleSidebar} aria-label="Collapse sidebar">
          <PanelLeftClose size={17} />
        </Button>
      </div>
      <div className="px-3">
        <Button
          variant="primary"
          className="w-full"
          onClick={async () => {
            await newSession("conversation");
            setPage("workspace");
          }}
        >
          <Plus size={16} /> New conversation
        </Button>
      </div>
      <nav className="mt-3 space-y-0.5 px-2" aria-label="Modes">
        {NAV.map((n) => (
          <button
            key={n.page}
            type="button"
            onClick={() => setPage(n.page)}
            className={cn("flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm", page === n.page ? "bg-ivory font-medium text-espresso" : "text-mocha hover:bg-warm")}
          >
            <n.icon size={16} />
            {n.label}
          </button>
        ))}
      </nav>
      <Section title="Sessions" className="mt-4 flex min-h-0 flex-1 flex-col px-3">
        <div className="relative mb-2">
          <Search size={14} className="absolute top-3 left-2.5 text-sand" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search history" className="h-9 pl-8" aria-label="Search sessions" />
        </div>
        <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto pb-2">
          {sessions.length === 0 && <li className="px-2 py-3 text-xs text-caramel">{q ? "No matching sessions." : "No sessions yet."}</li>}
          {sessions.map((s) => {
            const Icon = MODE_ICON[s.mode];
            return (
              <li key={s.id} className="group relative">
                <button
                  type="button"
                  onClick={() => void openSession(s.id)}
                  className={cn("flex w-full items-center gap-2 rounded-lg px-2 py-1.5 pr-8 text-left text-sm", currentSession?.id === s.id ? "bg-cream text-espresso" : "text-mocha hover:bg-warm")}
                >
                  <Icon size={14} className="shrink-0 text-caramel" />
                  <span className="truncate">{s.title}</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`Delete "${s.title}"? This cannot be undone.`)) void deleteSession(s.id);
                  }}
                  className="absolute top-1.5 right-1.5 hidden rounded p-0.5 text-sand group-hover:block hover:text-bark focus:block"
                  aria-label={`Delete ${s.title}`}
                >
                  <Trash2 size={14} />
                </button>
              </li>
            );
          })}
        </ul>
      </Section>
      <div className="border-t border-cream px-3 py-2 text-xs text-caramel">
        <button type="button" onClick={() => setPage("knowledge")} className="mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-mocha hover:bg-warm">
          <BookOpen size={14} /> {collections.length} knowledge collection{collections.length === 1 ? "" : "s"}
        </button>
        <div className="flex gap-1">
          <button type="button" onClick={() => setPage("settings")} className="flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-mocha hover:bg-warm">
            <SettingsIcon size={14} /> Settings
          </button>
          <button type="button" onClick={() => setPage("about")} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-mocha hover:bg-warm" aria-label="About">
            <Info size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function ContextPanel({ children }: { children?: ReactNode }) {
  const { contextOpen, toggleContext, currentSession, status, settings, collections, selectedCollections, toggleCollection, live, setPage } = useApp();
  const screen = useScreen();
  if (!contextOpen) {
    return (
      <div className="border-l border-cream bg-white p-2">
        <Button size="icon" variant="ghost" onClick={toggleContext} aria-label="Expand context panel">
          <PanelRightOpen size={17} />
        </Button>
      </div>
    );
  }
  const model = live?.meta?.model ?? settings?.text_model ?? status?.models[0]?.name;
  return (
    <aside className="flex w-80 shrink-0 flex-col gap-5 overflow-x-hidden overflow-y-auto border-l border-cream bg-white p-4" aria-label="Context">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-espresso">Context</h2>
        <Button size="icon" variant="ghost" onClick={toggleContext} aria-label="Collapse context panel">
          <PanelRightClose size={17} />
        </Button>
      </div>
      {children}
      {screen.sharing && (
        <Section title="Screen preview">
          <div className="overflow-hidden rounded-xl border border-cream bg-espresso">
            {screen.lastFrame ? <img src={screen.lastFrame} alt="Last analysed frame" className="w-full" /> : <p className="p-3 text-xs text-sand">No frame analysed yet.</p>}
          </div>
          <p className="mt-1 truncate text-xs text-caramel">Sharing: {screen.sourceName}</p>
        </Section>
      )}
      <Section title="Knowledge for answers">
        {collections.length === 0 ? (
          <button type="button" onClick={() => setPage("knowledge")} className="text-xs text-caramel underline">
            Upload documents to ground answers
          </button>
        ) : (
          <ul className="space-y-1.5">
            {collections.map((c) => (
              <li key={c.id}>
                <label className="flex cursor-pointer items-center gap-2 text-sm text-bark">
                  <input type="checkbox" checked={selectedCollections.includes(c.id)} onChange={() => toggleCollection(c.id)} className="accent-[#99613E]" />
                  <span className="truncate">{c.name}</span>
                  <Badge className="ml-auto">{c.documents.length} docs</Badge>
                </label>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="Model">
        <dl className="space-y-1 text-sm">
          <div className="flex justify-between gap-2">
            <dt className="text-caramel">Text</dt>
            <dd className="truncate text-bark">{model ?? "none installed"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-caramel">Vision</dt>
            <dd className="truncate text-bark">{settings?.vision_model ?? status?.models.find((m) => m.vision)?.name ?? "none installed"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-caramel">Speech</dt>
            <dd className="text-bark">whisper {settings?.asr_model}</dd>
          </div>
        </dl>
      </Section>
      {currentSession && (
        <Section title="Session">
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-caramel">Title</dt>
              <dd className="truncate text-bark">{currentSession.title}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-caramel">Mode</dt>
              <dd className="text-bark capitalize">{currentSession.mode}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-caramel">Started</dt>
              <dd className="text-bark">{new Date(currentSession.created_at + (currentSession.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</dd>
            </div>
          </dl>
        </Section>
      )}
    </aside>
  );
}

/** Always-visible capture indicators: privacy requires the user to see when VEENA hears or sees. */
export function CaptureIndicators() {
  const audio = useAudio();
  const screen = useScreen();
  const { setPage } = useApp();
  const mic = audio.isActive("mic");
  const sys = audio.isActive("system");
  if (!mic && !sys && !screen.sharing) return null;
  return (
    <div className="flex items-center gap-2" role="status" aria-label="Active capture">
      {(mic || sys) && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-bark px-3 py-1 text-xs font-medium text-white">
          <Mic size={12} /> {mic && sys ? "Mic + system audio" : mic ? "Microphone on" : "System audio on"}
          {audio.state.mic === "paused" && " (paused)"}
        </span>
      )}
      {screen.sharing && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-bark px-3 py-1 text-xs font-medium text-white">
          <Monitor size={12} />
          <button type="button" onClick={() => setPage("screen")} className="max-w-48 truncate underline-offset-2 hover:underline">
            Sharing {screen.sourceName}
          </button>
          {screen.continuous && "· continuous"}
          <button type="button" onClick={() => screen.stop()} className="ml-1 rounded-full bg-espresso px-2 py-0.5 hover:bg-mocha" aria-label="Stop sharing">
            Stop
          </button>
        </span>
      )}
    </div>
  );
}

export function TopBar({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  const { status, backend } = useApp();
  const ollama = status?.ollama.running;
  return (
    <header className="flex min-h-14 items-center gap-4 border-b border-cream bg-white/80 px-5 py-2 backdrop-blur">
      <div className="min-w-0">
        <h1 className="truncate text-[15px] font-semibold text-espresso">{title}</h1>
        {subtitle && <p className="truncate text-xs text-caramel">{subtitle}</p>}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <CaptureIndicators />
        {actions}
        <StatusDot
          state={backend?.status !== "ready" ? "busy" : ollama ? "ok" : "problem"}
          label={backend?.status !== "ready" ? "Starting" : ollama ? "Local AI ready" : "Ollama offline"}
        />
      </div>
    </header>
  );
}

export function SourcePicker({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { appInfo, toast } = useApp();
  const screen = useScreen();
  const [sources, setSources] = useState<ScreenSource[] | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [audio, setAudio] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSources(null);
    setChosen(null);
    void (async () => {
      const access = await window.veena?.mediaAccess("screen");
      if (access === "denied" || access === "restricted") {
        toast("error", "Screen recording permission is off for VEENA in System Settings → Privacy & Security.");
      }
      try {
        setSources((await window.veena?.listScreenSources()) ?? []);
      } catch (e) {
        toast("error", `Could not list screens: ${(e as Error).message}`);
        setSources([]);
      }
    })();
  }, [open, toast]);

  const confirm = async () => {
    const src = sources?.find((s) => s.id === chosen);
    if (!src) return;
    setBusy(true);
    try {
      await screen.start(src.id, src.name, audio);
      onClose();
    } catch (e) {
      toast("error", `Screen sharing failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-40 flex items-center justify-center bg-espresso/40 p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div role="dialog" aria-modal="true" aria-label="Choose what to share" className="flex max-h-full w-full max-w-4xl flex-col rounded-2xl bg-white shadow-[var(--shadow-lift)]" initial={{ y: 12 }} animate={{ y: 0 }}>
            <div className="flex items-center justify-between border-b border-cream px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-espresso">Choose a screen or window to share</h2>
                <p className="text-xs text-caramel">VEENA only sees the source you pick. Frames are analysed locally and not saved.</p>
              </div>
              <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close">
                <X size={18} />
              </Button>
            </div>
            <div className="grid min-h-48 grid-cols-2 gap-3 overflow-y-auto p-5 md:grid-cols-3">
              {sources === null && <p className="col-span-full text-sm text-caramel">Looking for screens and windows…</p>}
              {sources?.length === 0 && <p className="col-span-full text-sm text-caramel">No shareable sources found. Check the operating system's screen-recording permission.</p>}
              {sources?.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setChosen(s.id)}
                  onDoubleClick={() => {
                    setChosen(s.id);
                    void confirm();
                  }}
                  className={cn("overflow-hidden rounded-xl border-2 text-left transition-colors", chosen === s.id ? "border-caramel" : "border-cream hover:border-sand")}
                  aria-pressed={chosen === s.id}
                >
                  <div className="aspect-video bg-ivory">{s.thumbnail && <img src={s.thumbnail} alt="" className="h-full w-full object-contain" />}</div>
                  <div className="flex items-center gap-1.5 px-2.5 py-2 text-xs text-bark">
                    {s.kind === "screen" ? <Monitor size={12} /> : <PanelRightOpen size={12} />}
                    <span className="truncate">{s.name}</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4 border-t border-cream px-5 py-4">
              <div className="max-w-sm flex-1">
                <Switch
                  checked={audio}
                  onChange={setAudio}
                  disabled={!appInfo?.systemAudioSupported}
                  label="Also capture system audio"
                  description={appInfo?.systemAudioSupported ? "Transcribes what plays through your speakers." : "System audio capture is available on Windows only."}
                />
              </div>
              <Button variant="ghost" onClick={onClose} className="ml-auto">
                Cancel
              </Button>
              <Button variant="primary" onClick={() => void confirm()} disabled={!chosen || busy}>
                {busy ? "Starting…" : "Share"}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Toasts() {
  const { toasts, dismissToast } = useApp();
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-96 flex-col gap-2" aria-live="assertive">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={cn(
              "pointer-events-auto flex items-start gap-2 rounded-xl border px-4 py-3 text-sm shadow-[var(--shadow-lift)]",
              t.kind === "error" ? "border-bark bg-bark text-white" : t.kind === "warning" ? "border-ginger bg-cream text-espresso" : "border-cream bg-white text-bark",
            )}
            role={t.kind === "error" ? "alert" : "status"}
          >
            <span className="flex-1">{t.text}</span>
            <button type="button" onClick={() => dismissToast(t.id)} aria-label="Dismiss" className="opacity-70 hover:opacity-100">
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
