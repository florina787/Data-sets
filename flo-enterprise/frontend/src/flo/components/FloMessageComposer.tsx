import { ArrowUp, Square } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { cn } from "@/components/ui";

export type ComposerHandle = { focus: () => void; setText: (t: string) => void };

export const FloMessageComposer = forwardRef<ComposerHandle, {
  onSend: (text: string) => void; onCancel?: () => void; busy?: boolean; size?: "hero" | "dock"; personaLabel?: string; placeholder?: string;
}>(({ onSend, onCancel, busy, size = "dock", personaLabel, placeholder }, ref) => {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => ({ focus: () => ta.current?.focus(), setText: (t) => { setText(t); requestAnimationFrame(() => ta.current?.focus()); } }));
  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(size === "hero" ? 220 : 160, el.scrollHeight)}px`;
  }, [text, size]);
  const submit = () => {
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); submit(); }}
      className={cn("rounded-2xl border bg-card shadow-lg transition-colors focus-within:border-gold/70", size === "hero" ? "border-transparent bg-[#111a2e] p-3 sm:p-4" : "border-line p-2")}>
      <label htmlFor={`flo-input-${size}`} className="sr-only">Message FLO</label>
      <textarea id={`flo-input-${size}`} ref={ta} value={text} onChange={(e) => setText(e.target.value)} rows={size === "hero" ? 2 : 1} maxLength={4000}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
        placeholder={placeholder ?? "Ask FLO about investments, portfolios, clients, business performance or growth strategy…"}
        className={cn("w-full resize-none bg-transparent text-ink placeholder:text-muted/80 focus:outline-none", size === "hero" ? "px-1 text-base sm:text-lg" : "px-2 py-1 text-sm")} />
      <div className="mt-1 flex items-center gap-2">
        {personaLabel && <span className="truncate text-[11px] text-muted">Persona: <span className="text-ink/80">{personaLabel}</span></span>}
        <span className="ml-auto hidden text-[11px] text-muted sm:inline">Enter to send · Shift+Enter for a new line</span>
        {busy && onCancel ? (
          <button type="button" onClick={onCancel} aria-label="Stop analysis"
            className="grid h-9 w-9 place-items-center rounded-full border border-line text-ink hover:border-crit hover:text-crit"><Square className="h-3.5 w-3.5" /></button>
        ) : (
          <button type="submit" disabled={!text.trim() || busy} aria-label="Send to FLO"
            className="grid h-9 w-9 place-items-center rounded-full bg-gold text-[#0B1220] transition-opacity disabled:opacity-40"><ArrowUp className="h-4 w-4" /></button>
        )}
      </div>
    </form>
  );
});
FloMessageComposer.displayName = "FloMessageComposer";
