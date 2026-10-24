import { CatMark, Wordmark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { Card, Kbd } from "../components/ui";
import { useApp } from "../stores/app";

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
            <p>No telemetry is sent anywhere. Model downloads are the only network traffic, and only when you start them.</p>
          </Card>
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
