import { Bug, Camera, Code2, Crop, FileText, Monitor, Network, Radar, ScanEye, Square } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { CatMark } from "../components/CatMark";
import { Composer } from "../components/Composer";
import { MessageList } from "../components/Conversation";
import { ContextPanel, TopBar } from "../components/Shell";
import { Badge, Button, Card, cn, Section, Switch } from "../components/ui";
import type { Region } from "../services/screen";
import { useApp } from "../stores/app";
import { useScreen } from "../stores/media";
import { DetectedQuestions } from "./Workspace";

const ACTIONS = [
  { id: "explain_code", label: "Explain Code", icon: Code2, q: "Explain the code on my screen." },
  { id: "find_errors", label: "Find Errors", icon: Bug, q: "Identify the bug or error on my screen and how to fix it." },
  { id: "architecture", label: "Explain Architecture", icon: Network, q: "Explain the architecture shown on my screen." },
  { id: "summarize", label: "Summarize Screen", icon: FileText, q: "Summarise what is on my screen." },
];

function Preview() {
  const screen = useScreen();
  const ref = useRef<HTMLVideoElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [selecting, setSelecting] = useState(false);
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);

  useEffect(() => {
    if (ref.current && screen.stream) {
      ref.current.srcObject = screen.stream;
      void ref.current.play().catch(() => undefined);
    }
  }, [screen.stream]);

  // Map pointer positions to fractions of the actual video content (object-contain letterboxing).
  const toFrac = (e: RPointerEvent) => {
    const v = ref.current!;
    const r = v.getBoundingClientRect();
    const vr = v.videoWidth / v.videoHeight || 16 / 9;
    const br = r.width / r.height;
    const w = vr > br ? r.width : r.height * vr;
    const h = vr > br ? r.width / vr : r.height;
    const ox = r.left + (r.width - w) / 2;
    const oy = r.top + (r.height - h) / 2;
    return { x: Math.min(1, Math.max(0, (e.clientX - ox) / w)), y: Math.min(1, Math.max(0, (e.clientY - oy) / h)), ox: ox - r.left, oy: oy - r.top, w, h };
  };

  const region = screen.region;
  const overlay = (() => {
    const v = ref.current;
    if (!v) return null;
    const r: Region | null = drag
      ? { x: Math.min(drag.x0, drag.x1), y: Math.min(drag.y0, drag.y1), w: Math.abs(drag.x1 - drag.x0), h: Math.abs(drag.y1 - drag.y0) }
      : region;
    if (!r) return null;
    const rect = v.getBoundingClientRect();
    const vr = v.videoWidth / v.videoHeight || 16 / 9;
    const br = rect.width / rect.height;
    const w = vr > br ? rect.width : rect.height * vr;
    const h = vr > br ? rect.width / vr : rect.height;
    const ox = (rect.width - w) / 2;
    const oy = (rect.height - h) / 2;
    return { left: ox + r.x * w, top: oy + r.y * h, width: r.w * w, height: r.h * h };
  })();

  return (
    <div className="relative">
      <div
        ref={box}
        className={cn("relative aspect-video overflow-hidden rounded-xl bg-espresso", selecting && "cursor-crosshair")}
        onPointerDown={(e) => {
          if (!selecting) return;
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
          const f = toFrac(e);
          setDrag({ x0: f.x, y0: f.y, x1: f.x, y1: f.y });
        }}
        onPointerMove={(e) => {
          if (!drag) return;
          const f = toFrac(e);
          setDrag({ ...drag, x1: f.x, y1: f.y });
        }}
        onPointerUp={() => {
          if (!drag) return;
          const r = { x: Math.min(drag.x0, drag.x1), y: Math.min(drag.y0, drag.y1), w: Math.abs(drag.x1 - drag.x0), h: Math.abs(drag.y1 - drag.y0) };
          screen.setRegion(r.w > 0.02 && r.h > 0.02 ? r : null);
          setDrag(null);
          setSelecting(false);
        }}
      >
        <video ref={ref} muted playsInline className="h-full w-full object-contain" aria-label="Live preview of the shared screen" />
        {overlay && <div className="pointer-events-none absolute border-2 border-cream bg-white/10 shadow-[0_0_0_9999px_rgb(44_26_18/0.45)]" style={overlay} />}
        <span className="absolute top-2 left-2 inline-flex items-center gap-1.5 rounded-full bg-bark/90 px-2.5 py-1 text-[11px] font-medium text-white">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cream" /> Sharing {screen.sourceName}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Button size="sm" variant={selecting ? "subtle" : "ghost"} onClick={() => setSelecting(!selecting)}>
          <Crop size={14} /> {selecting ? "Drag on the preview…" : "Select region"}
        </Button>
        {region && (
          <Button size="sm" variant="ghost" onClick={() => screen.setRegion(null)}>
            Clear region
          </Button>
        )}
        {region && <Badge tone="outline">Analysing selected region only</Badge>}
      </div>
    </div>
  );
}

export function ScreenPage({ onShare }: { onShare: () => void }) {
  const screen = useScreen();
  const { ask, ensureSession, currentSession, settings, updateSettings, setPage, toast } = useApp();
  const [shot, setShot] = useState<string | null>(null);

  useEffect(() => {
    if (currentSession?.mode !== "screen") void ensureSession("screen");
  }, [currentSession?.mode, ensureSession]);

  const takeShot = () => {
    try {
      setShot(screen.capture());
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title="Screen Intelligence" subtitle="Share an explicitly selected screen or window, then ask about what is visible" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-4xl space-y-6 px-6 py-6">
            {!screen.sharing ? (
              <Card className="flex flex-col items-center p-10 text-center">
                <CatMark size={72} mood="idle" />
                <h2 className="mt-4 text-lg font-semibold text-espresso">Nothing is being shared</h2>
                <p className="mt-1 max-w-md text-sm text-mocha">Choose a screen or a single window. VEENA never selects one for you, shows an indicator while sharing, and processes frames locally without saving them.</p>
                <Button variant="primary" size="lg" className="mt-6" onClick={onShare}>
                  <Monitor size={18} /> Choose screen or window
                </Button>
              </Card>
            ) : (
              <Card className="p-4">
                <Preview />
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="secondary" onClick={takeShot}>
                    <Camera size={15} /> Screenshot
                  </Button>
                  {ACTIONS.map((a) => (
                    <Button key={a.id} variant="secondary" disabled={screen.analyzing} onClick={() => void screen.analyze(a.id, a.q)}>
                      <a.icon size={15} /> {a.label}
                    </Button>
                  ))}
                  <Button variant="danger" className="ml-auto" onClick={() => screen.stop()}>
                    <Square size={14} /> Stop Sharing
                  </Button>
                </div>
                {shot && (
                  <div className="mt-4">
                    <div className="mb-1 flex items-center justify-between text-xs text-caramel">
                      Screenshot (kept in memory only)
                      <button type="button" className="underline" onClick={() => setShot(null)}>
                        Discard
                      </button>
                    </div>
                    <img src={shot} alt="Captured frame" className="max-h-64 rounded-lg border border-cream" />
                  </div>
                )}
              </Card>
            )}

            <MessageList />
          </div>
        </div>
        <div className="border-t border-cream bg-warm px-6 py-4">
          <div className="mx-auto max-w-4xl">
            <Composer
              sessionMode="screen"
              placeholder={screen.sharing ? "Ask about your screen… e.g. Why is this failing?" : "Share a screen to ask about it, or just type a question"}
              onSend={async (text, style) => {
                if (screen.sharing) await screen.analyze("ask", text);
                else await ask({ text, answer_style: style, mode: "screen" });
              }}
            />
          </div>
        </div>
      </div>
      <ContextPanel>
        <Section title="Continuous understanding">
          <Switch
            checked={screen.continuous}
            onChange={(v) => screen.setContinuous(v)}
            disabled={!screen.sharing}
            label="Analyse changes automatically"
            description={`Samples a frame every ${settings?.continuous_interval_s ?? 5}s, skips unchanged frames, and pauses when VEENA is minimised.`}
          />
          {screen.pausedReason && (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-bark">
              <Radar size={13} className="mt-0.5 shrink-0" /> {screen.pausedReason}
            </p>
          )}
        </Section>
        <Section title="Privacy">
          <div className="space-y-3">
            <Switch checked={settings?.redact_screens ?? true} onChange={(v) => void updateSettings({ redact_screens: v })} label="Redact secrets before analysis" description="Masks passwords, tokens and keys found by OCR. Best effort." />
            <Switch checked={settings?.pause_on_sensitive ?? true} onChange={(v) => void updateSettings({ pause_on_sensitive: v })} label="Pause on sensitive content" description="Continuous mode stops when a password field is visible." />
          </div>
        </Section>
        <Section title="Spoken questions">
          <DetectedQuestions />
        </Section>
        <button type="button" onClick={() => setPage("settings")} className="flex items-center gap-1 text-xs text-caramel underline">
          <ScanEye size={12} /> Vision model settings
        </button>
      </ContextPanel>
    </div>
  );
}
