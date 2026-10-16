import { useCallback, useEffect, useRef, useState } from "react";

// Browser-native speech only. Nothing is recorded continuously: recognition runs for a single
// utterance after an explicit click, and only if the user enabled voice and granted mic permission.
type SR = { start: () => void; stop: () => void; lang: string; interimResults: boolean; onresult: ((e: any) => void) | null; onerror: ((e: any) => void) | null; onend: (() => void) | null };

export function useVoice(lang = "en-CA") {
  const w = typeof window !== "undefined" ? (window as any) : {};
  const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition;
  const ttsSupported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [rate, setRate] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SR | null>(null);
  const lastSpoken = useRef<string>("");

  useEffect(() => () => {
    recRef.current?.stop();
    if (ttsSupported) window.speechSynthesis.cancel();
  }, [ttsSupported]);

  const speak = useCallback((text: string) => {
    lastSpoken.current = text;
    if (!ttsSupported || muted) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = rate;
    window.speechSynthesis.speak(u);
  }, [ttsSupported, muted, lang, rate]);

  const replay = useCallback(() => speak(lastSpoken.current), [speak]);

  const listenOnce = useCallback((onText: (t: string) => void) => {
    if (!Recognition) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }
    const rec: SR = new Recognition();
    rec.lang = lang;
    rec.interimResults = false;
    rec.onresult = (e: any) => onText(e.results[0][0].transcript);
    rec.onerror = (e: any) => setError(e.error === "not-allowed" ? "Microphone permission was denied." : String(e.error));
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setError(null);
    setListening(true);
    rec.start();
  }, [Recognition, lang]);

  return { sttSupported: !!Recognition, ttsSupported, listening, listenOnce, speak, replay, muted, setMuted, rate, setRate, error };
}
