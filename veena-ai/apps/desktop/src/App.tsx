import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { CatMark, Wordmark } from "./components/CatMark";
import { Sidebar, SourcePicker, Toasts } from "./components/Shell";
import { Button } from "./components/ui";
import { About } from "./pages/About";
import { Analytics } from "./pages/Analytics";
import { Interview } from "./pages/Interview";
import { Knowledge } from "./pages/Knowledge";
import { Meeting } from "./pages/Meeting";
import { ScreenPage } from "./pages/Screen";
import { Settings } from "./pages/Settings";
import { Setup } from "./pages/Setup";
import { Welcome } from "./pages/Welcome";
import { Workspace } from "./pages/Workspace";
import { useApp } from "./stores/app";
import { useAudio, useScreen } from "./stores/media";

function Splash() {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-warm" role="status" aria-label="Starting VEENA">
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}>
        <CatMark size={120} mood="thinking" />
      </motion.div>
      <div className="mt-4">
        <Wordmark size="lg" />
      </div>
      <p className="mt-2 text-sm text-caramel">Starting the local AI service…</p>
    </div>
  );
}

function BackendFailed({ error }: { error?: string }) {
  const [log, setLog] = useState<string | null>(null);
  return (
    <div className="flex h-full flex-col items-center justify-center bg-warm px-6 text-center">
      <CatMark size={96} />
      <h1 className="mt-4 text-xl font-semibold text-espresso">VEENA's local service did not start</h1>
      <p className="mt-2 max-w-lg text-sm text-mocha">{error ?? "Unknown error."}</p>
      <p className="mt-2 max-w-lg text-xs text-caramel">
        Check that Python 3.11+ and the backend dependencies are installed (see the README), or set VEENA_PYTHON to the interpreter to use.
      </p>
      <div className="mt-6 flex gap-2">
        <Button variant="primary" onClick={() => void window.veena?.restartBackend()}>
          Try again
        </Button>
        <Button variant="ghost" onClick={async () => setLog((await window.veena?.backendLog()) ?? "")}>
          Show log
        </Button>
      </div>
      {log !== null && <pre className="mt-4 max-h-72 w-full max-w-3xl overflow-auto rounded-xl bg-espresso p-3 text-left font-mono text-[11px] text-cream">{log || "(empty)"}</pre>}
    </div>
  );
}

export default function App() {
  const { init, backend, page, setPage, ensureSession, toast } = useApp();
  const [picker, setPicker] = useState(false);

  useEffect(() => {
    void init();
  }, [init]);

  useEffect(() => {
    if (!window.veena) return;
    return window.veena.onShortcut(async (action) => {
      const audio = useAudio.getState();
      const screen = useScreen.getState();
      if (action === "toggle-mic") {
        if (audio.isActive("mic")) await audio.stop("mic");
        else {
          const s = await ensureSession(useApp.getState().currentSession?.mode ?? "conversation");
          await audio.start("mic", s.id);
        }
      } else if (action === "capture-screen") {
        if (screen.sharing) await screen.analyze("ask", "What is on my screen right now?");
        else toast("info", "Share a screen first (Screen Intelligence).");
      }
    });
  }, [ensureSession, toast]);

  if (!backend || backend.status === "starting" || backend.status === "restarting") return <Splash />;
  if (backend.status === "failed") return <BackendFailed error={backend.error} />;
  if (page === "setup") return <Setup />;

  const openPicker = () => {
    setPage(page === "meeting" ? "meeting" : "screen");
    setPicker(true);
  };

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar />
      <main className="min-w-0 flex-1">
        {page === "welcome" && <Welcome onShare={openPicker} />}
        {page === "workspace" && <Workspace />}
        {page === "screen" && <ScreenPage onShare={openPicker} />}
        {page === "interview" && <Interview />}
        {page === "knowledge" && <Knowledge />}
        {page === "meeting" && <Meeting onShare={openPicker} />}
        {page === "analytics" && <Analytics />}
        {page === "settings" && <Settings />}
        {page === "about" && <About />}
      </main>
      <SourcePicker open={picker} onClose={() => setPicker(false)} />
      <Toasts />
    </div>
  );
}
