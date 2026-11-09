import { CatMark, Wordmark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { useState } from "react";
import { Button, Card, Kbd } from "../components/ui";
import { useApp } from "../stores/app";

function UpdateCheck() {
  const [state, setState] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const check = async () => {
    if (!window.veena?.checkForUpdates) return;
    setState("Checking…");
    const u = await window.veena.checkForUpdates();
    setUrl(u.newer ? u.url : null);
    setState(u.error ? `Could not check: ${u.error}` : u.newer ? `VEENA ${u.latest} is available.` : u.latest ? `You have the latest version (${u.current}).` : "No published release yet.");
  };
  return (
    <Card className="mt-4 flex flex-wrap items-center gap-3 p-5 text-sm text-mocha">
      <Button size="sm" onClick={() => void check()}>
        Check for updates
      </Button>
      {state && <span role="status">{state}</span>}
      {url && (
        <Button size="sm" variant="primary" onClick={() => void window.veena?.openExternal(url)}>
          View release
        </Button>
      )}
    </Card>
  );
}

export function About() {
  const { appInfo, status } = useApp();
  return (
    <div className="flex h-full flex-col">
      <TopBar title="About" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-10">
          <div className="flex flex-col items-center text-center">
            <CatMark size={96} mood="idle" />
            <div className="mt-3">
              <Wordmark size="lg" />
            </div>
            <p className="mt-1 text-caramel">Your intelligent conversation companion.</p>
            <p className="mt-2 text-xs text-sand">
              Version {appInfo?.version} · Electron {appInfo?.electron} · {appInfo?.platform}/{appInfo?.arch}
            </p>
          </div>
          <Card className="mt-8 space-y-3 p-5 text-sm leading-relaxed text-mocha">
            <p>VEENA is a local-first desktop copilot. It needs no account, no API key and no subscription: every model runs on this computer through free, open tools.</p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Language and vision: Ollama ({status?.ollama.version ?? "not running"})</li>
              <li>Speech: faster-whisper with Silero VAD</li>
              <li>Documents: sentence-transformers embeddings and FAISS</li>
              <li>Screen text: Tesseract OCR {status?.tesseract ? "" : "(not installed)"}</li>
            </ul>
            <p>
              No telemetry is sent anywhere. VEENA uses the internet only to download the AI runtime and models when you ask it to, and, if allowed in Setup, to check GitHub once a day for a newer
              version number.
            </p>
          </Card>
          <UpdateCheck />
          <Card className="mt-4 p-5 text-sm text-mocha">
            <h3 className="mb-2 font-semibold text-espresso">Keyboard shortcuts</h3>
            <ul className="space-y-1.5">
              <li>
                <Kbd>Ctrl/⌘ Shift Space</Kbd> bring VEENA to the front
              </li>
              <li>
                <Kbd>Ctrl/⌘ Shift M</Kbd> start or stop the microphone
              </li>
              <li>
                <Kbd>Ctrl/⌘ Shift S</Kbd> analyse the shared screen
              </li>
              <li>
                <Kbd>Enter</Kbd> send · <Kbd>Shift Enter</Kbd> new line
              </li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
