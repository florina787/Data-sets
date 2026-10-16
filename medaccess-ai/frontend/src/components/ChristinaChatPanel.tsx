import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useApp } from "../hooks/AppContext";
import { useVoice } from "../hooks/useVoice";
import { endpoints, type AvatarState, type ChatReply } from "../services/api";
import { ChristinaAvatar } from "./ChristinaAvatar";
import { AvailabilityBadge, Pill } from "./ui";

interface Msg {
  role: "user" | "assistant";
  text: string;
  reply?: ChatReply;
}

export function VoiceControl({ voice, onTranscript }: { voice: ReturnType<typeof useVoice>; onTranscript: (t: string) => void }) {
  const { voiceEnabled, setVoiceEnabled } = useApp();
  const [showDisclosure, setShowDisclosure] = useState(false);
  if (!voiceEnabled) {
    return (
      <div className="text-xs">
        {!showDisclosure ? (
          <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setShowDisclosure(true)} aria-label="Enable voice">🎙 Enable voice</button>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-2">
            <p>Voice uses your browser's speech features. Some browsers send audio to their vendor's cloud speech service. Please avoid sharing health details by voice. The microphone is only used when you press the mic button.</p>
            <div className="mt-1 flex gap-2">
              <button className="btn-primary px-2 py-1 text-xs" onClick={() => { setVoiceEnabled(true); setShowDisclosure(false); void endpoints.setConsent("voice", true).catch(() => undefined); }}>I understand — enable</button>
              <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setShowDisclosure(false)}>No thanks</button>
            </div>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs" role="group" aria-label="Voice controls">
      <button className={`btn-ghost px-2 py-1 text-xs ${voice.listening ? "border-danger text-danger" : ""}`} disabled={!voice.sttSupported || voice.listening}
        onClick={() => voice.listenOnce(onTranscript)} aria-label="Speak a message">{voice.listening ? "● Listening…" : "🎙 Speak"}</button>
      <button className="btn-ghost px-2 py-1 text-xs" onClick={() => voice.setMuted(!voice.muted)} aria-pressed={voice.muted}>{voice.muted ? "🔇 Unmute" : "🔊 Mute"}</button>
      <button className="btn-ghost px-2 py-1 text-xs" onClick={voice.replay} disabled={!voice.ttsSupported}>↻ Replay</button>
      <label className="flex items-center gap-1">Speed
        <select className="rounded border border-slate-300 px-1 py-0.5" value={voice.rate} onChange={(e) => voice.setRate(Number(e.target.value))}>
          {[0.8, 1, 1.2, 1.4].map((r) => <option key={r} value={r}>{r}×</option>)}
        </select>
      </label>
      <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setVoiceEnabled(false)}>Disable</button>
      {voice.error && <span className="text-danger">{voice.error}</span>}
    </div>
  );
}

export function ChristinaChatPanel({ tall = false }: { tall?: boolean }) {
  const { reducedMotion, setLastSearch, scenario, voiceEnabled } = useApp();
  const voice = useVoice();
  const nav = useNavigate();
  const [session, setSession] = useState<string | undefined>();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [avatar, setAvatar] = useState<AvatarState>("idle");
  const [quick, setQuick] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    endpoints.greet().then((r) => { setSession(r.session_id); setMsgs([{ role: "assistant", text: r.reply, reply: r }]); setAvatar("greeting"); setQuick(r.quick_replies); })
      .catch(() => setMsgs([{ role: "assistant", text: "I'm having trouble connecting right now. Please try again shortly." }]));
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView?.({ block: "nearest" }); }, [msgs]);

  const send = async (text: string) => {
    const t = text.trim();
    if (!t || busy) return;
    setMsgs((m) => [...m, { role: "user", text: t }]);
    setInput(""); setBusy(true); setAvatar("thinking"); setQuick([]);
    try {
      const r = await endpoints.chat(t, session, scenario);
      setSession(r.session_id);
      setMsgs((m) => [...m, { role: "assistant", text: r.reply, reply: r }]);
      setAvatar(r.avatar_state);
      setQuick(r.quick_replies);
      if (r.workflow && r.workflow.recommendations) setLastSearch(r.workflow);
      if (voiceEnabled) voice.speak(r.reply);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: `Sorry — ${e instanceof Error ? e.message : "something went wrong"}. Nothing was booked or shared.` }]);
      setAvatar("warning");
    } finally { setBusy(false); }
  };

  return (
    <div className={`flex flex-col ${tall ? "h-[calc(100vh-10rem)] min-h-[520px]" : "h-[600px]"}`}>
      <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
        <ChristinaAvatar state={avatar} size={tall ? 120 : 84} reducedMotion={reducedMotion} />
        <div className="min-w-0">
          <div className="font-bold text-ink">Dr. Christina</div>
          <div className="text-xs font-medium text-teal">AI Healthcare Access Assistant</div>
          <div className="mt-1 text-[11px] text-slate-500">Christina is a virtual AI assistant, not a licensed physician.</div>
          <div className="mt-1"><VoiceControl voice={voice} onTranscript={(t) => void send(t)} /></div>
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto py-3" aria-live="polite" aria-label="Conversation with Christina">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm ${m.role === "user" ? "bg-brand text-white" : m.reply?.avatar_state === "warning" ? "border-2 border-warn bg-amber-50 text-ink" : "bg-canvas text-ink"}`}>
              <p className="whitespace-pre-wrap">{m.text}</p>
              {m.reply?.warnings?.map((w, j) => <p key={j} className="mt-1 text-xs font-semibold text-[#9A4500]">⚠ {w}</p>)}
              {!!m.reply?.citations?.length && (
                <ol className="mt-2 space-y-0.5 border-t border-slate-200 pt-1 text-[11px] text-slate-600">
                  {m.reply.citations.map((c, j) => (
                    <li key={j}>[{j + 1}] {c.title} — {c.provider}{c.stale && <Pill tone="warn">review overdue</Pill>}{c.access_classification === "synthetic_demo" && <Pill>fictional</Pill>}</li>
                  ))}
                </ol>
              )}
              {m.reply?.workflow?.recommendations?.length ? (
                <div className="mt-2 space-y-1 border-t border-slate-200 pt-2">
                  {m.reply.workflow.recommendations.slice(0, 3).map((r) => (
                    <div key={r.slot_id} className="flex flex-wrap items-center justify-between gap-1 text-xs">
                      <span className="font-medium">{r.facility_name} · {r.days_until} d · {r.straight_km.toFixed(1)} km</span>
                      <AvailabilityBadge status={r.verification_status} simulated={r.is_synthetic} />
                    </div>
                  ))}
                  <button className="mt-1 text-xs font-semibold text-brand underline" onClick={() => { setLastSearch(m.reply!.workflow!); nav("/search"); }}>View full results, map and agent activity →</button>
                </div>
              ) : null}
              {m.reply?.mode && m.reply.mode !== "deterministic" && <div className="mt-1 text-[10px] text-slate-400">reply phrased by LLM ({m.reply.mode})</div>}
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-slate-500" role="status">Christina is checking with the agents…</div>}
        <div ref={endRef} />
      </div>
      {quick.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pb-2">
          {quick.map((q) => <button key={q} className="rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100" onClick={() => void send(q)}>{q}</button>)}
        </div>
      )}
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
        <label htmlFor="chat-input" className="sr-only">Message Christina</label>
        <input id="chat-input" className="input" value={input} maxLength={1000} placeholder="e.g. I need an MRI near Toronto" onChange={(e) => setInput(e.target.value)} disabled={busy} />
        <button className="btn-primary" disabled={busy || !input.trim()}>Send</button>
      </form>
      <p className="mt-1 text-[10px] text-slate-500">Don't share names, health card numbers or symptoms details. In an emergency call 911.</p>
    </div>
  );
}
