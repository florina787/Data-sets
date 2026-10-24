import { create } from "zustand";
import type { Message } from "../services/api";
import { AudioCapture, type AudioEvent, type AudioSource, type CaptureState, listInputDevices } from "../services/audio";
import { captureFrame, frameHash, hamming, type Region, startShare, stopShare } from "../services/screen";
import { useApp } from "./app";

// ---------------------------------------------------------------- audio

type FinalListener = (text: string, source: AudioSource) => void;
const finalListeners = new Set<FinalListener>();

/** Pages (e.g. interview practice) can receive final transcripts directly. */
export function onFinalTranscript(fn: FinalListener): () => void {
  finalListeners.add(fn);
  return () => finalListeners.delete(fn);
}

interface AudioStore {
  captures: Partial<Record<AudioSource, AudioCapture>>;
  state: Partial<Record<AudioSource, CaptureState>>;
  detail: string | null;
  level: number;
  devices: MediaDeviceInfo[];
  deviceId: string | undefined;
  autoAnswer: boolean;
  isActive(source?: AudioSource): boolean;
  refreshDevices(): Promise<void>;
  setDevice(id: string | undefined): void;
  setAutoAnswer(v: boolean): void;
  start(source: AudioSource, sessionId: string, stream?: MediaStream): Promise<void>;
  pause(): void;
  resume(): void;
  stop(source?: AudioSource): Promise<void>;
}

export const useAudio = create<AudioStore>((set, get) => ({
  captures: {},
  state: {},
  detail: null,
  level: 0,
  devices: [],
  deviceId: undefined,
  autoAnswer: true,

  isActive(source) {
    const st = get().state;
    const active = (s?: CaptureState) => !!s && s !== "stopped" && s !== "error";
    return source ? active(st[source]) : active(st.mic) || active(st.system);
  },

  async refreshDevices() {
    try {
      set({ devices: await listInputDevices() });
    } catch {
      set({ devices: [] });
    }
  },

  setDevice: (deviceId) => set({ deviceId }),
  setAutoAnswer: (autoAnswer) => set({ autoAnswer }),

  async start(source, sessionId, stream) {
    const app = useApp.getState();
    if (get().captures[source]) await get().stop(source);
    if (source === "mic") {
      const access = await window.veena?.mediaAccess("microphone");
      if (access && access !== "granted") {
        app.toast("error", "Microphone access is blocked in system settings.");
        return;
      }
    }
    const api = app.api!;
    const onEvent = (ev: AudioEvent) => handleAudioEvent(ev, source, sessionId);
    const cap = new AudioCapture(
      api.wsUrl,
      api.token,
      sessionId,
      source,
      {
        onEvent,
        onLevel: (level) => set({ level }),
        onState: (st, detail) => {
          set((s) => ({ state: { ...s.state, [source]: st }, detail: detail ?? s.detail }));
          if (detail && (st === "error" || st === "reconnecting")) app.toast(st === "error" ? "error" : "warning", detail);
          if (st === "stopped" || st === "error") {
            set((s) => {
              const captures = { ...s.captures };
              if (captures[source] === cap) delete captures[source];
              return { captures, level: 0 };
            });
          }
        },
      },
      source === "mic" ? get().deviceId : undefined,
      stream,
    );
    set((s) => ({ captures: { ...s.captures, [source]: cap } }));
    try {
      await cap.start();
    } catch (e) {
      app.toast("error", `Could not start ${source === "mic" ? "microphone" : "system audio"}: ${(e as Error).message}`);
      await cap.stop();
    }
  },

  pause() {
    Object.values(get().captures).forEach((c) => c?.pause());
  },

  resume() {
    Object.values(get().captures).forEach((c) => c?.resume());
  },

  async stop(source) {
    const entries = Object.entries(get().captures) as [AudioSource, AudioCapture][];
    for (const [src, cap] of entries) {
      if (!source || src === source) await cap.stop();
    }
  },
}));

function handleAudioEvent(ev: AudioEvent, source: AudioSource, sessionId: string) {
  const app = useApp.getState();
  const key = `${source}:${String(ev.utterance_id)}`;
  switch (ev.type) {
    case "partial":
      if (ev.text) app.setPartial(key, { utterance_id: Number(ev.utterance_id), text: String(ev.text), source });
      break;
    case "discard":
      app.setPartial(key, null);
      break;
    case "final": {
      app.setPartial(key, null);
      const text = String(ev.text ?? "");
      if (!text) break;
      const msg: Message = {
        id: Number(ev.message_id),
        session_id: sessionId,
        role: "transcript",
        content: text,
        intent: null,
        answer_style: null,
        model: null,
        citations: [],
        meta: { source, start_s: ev.start_s, end_s: ev.end_s, latency_ms: ev.latency_ms },
        created_at: new Date().toISOString(),
      };
      app.appendTranscript(msg);
      finalListeners.forEach((fn) => fn(text, source));
      break;
    }
    case "question": {
      const q = {
        text: String(ev.text),
        intent: String(ev.intent),
        confidence: Number(ev.confidence),
        answer_mode: String(ev.answer_mode),
        context_ref: (ev.context_ref as string) ?? null,
        timestamp: Number(ev.timestamp),
        source,
      };
      app.pushQuestion(q);
      const s = app.currentSession;
      const audio = useAudio.getState();
      // Auto-answer in conversation and screen sessions only; meetings and
      // practice interviews keep the user in control.
      if (audio.autoAnswer && app.settings?.auto_answer_questions && s?.id === sessionId && (s.mode === "conversation" || s.mode === "screen")) {
        const screen = useScreen.getState();
        const transcript = app.messages.filter((m) => m.role === "transcript").slice(-12).map((m) => m.content);
        const image = s.mode === "screen" && screen.sharing ? safeCapture() : null;
        void app.ask({ text: q.text, source: "speech", intent: q.intent, transcript_context: transcript, image_b64: image, mode: s.mode });
      }
      break;
    }
    case "error":
      app.toast("error", `Audio: ${String(ev.message)}`);
      break;
  }
}

function safeCapture(): string | null {
  try {
    return useScreen.getState().capture();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------- screen

interface ScreenStore {
  stream: MediaStream | null;
  video: HTMLVideoElement | null;
  sourceName: string | null;
  sharing: boolean;
  withAudio: boolean;
  region: Region | null;
  continuous: boolean;
  pausedReason: string | null;
  analyzing: boolean;
  lastHash: bigint | null;
  lastFrame: string | null;
  timer: number | null;
  start(sourceId: string, sourceName: string, withAudio: boolean): Promise<void>;
  stop(reason?: string): void;
  setRegion(r: Region | null): void;
  capture(): string;
  analyze(action: string, question: string, opts?: { continuous?: boolean }): Promise<void>;
  setContinuous(on: boolean): void;
}

export const useScreen = create<ScreenStore>((set, get) => ({
  stream: null,
  video: null,
  sourceName: null,
  sharing: false,
  withAudio: false,
  region: null,
  continuous: false,
  pausedReason: null,
  analyzing: false,
  lastHash: null,
  lastFrame: null,
  timer: null,

  async start(sourceId, sourceName, withAudio) {
    get().stop();
    const stream = await startShare(sourceId, withAudio);
    const video = document.createElement("video");
    video.muted = true;
    video.srcObject = stream;
    await video.play().catch(() => undefined);
    stream.getVideoTracks()[0]?.addEventListener("ended", () => get().stop("Screen sharing ended (stopped by the system or permission revoked)."));
    set({ stream, video, sourceName, sharing: true, withAudio, region: null, pausedReason: null, lastHash: null });
    const app = useApp.getState();
    if (withAudio && stream.getAudioTracks().length) {
      const session = await app.ensureSession("screen");
      await useAudio.getState().start("system", session.id, stream);
    }
  },

  stop(reason) {
    const { stream, timer } = get();
    if (timer) window.clearInterval(timer);
    if (useAudio.getState().captures.system) void useAudio.getState().stop("system");
    stopShare(stream);
    const wasSharing = get().sharing;
    set({ stream: null, video: null, sharing: false, continuous: false, timer: null, sourceName: null, region: null, lastHash: null });
    if (wasSharing && reason) useApp.getState().toast("warning", reason);
  },

  setRegion: (region) => set({ region }),

  capture() {
    const v = get().video;
    if (!v) throw new Error("Screen sharing is not active.");
    const frame = captureFrame(v, get().region);
    set({ lastFrame: frame });
    return frame;
  },

  async analyze(action, question, opts) {
    const app = useApp.getState();
    if (!get().sharing) {
      app.toast("warning", "Share a screen or window first.");
      return;
    }
    set({ analyzing: true });
    try {
      const image = get().capture();
      const transcript = app.messages.filter((m) => m.role === "transcript").slice(-12).map((m) => m.content);
      const session = await app.ensureSession("screen");
      await app.ask({
        session_id: session.id,
        text: question,
        source: "screen",
        mode: "screen",
        image_b64: image,
        screen_action: action,
        continuous: !!opts?.continuous,
        transcript_context: transcript,
      });
      if (opts?.continuous && app.live?.error && /sensitive/i.test(app.live.error)) {
        get().setContinuous(false);
        set({ pausedReason: app.live.error });
      }
    } catch (e) {
      app.toast("error", (e as Error).message);
    } finally {
      set({ analyzing: false });
    }
  },

  setContinuous(on) {
    const { timer } = get();
    if (timer) window.clearInterval(timer);
    if (!on) {
      set({ continuous: false, timer: null });
      return;
    }
    const interval = Math.max(2, useApp.getState().settings?.continuous_interval_s ?? 5) * 1000;
    const tick = async () => {
      const s = get();
      // Pause while VEENA is minimised or hidden, or a request is in flight.
      const live = useApp.getState().live;
      const busy = !!live && !live.done && !live.error;
      if (!s.sharing || !s.video || document.hidden || s.analyzing || busy) return;
      const h = frameHash(s.video);
      if (s.lastHash !== null && hamming(h, s.lastHash) < 12) return; // unchanged frame
      set({ lastHash: h });
      await s.analyze("summarize", "Briefly describe what is on screen now and anything that needs attention.", { continuous: true });
    };
    set({ continuous: true, pausedReason: null, lastHash: null, timer: window.setInterval(() => void tick(), interval) });
    void tick();
  },
}));
