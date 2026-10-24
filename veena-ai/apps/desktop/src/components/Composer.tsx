import { ArrowUp, CircleStop, Mic, MicOff, Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useApp } from "../stores/app";
import { useAudio } from "../stores/media";
import { Button, cn, Select } from "./ui";

export const ANSWER_STYLES: [string, string][] = [
  ["auto", "Auto style"],
  ["quick", "Quick Answer"],
  ["detailed", "Detailed Answer"],
  ["deep_dive", "Technical Deep Dive"],
  ["code", "Code Explanation"],
  ["architecture", "Architecture Explanation"],
  ["tutorial", "Step-by-Step Tutorial"],
  ["interview", "Practice Interview Answer"],
];

export function LevelMeter({ level, active }: { level: number; active: boolean }) {
  const bars = 5;
  const lit = Math.min(bars, Math.round(Math.sqrt(level) * 14));
  return (
    <span className="flex h-4 items-end gap-0.5" aria-hidden>
      {Array.from({ length: bars }, (_, i) => (
        <span key={i} className={cn("w-1 rounded-sm transition-all", active && i < lit ? "bg-caramel" : "bg-cream")} style={{ height: `${30 + i * 17}%` }} />
      ))}
    </span>
  );
}

/** Microphone control: start/pause/stop with a visible recording state. */
export function MicControl({ sessionMode = "conversation" as const }: { sessionMode?: "conversation" | "screen" | "meeting" | "interview" }) {
  const { ensureSession, toast } = useApp();
  const audio = useAudio();
  const state = audio.state.mic;
  const active = audio.isActive("mic");
  const label =
    state === "loading_model"
      ? "Loading speech model…"
      : state === "connecting"
        ? "Connecting…"
        : state === "reconnecting"
          ? "Reconnecting…"
          : state === "paused"
            ? "Paused"
            : state === "listening"
              ? "Listening"
              : "Microphone off";

  const start = async () => {
    try {
      const s = await ensureSession(sessionMode);
      await audio.start("mic", s.id);
    } catch (e) {
      toast("error", (e as Error).message);
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      {!active ? (
        <Button size="sm" variant="secondary" onClick={() => void start()} aria-label="Start microphone">
          <Mic size={15} /> Listen
        </Button>
      ) : (
        <>
          <span className={cn("flex h-8 items-center gap-2 rounded-xl border px-2.5 text-xs font-medium", state === "listening" ? "border-caramel bg-cream text-bark" : "border-cream bg-ivory text-mocha")} role="status">
            <span className={cn("h-2 w-2 rounded-full", state === "listening" ? "animate-pulse bg-bark" : "border border-mocha")} aria-hidden />
            {label}
            <LevelMeter level={audio.level} active={state === "listening"} />
          </span>
          {state === "paused" ? (
            <Button size="icon" variant="ghost" onClick={audio.resume} aria-label="Resume microphone">
              <Play size={15} />
            </Button>
          ) : (
            <Button size="icon" variant="ghost" onClick={audio.pause} aria-label="Pause microphone">
              <Pause size={15} />
            </Button>
          )}
          <Button size="icon" variant="ghost" onClick={() => void audio.stop("mic")} aria-label="Stop microphone">
            <MicOff size={15} />
          </Button>
        </>
      )}
    </div>
  );
}

export function Composer({
  onSend,
  placeholder = "Ask anything… (Enter to send, Shift+Enter for a new line)",
  big,
  showMic = true,
  sessionMode = "conversation",
}: {
  onSend: (text: string, style: string | null) => void;
  placeholder?: string;
  big?: boolean;
  showMic?: boolean;
  sessionMode?: "conversation" | "screen" | "meeting" | "interview";
}) {
  const [text, setText] = useState("");
  const [style, setStyle] = useState("auto");
  const { live, cancel, settings } = useApp();
  const ref = useRef<HTMLTextAreaElement>(null);
  const busy = !!live && !live.done && !live.error;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(220, el.scrollHeight) + "px";
  }, [text]);

  const send = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t, style === "auto" ? null : style);
    setText("");
  };

  return (
    <div className={cn("rounded-2xl border border-cream bg-white p-2 shadow-[var(--shadow-lift)] focus-within:border-sand", big && "p-3")}>
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
        rows={big ? 3 : 1}
        aria-label="Message"
        className={cn("w-full resize-none bg-transparent px-2 py-1.5 text-bark placeholder:text-sand focus:outline-none", big ? "text-base" : "text-sm")}
      />
      <div className="mt-1 flex items-center gap-2">
        {showMic && <MicControl sessionMode={sessionMode} />}
        <Select value={style} onChange={(e) => setStyle(e.target.value)} className="h-8 w-auto rounded-lg text-xs" aria-label="Answer style">
          {ANSWER_STYLES.map(([v, l]) => (
            <option key={v} value={v}>
              {v === "auto" && settings ? `Auto (${settings.answer_style})` : l}
            </option>
          ))}
        </Select>
        <div className="ml-auto">
          {busy ? (
            <Button size="sm" variant="secondary" onClick={() => void cancel()} aria-label="Stop generating">
              <CircleStop size={15} /> Stop
            </Button>
          ) : (
            <Button size="sm" variant="primary" onClick={send} disabled={!text.trim()} aria-label="Send">
              <ArrowUp size={15} /> Send
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
